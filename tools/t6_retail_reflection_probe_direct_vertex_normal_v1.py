#!/usr/bin/env python3
"""Retained T6 direct-vertex-normal reflection role proof.

This stage closes the reflection family whose pixel shader uses:

    A = normalize(TEXCOORD1.xyz)
    B = normalize(TEXCOORD5.xyz)
    cubeCoord = B - 2*A*dot(A,B)

There are 616 unique retained reflection shaders with that exact operand shape.
374 of those shaders are physically mapped into the retained TechniqueSet
passes, giving 902 pass occurrences. Their 24 packed VS pointers resolve to
8 direct VS payloads using the same cross-map structural relation plus the
already-validated introduction grammar.

For all 8 VS payloads this verifier proves TEXCOORD1.xyz is emitted from a
normalized three-component vector whose raw components are DP3s against
dlights.worldMatrix rows cb3[0..2], and the non-matrix vector has conservative
input ancestry exclusively to ISGN NORMAL0. TEXCOORD5 is independently rerun
through the exact homogeneous POSITION/worldMatrix producer proof.

This promotes A to a transformed vertex-normal path only for the 902 mapped
pass occurrences / 374 mapped pixel-shader identities. The other 242 unique
pixel shaders in the 616-shader operand family remain unmapped and are not
given vertex-producer semantics here.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path

EXPECTED_GLOBAL_PS=616
EXPECTED_MAPPED_PS=374
EXPECTED_PASS_OCC=902
EXPECTED_DIRECT_OCC=24
EXPECTED_PACKED_OCC=878
EXPECTED_PTR=24
EXPECTED_STRUCT=18
EXPECTED_INTRO_ONLY=6
EXPECTED_VS=8

TYPE_TEMP=0;TYPE_INPUT=1;TYPE_OUTPUT=2;TYPE_CB=8
OP_MOV=54;OP_DP3=16

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def rawclass(surf,sig,coord,latest,z):
 r=z['raw']
 if r['type']==TYPE_INPUT and len(r['idx'])==1:
  ss=sig.get(r['idx'][0]);return f'{ss[0]}{ss[1]}.{z["rawComponents"]}' if ss else f'INPUT{r["idx"][0]}.{z["rawComponents"]}'
 if r['type']==TYPE_TEMP:
  ws=[latest(z['normWriter'],r['idx'][0],ch) for ch in set(z['rawComponents'])]
  opn=ws[0][2] if all(ws) and len({x[0] for x in ws})==1 else -1
  return f'TEMP_OP{opn}'
 return f'TYPE{r["type"]}'

def collect_pixel_targets(root,prod,coord,weight,surf,shared,guard):
 allref={}
 for mn,(rel,sha) in guard.SOURCES.items():
  path=root/rel
  if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError(f'{mn}: source mismatch')
  valid,_=guard.scan_map(path)
  for hh,(blob,res) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in res):allref.setdefault(hh,(blob,res))
 targets=set()
 for hh,(blob,res) in sorted(allref.items()):
  sig=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst)
  hit=0
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);rr,ss=O[2],O[3]
   if not(rr['type']==7 and ss['type']==6 and rr['idx']==[15] and ss['idx']==[15]):continue
   roles=surf.formula_roles(coord,w,inst,latest,si,p,op)
   if roles is None:raise ValueError(f'{hh}: reflect role mapping failed')
   A=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A'])
   B=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
   if A is None or B is None:raise ValueError(f'{hh}: normalized role unresolved')
   if (rawclass(surf,sig,coord,latest,A),rawclass(surf,sig,coord,latest,B))==('TEXCOORD1.xyz','TEXCOORD5.xyz'):
    hit+=1
  if hit:
   if hit!=1:raise ValueError(f'{hh}: target reflection fetch count {hit}')
   targets.add(hh)
 if len(targets)!=EXPECTED_GLOBAL_PS:raise ValueError(f'global target PS count {len(targets)}')
 return targets

def input_ancestry(prod,coord,blob,inst,tab,before,src,seen=None):
 if seen is None:seen=set()
 isgn=prod.signature(blob,b'ISGN')
 if src['type']==TYPE_INPUT:
  if len(src['idx'])!=1:return {('INPUT?',-1)}
  return {isgn.get(src['idx'][0],('INPUT',src['idx'][0]))}
 if src['type']!=TYPE_TEMP or len(src['idx'])!=1:return set()
 out=set();reg=src['idx'][0]
 for ch in set(src['comps'] or 'x'):
  key=(before,reg,ch)
  if key in seen:continue
  seen.add(key);wr=prod.latest(tab,TYPE_TEMP,reg,ch,before)
  if wr is None:continue
  wi,p,op,d,O=wr
  for s in O[1:]:
   if s['type']==TYPE_INPUT:
    if len(s['idx'])==1:out.add(isgn.get(s['idx'][0],('INPUT',s['idx'][0])))
   elif s['type']==TYPE_TEMP and len(s['idx'])==1:
    out|=input_ancestry(prod,coord,blob,inst,tab,wi,s,seen)
 return out

def prove_vs(prod,coord,sem,surf,blob):
 base=prod.prove_vs(coord,sem,blob)
 if base is None:raise ValueError('TEXCOORD5 world-position producer failed')
 osgn=prod.signature(blob,b'OSGN');regs=[r for r,s in osgn.items() if s==('TEXCOORD',1)]
 if len(regs)!=1:raise ValueError(f'TEXCOORD1 OSGN count {len(regs)}')
 oreg=regs[0];w=coord.get_program_words(blob);inst=list(coord.walk(w));tab=prod.writer_table(coord,w,inst)
 out=[prod.latest(tab,TYPE_OUTPUT,oreg,ch,len(inst)) for ch in 'xyz']
 if any(x is None for x in out) or len({x[0] for x in out})!=1 or out[0][2]!=OP_MOV:raise ValueError('TEXCOORD1 xyz final MOV failed')
 oi,p,op,d,O=out[0]
 if d['comps']!='xyz' or len(O)!=2:raise ValueError('TEXCOORD1 MOV shape')
 src=O[1];latest=lambda before,reg,ch:prod.latest(tab,TYPE_TEMP,reg,ch,before)
 norm=surf.normalized_raw(coord,w,inst,latest,oi,src)
 if norm is None:raise ValueError('TEXCOORD1 source is not normalized vector')
 raw=norm['raw']
 if raw['type']!=TYPE_TEMP or len(raw['idx'])!=1 or norm['rawComponents']!='xyz':raise ValueError('normal raw vector shape')
 rr=raw['idx'][0];rw=[latest(norm['normWriter'],rr,ch) for ch in 'xyz']
 if any(x is None for x in rw) or len({x[0] for x in rw})!=3 or any(x[2]!=OP_DP3 for x in rw):
  raise ValueError('normal world transform is not three DP3s')
 rows=[];ances=[];rawsig=None
 for ch,q in zip('xyz',rw):
  ii,p,op,d,O=q
  if d['comps']!=ch or len(O)!=3:raise ValueError('normal DP3 shape')
  a,b=O[1],O[2];cb=a if a['type']==TYPE_CB else b if b['type']==TYPE_CB else None
  vv=b if cb is a else a if cb is b else None
  if cb is None or vv is None or len(cb['idx'])!=2:raise ValueError('normal DP3 operands')
  if rawsig is None:rawsig=coord.base_sig(vv)
  elif coord.base_sig(vv)!=rawsig:raise ValueError('normal DP3 source vector identity split')
  cbn,bo,var=sem.cb_var_at(blob,cb['idx'][0],cb['idx'][1],cb['comps'][0]);rows.append((cb['idx'][0],cb['idx'][1],bo,cbn,var))
  ances.append(sorted(input_ancestry(prod,coord,blob,inst,tab,ii,vv)))
 exp=[(3,0,0,'dlights','worldMatrix'),(3,1,16,'dlights','worldMatrix'),(3,2,32,'dlights','worldMatrix')]
 if rows!=exp:raise ValueError(f'normal world rows {rows}')
 if ances!=[[('NORMAL',0)],[('NORMAL',0)],[('NORMAL',0)]]:raise ValueError(f'normal input ancestry {ances}')
 return {'vertexShaderSha256':hashlib.sha256(blob).hexdigest(),'texcoord1OutputRegister':oreg,
         'texcoord1OutputMovInstructionIndex':oi,'normalRawDp3InstructionIndices':[x[0] for x in rw],
         'normalNormalizationWriterIndex':norm['normWriter'],'normalSelfDotInstructionIndex':norm['selfDotIndex'],
         'texcoord5OutputRegister':base['osgnRegister'],'texcoord5ProducerEquation':base['equation']}

def resolve_passes(root,prod,alias,targets):
 events,blobs=alias.collect_events(root,prod);mapped=[];direct=packed=0
 for mn,evs in events.items():
  for e in evs:
   if e['pixelShaderSha256'] not in targets or e['vertexNode'] is None:continue
   mapped.append((mn,e))
   if e['vertexNode'][0]=='sha':direct+=1
   else:packed+=1
 mapped_ps={e['pixelShaderSha256'] for _,e in mapped}
 if (len(mapped_ps),len(mapped),direct,packed)!=(EXPECTED_MAPPED_PS,EXPECTED_PASS_OCC,EXPECTED_DIRECT_OCC,EXPECTED_PACKED_OCC):
  raise ValueError(f'mapped census {(len(mapped_ps),len(mapped),direct,packed)}')
 dsu=alias.DSU();bykey=collections.defaultdict(set)
 for mn,evs in events.items():
  for e in evs:
   n=e['vertexNode']
   if n is None:continue
   bykey[(e['techniqueSet'],e['slot'],e['passIndex'],e['worldVertFormat'])].add(n)
 for ns in bykey.values():
  q=list(ns)
  for n in q[1:]:dsu.union(q[0],n)
 csh=collections.defaultdict(set)
 for n in list(dsu.p):
  if n[0]=='sha':csh[dsu.find(n)].add(n[1])
 ptr=collections.Counter();first={}
 for mn,e in mapped:
  n=e['vertexNode']
  if n[0]=='ptr':ptr[n]+=1;first.setdefault(n,e)
 if len(ptr)!=EXPECTED_PTR:raise ValueError(f'pointer count {len(ptr)}')
 structural={};conf=[]
 for p in ptr:
  ss=csh[dsu.find(p)]
  if len(ss)>1:conf.append((p,sorted(ss)))
  elif len(ss)==1:structural[p]=next(iter(ss))
 if conf:raise ValueError(f'alias conflicts {conf[:2]}')
 if len(structural)!=EXPECTED_STRUCT:raise ValueError(f'structural anchors {len(structural)}')
 intro={}
 patterns=collections.Counter()
 for p,fe in first.items():
  evs=events[p[1]]
  cand=[e for e in evs if e['techniqueSetOrdinal']==fe['techniqueSetOrdinal'] and e['eventIndex']<fe['eventIndex'] and e['vertexNode'] and e['vertexNode'][0]=='sha']
  if not cand:raise ValueError('no direct introduction')
  q=cand[-1];pat=(q['slot'],fe['slot'],fe['eventIndex']-q['eventIndex']);patterns[pat]+=1
  if pat not in ((4,5,1),(6,8,2)):raise ValueError(f'introduction pattern {pat}')
  intro[p]=q['vertexNode'][1]
 bad=[p for p,s in structural.items() if intro[p]!=s]
 if bad:raise ValueError('introduction rule validation failed')
 unresolved=[p for p in ptr if p not in structural]
 if len(unresolved)!=EXPECTED_INTRO_ONLY:raise ValueError(f'introduction-only count {len(unresolved)}')
 resolved={p:structural.get(p,intro[p]) for p in ptr};counts=collections.Counter()
 for mn,e in mapped:
  n=e['vertexNode'];h=n[1] if n[0]=='sha' else resolved[n];counts[h]+=1
 if len(counts)!=EXPECTED_VS or sum(counts.values())!=EXPECTED_PASS_OCC:raise ValueError(f'VS resolved count {len(counts)}')
 return events,blobs,mapped,counts,ptr,structural,patterns

def build(root,producer_verifier,alias_verifier,coordinate_verifier,weight_verifier,surface_verifier,shared_verifier,semantic_verifier,guard_path,matrix_verifier):
 prod=load(producer_verifier,'prod');alias=load(alias_verifier,'alias');coord=load(coordinate_verifier,'coord');weight=load(weight_verifier,'weight')
 surf=load(surface_verifier,'surf');shared=load(shared_verifier,'shared');sem=load(semantic_verifier,'sem');guard=load(guard_path,'guard');matrix=load(matrix_verifier,'matrix')
 targets=collect_pixel_targets(root,prod,coord,weight,surf,shared,guard)
 events,blobs,mapped,counts,ptr,structural,patterns=resolve_passes(root,prod,alias,targets)
 occ,kinds=matrix.collect(root,prod,targets)
 if len(occ)!=EXPECTED_PASS_OCC:raise ValueError('matrix occurrence count')
 shadow=0
 for r in occ:
  code=[a for a in r['arguments'] if a['type']==3]
  ww=[a for a in code if a['codeIndex']==0xD5];vp=[a for a in code if a['codeIndex']==0xE5]
  if len(ww)!=1 or matrix.key(ww[0])!=(3,0,64,3,0xD5,0,4):raise ValueError('world matrix binding')
  if len(vp)!=1 or matrix.key(vp[0])!=(3,576,64,0,0xE5,0,4):raise ValueError('viewProjection binding')
  shadow+=sum(a['codeIndex']==0xED for a in code)
 rows=[]
 for h in sorted(counts):
  b=blobs.get(h)
  if b is None:raise ValueError(f'direct VS bytes missing {h}')
  q=prove_vs(prod,coord,sem,surf,b);q['resolvedPassOccurrenceCount']=counts[h];rows.append(q)
 summary={'globalOperandFamilyShaderCount':len(targets),'mappedPixelShaderCount':len({e['pixelShaderSha256'] for _,e in mapped}),
          'mappedPassOccurrenceCount':len(mapped),'directVertexShaderOccurrenceCount':EXPECTED_DIRECT_OCC,'packedVertexShaderOccurrenceCount':EXPECTED_PACKED_OCC,
          'uniquePackedPointerCount':len(ptr),'crossMapAnchoredPointerCount':len(structural),'introductionRuleValidationCount':len(structural),
          'introductionRuleValidationFailureCount':0,'introductionOnlyPointerCount':len(ptr)-len(structural),'resolvedVertexShaderCount':len(rows),
          'vertexNormalProducerProofCount':len(rows),'vertexNormalProducerFailureCount':0,'normalInputAncestryCheckCount':len(rows)*3,
          'normalInputAncestryFailureCount':0,'texcoord5WorldPositionProducerProofCount':len(rows),'worldMatrixBindingCheckCount':len(occ),
          'viewProjectionBindingCheckCount':len(occ),'shadowLookupBindingCount':shadow,'vertexShaderRowsSha256':jhash(rows),
          'resolvedVsCountsSha256':jhash(sorted(counts.items())),'introductionPatternCountsSha256':jhash(sorted((list(k),v) for k,v in patterns.items()))}
 return {'format':'t6-retail-reflection-probe-direct-vertex-normal-v1','producer':'tools/t6_retail_reflection_probe_direct_vertex_normal_v1.py',
         'sources':{'coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json',
                    'texcoord5ProducerProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD5_PRODUCER_V1.json',
                    'matrixBindingProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_MATRIX_BINDING_V1.json'},
         'equations':{'pixelReflect':'normalize(TEXCOORD5.xyz) - 2 * normalize(TEXCOORD1.xyz) * dot(normalize(TEXCOORD1.xyz), normalize(TEXCOORD5.xyz))',
                      'vertexNormal':'TEXCOORD1.xyz = normalize(worldMatrix3x3 * decoded NORMAL0)',
                      'vertexPosition':'TEXCOORD5.xyz = (worldMatrix * float4(POSITION.xyz,1)).xyz'},
         'vertexShaderRows':rows,'summary':summary,
         'proofBoundary':'Direct retained pixel/vertex/pass proof for the reflection family whose formula operands are A=normalize(TEXCOORD1.xyz), B=normalize(TEXCOORD5.xyz). The global retained DXBC census contains 616 unique shaders with that exact operand family; 374 are physically mapped into 902 retained TechniqueSet pass occurrences. Their 24 packed paired-VS pointers resolve to eight direct VS payloads using 18 conflict-free cross-map anchors plus an introduction grammar validated 18/18 before resolving six remaining pointers. In all eight VS, TEXCOORD1.xyz is a normalized three-DP3 transform through dlights.worldMatrix rows cb3[0..2], and a conservative ancestry walk of the transformed vector reaches only ISGN NORMAL0; TEXCOORD5 independently satisfies the homogeneous POSITION/worldMatrix producer proof. All 902 pass occurrences bind 0xD5 TRANSPOSE_WORLD_MATRIX and 0xE5 TRANSPOSE_VIEW_PROJECTION_MATRIX in the expected destinations. This promotes formula A to a transformed vertex-normal path for the 902 mapped occurrences / 374 mapped PS identities only; 242 globally retained PS identities in this operand family remain without retained pass/VS producer mapping.'}

def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True)
 for n in ('producer-verifier','alias-verifier','coordinate-verifier','weight-verifier','surface-verifier','shared-verifier','semantic-verifier','guard','matrix-verifier'):
  a.add_argument('--'+n,type=Path,required=True)
 a.add_argument('--out',type=Path,required=True);q=a.parse_args()
 d=build(q.root,q.producer_verifier,q.alias_verifier,q.coordinate_verifier,q.weight_verifier,q.surface_verifier,q.shared_verifier,q.semantic_verifier,q.guard,q.matrix_verifier)
 q.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
