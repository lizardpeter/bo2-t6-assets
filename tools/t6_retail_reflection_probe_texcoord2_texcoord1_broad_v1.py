#!/usr/bin/env python3
"""Broad retained ownership extension for the 75-shader T6 reflection family.

This stage intentionally inherits the exhaustive global DXBC census from
T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_V1.json instead of rescanning
all reflection bytecode. The exact 75 shader identities are embedded and pinned
by SHA-256. This verifier proves only newly recovered TechniqueSet/pass ownership,
paired vertex-shader semantics, and packed-VS alias bounds.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path

TARGET_SET_SHA256='be9e44e06742a56170b91ce5f94173fee63c3fbc8c91aaf690cf712b2f8cc0a0'
PRIOR_GLOBAL_ROWS_SHA256='0d088b939b586ee46c7d69f7728046e0c377e12627f2883eba2786d25de5e5f3'
EXPECTED=(75,54,58,17,41,7,12,3,4,21)

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def build(root:Path,base_path:Path,broad_path:Path,prior_alias_path:Path,prior_family_path:Path,target_set_path:Path):
 b=load(base_path,'base75');q=load(broad_path,'broad42')
 targets=json.loads(target_set_path.read_text());TARGET_HASHES=targets.get('shaderSha256',[]);ts=targets.get('summary',{})
 if len(TARGET_HASHES)!=75 or len(set(TARGET_HASHES))!=75 or ts.get('shaderSetSha256')!=TARGET_SET_SHA256 or hashlib.sha256(json.dumps(sorted(TARGET_HASHES),separators=(',',':')).encode()).hexdigest()!=TARGET_SET_SHA256:raise ValueError('target set drift')
 prior_family=json.loads(prior_family_path.read_text())
 ps=prior_family.get('summary',{})
 if ps.get('globalFamilyShaderCount')!=75 or ps.get('globalFamilyFetchCount')!=75 or ps.get('globalShaderRowsSha256')!=PRIOR_GLOBAL_ROWS_SHA256:raise ValueError('prior family manifest mismatch')
 # Hash-pin all retained expanded worlds before ownership parsing.
 for mn,cfg in b.MAPS.items():
  actual=hashlib.sha256((root/cfg['rel']).read_bytes()).hexdigest()
  if actual!=b.SHAS[mn]:raise ValueError(f'{mn}: expanded SHA mismatch {actual}')
 T=set(TARGET_HASHES)
 ev,bl,objs,scan=q.broad_pass_events(root,T,b)
 occ=[(mn,e) for mn,es in ev.items() for e in es if e['ps'] in T]
 mapped={e['ps'] for _,e in occ};direct=[(mn,e['vs'][1],e) for mn,e in occ if e['vs'] and e['vs'][0]=='sha'];ptr=collections.Counter(e['vs'] for _,e in occ if e['vs'] and e['vs'][0]=='ptr')
 if not mapped<=T:raise ValueError('non-target mapped shader')
 dsh=sorted({h for _,h,_ in direct});proofs=[b.prove_vs(bl[h]) for h in dsh]
 # Exact cross-map anchors over all retained pass nodes.
 D=q.DSU();by=collections.defaultdict(set)
 for mn,es in ev.items():
  for e in es:
   if e['vs'] is not None:by[(e['ts'],e['slot'],e['pass'],e['fmt'])].add(e['vs'])
 for nodes in by.values():
  z=list(nodes)
  for n in z[1:]:D.u(z[0],n)
 comp=collections.defaultdict(set)
 for n in list(D.p):
  if n[0]=='sha':comp[D.f(n)].add(n[1])
 structural={};conf=[]
 for p in ptr:
  ss=comp[D.f(p)]
  if len(ss)==1:structural[p]=next(iter(ss))
  elif len(ss)>1:conf.append((p,sorted(ss)))
 if conf:raise ValueError('anchor conflicts '+str(conf))
 if any(h not in dsh for h in structural.values()):raise ValueError('cross-map anchor to unproven direct VS')
 # Serializer calibration from the independently proven 64-pointer alias corpus.
 prior=json.loads(prior_alias_path.read_text());drifts=b.calibrate(root,prior,objs);maxd=max(drifts)
 if len(drifts)!=32 or maxd!=12:raise ValueError('calibration')
 un=[p for p in ptr if p not in structural]
 if len(un)!=4:raise ValueError('unanchored count '+str(len(un)))
 # The four residual Hijacked pointers form two disjoint offset-adjacent reusable pairs.
 uo=sorted(un,key=lambda p:p[3]);pairs=[uo[:2],uo[2:]];pairrows=[];bounded=set()
 for pp in pairs:
  if any(p[1]!='mp_hijacked' for p in pp):raise ValueError('non-Hijacked residual pair')
  pd=pp[1][3]-pp[0][3]
  candidates=[]
  # Candidate set is constrained inside a retained TechniqueSet occurrence that contains both pointers and exactly two direct VS programs.
  for ti in sorted({e['ti'] for e in ev['mp_hijacked'] if e['vs'] in pp}):
   pes=[e for e in ev['mp_hijacked'] if e['ti']==ti]
   if not all(any(e['vs']==p for e in pes) for p in pp):continue
   ds=sorted({e['vs'][1] for e in pes if e['vs'] and e['vs'][0]=='sha'})
   if len(ds)!=2:continue
   od=abs(objs[('mp_hijacked',ds[1])]-objs[('mp_hijacked',ds[0])]);dr=abs(od-pd)
   if dr<=maxd:candidates.append((ti,ds,od,dr))
  if len(candidates)!=1:raise ValueError('pair candidate ambiguity '+str((pp,candidates)))
  ti,ds,od,dr=candidates[0]
  if not set(ds)<=set(dsh):raise ValueError('candidate not proven')
  bounded.update(pp)
  pairrows.append({'pointerOffsets':[pp[0][3],pp[1][3]],'targetOccurrenceCounts':[ptr[pp[0]],ptr[pp[1]]],'candidateVertexShaderSha256':ds,'techniqueSetOrdinal':ti,'pointerSpacingBytes':pd,'candidateObjectSpacingBytes':od,'differentialDriftBytes':dr})
 if len(bounded)!=4:raise ValueError('pair closure')
 census=(len(T),len(mapped),len(occ),len(direct),sum(ptr.values()),len(ptr),len(dsh),len(structural),len(bounded),len(T)-len(mapped))
 if census!=EXPECTED:raise ValueError('census '+str(census))
 # Pin the exact mapped target identity set. Pixel reflect role is inherited from the prior exhaustive family proof.
 mapped_rows=sorted(mapped)
 summary={'inheritedGlobalFamilyShaderCount':len(T),'mappedPixelShaderCount':len(mapped),'mappedPassOccurrenceCount':len(occ),'remainingUnmappedFamilyShaderCount':len(T)-len(mapped),'newlyClosedBeyondPriorWorldTailCount':len(mapped)-ps.get('closedMappedShaderCount',20),'directVertexShaderOccurrenceCount':len(direct),'packedVertexShaderOccurrenceCount':sum(ptr.values()),'uniquePackedPointerCount':len(ptr),'directVertexShaderCount':len(dsh),'directVertexShaderRoleProofCount':len(proofs),'crossMapAnchoredPackedPointerCount':len(structural),'serializerBoundedPackedPointerCount':len(bounded),'anchorConflictCount':0,'priorAliasCalibrationPairCount':len(drifts),'priorAliasCalibrationMaxDifferentialDriftBytes':maxd,'targetShaderSetSha256':TARGET_SET_SHA256,'mappedShaderSetSha256':jhash(mapped_rows),'directProofRowsSha256':jhash(proofs),'pairRowsSha256':jhash(pairrows),'scanRowsSha256':jhash(scan)}
 return {'format':'t6-retail-reflection-probe-texcoord2-texcoord1-broad-v1','producer':'tools/t6_retail_reflection_probe_texcoord2_texcoord1_broad_v1.py','sources':{'inheritedFamilyProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_V1.json','targetSet':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_TARGET_SET_V1.json','packedAliasCalibration':'manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json'},'equation':{'reflection':'cubeCoord=normalize(TEXCOORD1)-2*N*dot(N,normalize(TEXCOORD1))','mappedSurfaceNormal':'N=normalize(worldMatrix3x3 * decoded NORMAL0)','mappedOpposingVector':'TEXCOORD1.xyz=(worldMatrix*float4(POSITION.xyz,1)).xyz'},'directVertexShaderProofs':proofs,'serializerPairBounds':pairrows,'scanCoverage':scan,'summary':summary,'proofBoundary':'Ownership/producer extension only. The exact 75-shader A=TEXCOORD2/B=TEXCOORD1 family and its pixel-side reflect equation are inherited from the previously committed exhaustive DXBC proof and pinned here by the embedded target-set digest. The broader retained TechniqueSet graph physically maps 54 of those 75 identities. All 12 direct paired VS payloads prove TEXCOORD2 from NORMAL0 through normalized worldMatrix3x3 and TEXCOORD1 from POSITION through worldMatrix. Three packed pointer identities are exact cross-map anchors. The remaining four form two reusable Hijacked pointer pairs; each pair is bounded to exactly two direct proven VS candidates in a retained TechniqueSet occurrence, with 3-byte and 5-byte object/pointer spacing drift, inside the independently calibrated 12-byte maximum. Candidate ambiguity is zero within the owning TechniqueSet. Twenty-one target shader identities remain without retained pass/VS ownership and are not promoted.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'));ap.add_argument('--broad-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'));ap.add_argument('--prior-alias',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json'));ap.add_argument('--prior-family',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_V1.json'));ap.add_argument('--target-set',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_TARGET_SET_V1.json'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.base_verifier,a.broad_verifier,a.prior_alias,a.prior_family,a.target_set);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
