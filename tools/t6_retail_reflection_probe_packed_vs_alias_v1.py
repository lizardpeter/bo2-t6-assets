#!/usr/bin/env python3
"""Retained T6 packed vertex-shader alias proof for reflection passes.

This stage extends the direct TEXCOORD5 producer proof without dereferencing
packed zone pointers by guesswork.

For target surface-normal reflection passes it uses two retained structural
relations:

1. Cross-map pass identity: the same
   (TechniqueSet name, slot, passIndex, worldVertFormat)
   associates a packed VS pointer in one retained world with a physically
   direct VS payload in another retained world. Components containing more than
   one direct SHA fail closed.

2. Introduction grammar: for each target packed pointer, its first target use
   is paired with the latest physically direct VS introduced earlier in the
   same serialized TechniqueSet occurrence. Across the 60 target pointer
   identities independently anchored by relation (1), this rule must agree
   60/60. Only then is it used to close the four otherwise-unanchored target
   pointers.

The result assigns all 64 unique target packed VS pointers / 5,612 packed pass
occurrences to one of the 16 physically retained direct VS payloads already
proved to emit:

    TEXCOORD5.xyz = (dlights.worldMatrix * float4(POSITION.xyz,1)).xyz

This is a structural alias proof, not a direct virtual-block-offset
dereference. CPU-side semantics of worldMatrix remain outside the proof.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json
from pathlib import Path

EXPECTED_TARGET_SHADERS=4086
EXPECTED_TARGET_PASSES=5676
EXPECTED_DIRECT_OCC=64
EXPECTED_PACKED_OCC=5612
EXPECTED_UNIQUE_DIRECT=16
EXPECTED_UNIQUE_TARGET_PTR=64
EXPECTED_CROSSMAP_ANCHORED_PTR=60
EXPECTED_INTRO_ONLY_PTR=4
EXPECTED_INTRO_VALIDATION=60

def load(path:Path,name:str):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s); assert s.loader
    s.loader.exec_module(m); return m

def jhash(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class DSU:
    def __init__(self): self.p={}
    def find(self,x):
        self.p.setdefault(x,x)
        if self.p[x]!=x:self.p[x]=self.find(self.p[x])
        return self.p[x]
    def union(self,a,b):
        a=self.find(a); b=self.find(b)
        if a!=b:self.p[b]=a

def collect_events(root:Path,producer):
    all_events={}; direct_blobs={}
    for mn,cfg in producer.PASS_MAPS.items():
        d=(root/cfg['rel']).read_bytes()
        actual=hashlib.sha256(d).hexdigest()
        if actual!=cfg['sha']:raise ValueError(f'{mn}: source mismatch {actual}')
        blocks=producer.ff_front(d); count=cfg['q1']-cfg['q0']+1
        rows=producer.ff_scan_tech(d,blocks,cfg['world'])[-count:]
        if len(rows)!=count:raise ValueError(f'{mn}: TechniqueSet count {len(rows)}')
        events=[]
        for ti,r in enumerate(rows):
            nxt=rows[ti+1]['fixedStart'] if ti+1<len(rows) else cfg['world']
            ts=producer.ff_parse_techset(d,r,nxt,blocks)
            for tr in ts['techniqueRefs']:
                it=tr.get('inlineTechnique')
                if not it:continue
                for pa in it['passes']:
                    vs=pa['children']['vertexShader']; vi=vs.get('inline')
                    node=None
                    if vi and vi['program']['direct']:
                        vp=vi['program']; vh=vp['sha256']
                        blob=d[vp['start']:vp['start']+vp['bytes']]
                        if hashlib.sha256(blob).hexdigest()!=vh:raise ValueError('direct VS hash mismatch')
                        old=direct_blobs.setdefault(vh,blob)
                        if old!=blob:raise ValueError('direct VS SHA collision')
                        node=('sha',vh)
                    elif vs['kind']=='packed':
                        node=('ptr',mn,vs.get('block'),vs.get('offset'))
                    ps=pa['children']['pixelShader']; pi=ps.get('inline')
                    ph=pi['program']['sha256'] if pi and pi['program']['direct'] else None
                    events.append({
                        'eventIndex':len(events),'techniqueSetOrdinal':ti,'techniqueSet':ts['name'],
                        'worldVertFormat':ts['worldVertFormat'],'slot':tr['slot'],'passIndex':pa['passIndex'],
                        'pixelShaderSha256':ph,'vertexNode':node})
        all_events[mn]=events
    return all_events,direct_blobs

def build(root:Path,producer_verifier:Path,coordinate_verifier:Path,mip_verifier:Path,
          weight_verifier:Path,angular_verifier:Path,semantic_verifier:Path,
          surface_verifier:Path,shared_verifier:Path,guard_path:Path):
    producer=load(producer_verifier,'producer')
    coord=load(coordinate_verifier,'coord');mip=load(mip_verifier,'mip')
    weight=load(weight_verifier,'weight');angular=load(angular_verifier,'angular')
    sem=load(semantic_verifier,'sem');surf=load(surface_verifier,'surf')
    shared=load(shared_verifier,'shared');guard=load(guard_path,'guard')
    target=producer.collect_target_shaders(root,coord,mip,weight,angular,sem,surf,shared,guard)
    if len(target)!=EXPECTED_TARGET_SHADERS:raise ValueError(f'target shader count {len(target)}')

    events,direct_blobs=collect_events(root,producer)

    # Independent cross-map structural anchoring over every retained VS node.
    dsu=DSU(); by_key=collections.defaultdict(set)
    for mn,evs in events.items():
        for e in evs:
            n=e['vertexNode']
            if n is None:continue
            key=(e['techniqueSet'],e['slot'],e['passIndex'],e['worldVertFormat'])
            by_key[key].add(n)
    for nodes in by_key.values():
        q=list(nodes)
        for n in q[1:]:dsu.union(q[0],n)

    comp_shas=collections.defaultdict(set)
    comp_nodes=collections.defaultdict(set)
    for n in list(dsu.p):
        r=dsu.find(n);comp_nodes[r].add(n)
        if n[0]=='sha':comp_shas[r].add(n[1])

    # Target pass/pointer population.
    target_ptr_occ=collections.Counter(); first_target={}; direct_occ=packed_occ=0
    target_occ=[]
    for mn,evs in events.items():
        for e in evs:
            if e['pixelShaderSha256'] not in target or e['vertexNode'] is None:continue
            target_occ.append((mn,e))
            n=e['vertexNode']
            if n[0]=='sha':direct_occ+=1
            else:
                packed_occ+=1;target_ptr_occ[n]+=1;first_target.setdefault(n,e)

    if (len(target_occ),direct_occ,packed_occ)!=(EXPECTED_TARGET_PASSES,EXPECTED_DIRECT_OCC,EXPECTED_PACKED_OCC):
        raise ValueError(f'target occurrence census {(len(target_occ),direct_occ,packed_occ)}')
    if len(target_ptr_occ)!=EXPECTED_UNIQUE_TARGET_PTR:
        raise ValueError(f'unique target pointer count {len(target_ptr_occ)}')

    # Structural anchors.
    structural={}
    conflicts=[]
    for ptr in target_ptr_occ:
        r=dsu.find(ptr); shas=comp_shas[r]
        if len(shas)>1:conflicts.append((ptr,sorted(shas)))
        elif len(shas)==1:structural[ptr]=next(iter(shas))
    if conflicts:raise ValueError(f'target structural SHA conflicts {conflicts[:3]}')
    if len(structural)!=EXPECTED_CROSSMAP_ANCHORED_PTR:
        raise ValueError(f'structurally anchored target pointers {len(structural)}')

    # Introduction rule: latest direct VS earlier in the same serialized TS occurrence.
    intro={}
    intro_rows=[]
    for ptr,fe in first_target.items():
        mn=ptr[1]
        candidates=[
            e for e in events[mn]
            if e['techniqueSetOrdinal']==fe['techniqueSetOrdinal']
            and e['eventIndex']<fe['eventIndex']
            and e['vertexNode'] is not None and e['vertexNode'][0]=='sha'
        ]
        if not candidates:raise ValueError(f'{ptr}: no prior direct VS in introducing TechniqueSet')
        q=candidates[-1]
        distance=fe['eventIndex']-q['eventIndex']
        pat=(q['slot'],fe['slot'],distance)
        if pat not in ((4,5,1),(6,8,2)):
            raise ValueError(f'{ptr}: unexpected introduction pattern {pat}')
        intro[ptr]=q['vertexNode'][1]
        intro_rows.append({
            'map':ptr[1],'block':ptr[2],'offset':ptr[3],
            'firstTargetTechniqueSet':fe['techniqueSet'],
            'firstTargetWorldVertFormat':fe['worldVertFormat'],
            'firstTargetSlot':fe['slot'],'introductionDirectSlot':q['slot'],
            'introductionDistance':distance,'introducedVertexShaderSha256':q['vertexNode'][1]
        })

    # Validate intro rule only against the independently anchored 60.
    mismatch=[p for p,s in structural.items() if intro.get(p)!=s]
    if mismatch:raise ValueError(f'introduction rule mismatch on structurally anchored pointers {mismatch[:3]}')
    if len(structural)!=EXPECTED_INTRO_VALIDATION:
        raise ValueError('unexpected introduction validation population')

    # Only after validation, close the four unanchored target pointers.
    resolved=dict(structural)
    for p in target_ptr_occ:
        resolved.setdefault(p,intro[p])
    if len(resolved)!=EXPECTED_UNIQUE_TARGET_PTR:raise ValueError('incomplete target pointer resolution')
    intro_only=[p for p in target_ptr_occ if p not in structural]
    if len(intro_only)!=EXPECTED_INTRO_ONLY_PTR:raise ValueError(f'introduction-only pointer count {len(intro_only)}')

    # Resolve all target pass occurrences and prove all resolved direct payloads.
    resolved_occ=collections.Counter(); direct_target_shas=set()
    for mn,e in target_occ:
        n=e['vertexNode']
        if n[0]=='sha':
            sha=n[1];direct_target_shas.add(sha)
        else:sha=resolved[n]
        resolved_occ[sha]+=1
    if len(resolved_occ)!=EXPECTED_UNIQUE_DIRECT:raise ValueError(f'resolved target VS SHA count {len(resolved_occ)}')
    if len(direct_target_shas)!=EXPECTED_UNIQUE_DIRECT:raise ValueError(f'direct target VS SHA count {len(direct_target_shas)}')
    if set(resolved_occ)!=direct_target_shas:raise ValueError('packed aliases introduce an unproven VS SHA')

    producer_proofs={}
    for sha in sorted(direct_target_shas):
        blob=direct_blobs.get(sha)
        if blob is None:raise ValueError(f'direct target VS bytes unavailable {sha}')
        q=producer.prove_vs(coord,sem,blob)
        if q is None or q['equation']!='TEXCOORD5.xyz = (worldMatrix * float4(POSITION.xyz,1)).xyz':
            raise ValueError(f'{sha}: producer proof failed')
        producer_proofs[sha]=q

    pointer_rows=[]
    for p in sorted(target_ptr_occ,key=lambda x:(x[1],x[2],x[3])):
        fe=first_target[p]
        pointer_rows.append({
            'map':p[1],'block':p[2],'offset':p[3],
            'targetPassOccurrenceCount':target_ptr_occ[p],
            'vertexShaderSha256':resolved[p],
            'structurallyAnchored':p in structural,
            'firstTargetTechniqueSet':fe['techniqueSet'],
            'firstTargetSlot':fe['slot'],
            'introductionDirectSlot':next(x['introductionDirectSlot'] for x in intro_rows if x['map']==p[1] and x['block']==p[2] and x['offset']==p[3]),
            'introductionDistance':next(x['introductionDistance'] for x in intro_rows if x['map']==p[1] and x['block']==p[2] and x['offset']==p[3])
        })
    sha_rows=[{'vertexShaderSha256':s,'resolvedTargetPassOccurrenceCount':n} for s,n in sorted(resolved_occ.items())]
    map_rows=[]
    for mn in producer.PASS_MAPS:
        prs=[r for r in pointer_rows if r['map']==mn]
        map_rows.append({
            'map':mn,'uniqueTargetPackedPointerCount':len(prs),
            'targetPackedPassOccurrenceCount':sum(r['targetPassOccurrenceCount'] for r in prs),
            'structurallyAnchoredPointerCount':sum(r['structurallyAnchored'] for r in prs),
            'introductionOnlyPointerCount':sum(not r['structurallyAnchored'] for r in prs)
        })

    summary={
        'retainedMapCount':5,'surfaceNormalTargetShaderCount':len(target),
        'targetPassOccurrenceCount':len(target_occ),'directVertexShaderOccurrenceCount':direct_occ,
        'packedVertexShaderOccurrenceCount':packed_occ,'uniqueTargetPackedPointerCount':len(pointer_rows),
        'crossMapStructurallyAnchoredPointerCount':len(structural),
        'crossMapStructuralConflictCount':0,
        'introductionRuleValidationCount':len(structural),'introductionRuleValidationFailureCount':0,
        'introductionOnlyPointerCount':len(intro_only),
        'resolvedPackedPointerCount':len(resolved),
        'resolvedPackedOccurrenceCount':packed_occ,
        'resolvedTargetVertexShaderCount':len(resolved_occ),
        'resolvedTargetProducerOccurrenceCount':sum(resolved_occ.values()),
        'producerProofFailureCount':0,
        'pointerRowsSha256':jhash(pointer_rows),'shaRowsSha256':jhash(sha_rows),
        'mapRowsSha256':jhash(map_rows),'introRowsSha256':jhash(sorted(intro_rows,key=lambda x:(x['map'],x['block'],x['offset'])))
    }

    # Compact archival encoding; full forensic rows are pinned by the summary digests.
    map_table=list(producer.PASS_MAPS)
    shader_table=sorted(resolved_occ)
    mi={m:i for i,m in enumerate(map_table)};si={h:i for i,h in enumerate(shader_table)}
    pattern_table=[[4,5,1],[6,8,2]]
    compact_ptr=[]
    for r in pointer_rows:
        pat=[r['introductionDirectSlot'],r['firstTargetSlot'],r['introductionDistance']]
        compact_ptr.append([mi[r['map']],r['block'],r['offset'],r['targetPassOccurrenceCount'],
                            si[r['vertexShaderSha256']],1 if r['structurallyAnchored'] else 0,
                            pattern_table.index(pat)])
    compact_counts=[[si[r['vertexShaderSha256']],r['resolvedTargetPassOccurrenceCount']] for r in sha_rows]
    compact_maps=[[mi[r['map']],r['uniqueTargetPackedPointerCount'],r['targetPackedPassOccurrenceCount'],
                   r['structurallyAnchoredPointerCount'],r['introductionOnlyPointerCount']] for r in map_rows]
    intro_only_rows=[x for x in compact_ptr if not x[5]]

    return {
        'format':'t6-retail-reflection-probe-packed-vs-alias-v1',
        'producer':'tools/t6_retail_reflection_probe_packed_vs_alias_v1.py',
        'sources':{
            'directProducerProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD5_PRODUCER_V1.json',
            'surfaceNormalProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_SURFACE_NORMAL_V1.json',
            'expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in guard.SOURCES.items()}
        },
        'relations':{
            'crossMapPassKey':['TechniqueSet','slot','passIndex','worldVertFormat'],
            'validatedIntroductionPatterns':[
                {'directSlot':4,'firstPackedSlot':5,'eventDistance':1},
                {'directSlot':6,'firstPackedSlot':8,'eventDistance':2}
            ],
            'resolvedProducerEquation':'TEXCOORD5.xyz = (dlights.worldMatrix * float4(POSITION.xyz,1)).xyz'
        },
        'encoding':{
            'mapTable':map_table,'vertexShaderTable':shader_table,'introductionPatternTable':pattern_table,
            'pointerAliasColumns':['mapIndex','block','offset','targetPassOccurrenceCount','vertexShaderIndex','structurallyAnchored01','patternIndex'],
            'resolvedCountColumns':['vertexShaderIndex','resolvedTargetPassOccurrenceCount'],
            'mapCoverageColumns':['mapIndex','uniqueTargetPackedPointerCount','targetPackedPassOccurrenceCount','structurallyAnchoredPointerCount','introductionOnlyPointerCount']
        },
        'pointerAliases':compact_ptr,'resolvedVertexShaderCounts':compact_counts,'mapCoverage':compact_maps,
        'introductionOnlyAliases':intro_only_rows,
        'summary':summary,
        'proofBoundary':'Retained structural alias proof for the 5,612 packed paired-VS occurrences in the 4,086-shader surface-normal reflection subset. Sixty of 64 unique target packed block-5 pointers are independently anchored to exactly one direct VS SHA by cross-map equality of TechniqueSet name + slot + passIndex + worldVertFormat, with zero multi-SHA components. A same-TechniqueSet introduction grammar (direct slot 4 -> first packed slot 5 at distance 1, or direct slot 6 -> first packed slot 8 at distance 2) agrees with all 60 independent anchors before being used to resolve the four otherwise-unanchored pointers. All 64 pointer identities / 5,612 packed occurrences then resolve to the same 16 physically retained direct VS payloads, each rerun through the exact TEXCOORD5 producer proof. Compact manifest rows are backed by SHA-256 digests of the full forensic rows. This does not directly dereference virtual block-5 offsets and does not assign camera/view semantics to dlights.worldMatrix.'
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'))
    ap.add_argument('--producer-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord5_producer_v1.py'))
    ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
    ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'))
    ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
    ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'))
    ap.add_argument('--semantic-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_semantics_v1.py'))
    ap.add_argument('--surface-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_surface_normal_v1.py'))
    ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'))
    ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    d=build(a.root,a.producer_verifier,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.semantic_verifier,a.surface_verifier,a.shared_verifier,a.guard)
    a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
