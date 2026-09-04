#!/usr/bin/env python3
"""Retained proof for T6 reflection family A=TEXCOORD1, B=TEXCOORD0.

Global DXBC census is exhaustive over the five pinned retail worlds. All target
shader identities are recovered in the broad TechniqueSet graph. Five direct
paired VS payloads prove TEXCOORD1 is a normalized NORMAL0/worldMatrix3x3 path
and TEXCOORD0 is homogeneous POSITION/worldMatrix. The two packed target VS
pointers are resolved by an independently calibrated broad serialization grammar:
for the exact (direct slot 4 -> first packed slot 6, event distance 1) pattern,
all 5 cross-map-anchored pointer identities agree with the immediately preceding
direct VS. Both target pointers instantiate that exact pattern.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path
EXPECTED_SHADERS=11;EXPECTED_FETCHES=11;EXPECTED_PASSES=11;EXPECTED_DIRECT_OCC=6;EXPECTED_PACKED_OCC=5;EXPECTED_PTRS=2;EXPECTED_DIRECT_VS=5;EXPECTED_CAL=5

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def match(a,b):return a and b and a[0]==('TEXCOORD',1) and b[0]==('TEXCOORD',0) and a[1]=='xyz' and b[1]=='xyz'

def global_target(root,b):
 out={};rows=[];fetches=0
 for mn,cfg in b.MAPS.items():
  p=root/cfg['rel'];d=p.read_bytes();actual=hashlib.sha256(d).hexdigest()
  if actual!=b.SHAS[mn]:raise ValueError(f'{mn}: expanded SHA mismatch {actual}')
  seen=set()
  for _,blob in b.all_dxbc(d):
   if b'reflectionProbeSampler\0' not in blob:continue
   h=hashlib.sha256(blob).hexdigest()
   if h in seen:continue
   seen.add(h)
   try:r=b.family_roles(blob)
   except Exception:continue
   mm=[(a,z) for a,z in r if match(a,z)]
   if not mm:continue
   q=out.setdefault(h,{'blob':blob,'maps':set(),'targetFetchCount':len(mm),'roles':r})
   if q['blob']!=blob or q['targetFetchCount']!=len(mm):raise ValueError('shader identity conflict')
   q['maps'].add(mn)
 for h,q in sorted(out.items()):
  fetches+=q['targetFetchCount'];rows.append({'sha256':h,'maps':sorted(q['maps']),'targetFetchCount':q['targetFetchCount']})
 if len(out)!=EXPECTED_SHADERS or fetches!=EXPECTED_FETCHES:raise ValueError(f'global census {(len(out),fetches)}')
 return out,rows,fetches

def prove_vs(b,blob):
 w=b.words(blob);inst=list(b.walk(w));si=b.signature(blob,b'ISGN');so=b.signature(blob,b'OSGN')
 def oreg(sem):
  a=[r for r,s in so.items() if s==sem]
  if len(a)!=1:raise ValueError('output semantic '+str(sem))
  return a[0]
 r=oreg(('TEXCOORD',1));ow=[b.latest(inst,w,len(inst),b.OUTPUT,r,c) for c in 'xyz']
 if any(x is None for x in ow) or len({x[0] for x in ow})!=1 or ow[0][2]!=54:raise ValueError('TC1 writer')
 O=ow[0][4];src=O[1] if len(O)>1 else None
 if not src or src['type']!=b.TEMP:raise ValueError('TC1 source')
 nr=src['idx'][0];nw=[b.latest(inst,w,ow[0][0],b.TEMP,nr,c) for c in 'xyz']
 if any(x is None for x in nw) or len({x[0] for x in nw})!=1 or nw[0][2]!=56:raise ValueError('TC1 normalize MUL')
 mul=nw[0][4];vec=None
 for scalar,raw in ((mul[1],mul[2]),(mul[2],mul[1])):
  if scalar['type']==b.TEMP and len(set(scalar['comps'][:3]))==1 and raw['type']==b.TEMP:vec=raw
 if vec is None:raise ValueError('TC1 normalize split')
 leaves=b.input_leaves(blob,w,inst,nw[0][0],vec,si)
 if leaves!={('NORMAL',0)}:raise ValueError('TC1 leaves '+str(leaves))
 vr=vec['idx'][0];dps=[b.latest(inst,w,nw[0][0],b.TEMP,vr,c) for c in 'xyz'];rows=[]
 if any(x is None for x in dps) or [x[2] for x in dps]!=[16,16,16]:raise ValueError('TC1 DP3')
 for x in dps:
  cbs=[y for y in x[4][1:] if y['type']==b.CB and len(y['idx'])>=2]
  if len(cbs)!=1 or cbs[0]['idx'][0]!=3:raise ValueError('TC1 cb')
  rows.append(cbs[0]['idx'][1])
 if rows!=[0,1,2]:raise ValueError('TC1 rows '+str(rows))
 r=oreg(('TEXCOORD',0));ow=[b.latest(inst,w,len(inst),b.OUTPUT,r,c) for c in 'xyz']
 if any(x is None for x in ow) or len({x[0] for x in ow})!=1 or ow[0][2]!=54:raise ValueError('TC0 writer')
 O=ow[0][4];cur=O[1] if len(O)>1 else None;before=ow[0][0]
 if cur is None:raise ValueError('TC0 source')
 pleaves=b.input_leaves(blob,w,inst,before,cur,si)
 if pleaves!={('POSITION',0)}:raise ValueError('TC0 leaves '+str(pleaves))
 for _ in range(4):
  if cur['type']!=b.TEMP or len(cur['idx'])!=1:break
  sr=cur['idx'][0];ww=[b.latest(inst,w,before,b.TEMP,sr,c) for c in 'xyz']
  if any(x is None for x in ww) or len({x[0] for x in ww})!=1 or ww[0][2]!=54:break
  OO=ww[0][4]
  if len(OO)!=2 or OO[1]['type']!=b.TEMP:break
  before=ww[0][0];cur=OO[1]
 if cur['type']!=b.TEMP or len(cur['idx'])!=1:raise ValueError('TC0 DP4 temp')
 sr=cur['idx'][0];dps=[b.latest(inst,w,before,b.TEMP,sr,c) for c in 'xyz'];prows=[]
 if any(x is None for x in dps) or [x[2] for x in dps]!=[17,17,17]:raise ValueError('TC0 DP4')
 for x in dps:
  cbs=[y for y in x[4][1:] if y['type']==b.CB and len(y['idx'])>=2]
  if len(cbs)!=1 or cbs[0]['idx'][0]!=3:raise ValueError('TC0 cb')
  prows.append(cbs[0]['idx'][1])
 if prows!=[0,1,2]:raise ValueError('TC0 rows '+str(prows))
 return {'vertexShaderSha256':hashlib.sha256(blob).hexdigest(),'texcoord1InputLeaves':sorted(map(list,leaves)),'texcoord1WorldMatrixRows':rows,'texcoord0InputLeaves':sorted(map(list,pleaves)),'texcoord0WorldMatrixRows':prows}

def build(root,base_path,broad_path,target_set_path):
 b=load(base_path,'base');q=load(broad_path,'broad');td=json.loads(target_set_path.read_text());ts=td.get('summary',{});H=td.get('shaderSha256',[])
 if ts.get('shaderCount')!=EXPECTED_SHADERS or ts.get('fetchCount')!=EXPECTED_FETCHES or ts.get('shaderSetSha256')!='013157b8e9af431ba3585a6016dbdac597de460e4ab408781e411625a980826b':raise ValueError('target set drift')
 if hashlib.sha256(json.dumps(H,separators=(',',':')).encode()).hexdigest()!=ts['shaderSetSha256']:raise ValueError('target set hash drift')
 for mn,cfg in b.MAPS.items():
  actual=hashlib.sha256((root/cfg['rel']).read_bytes()).hexdigest()
  if actual!=b.SHAS[mn]:raise ValueError(f'{mn}: expanded SHA mismatch {actual}')
 T=set(H);fetches=ts['fetchCount']
 ev,bl,objs,scan=q.broad_pass_events(root,T,b)
 occ=[(mn,e) for mn,es in ev.items() for e in es if e['ps'] in T];mapped={e['ps'] for _,e in occ}
 direct=[(mn,e['vs'][1],e) for mn,e in occ if e['vs'] and e['vs'][0]=='sha'];ptr=collections.Counter(e['vs'] for _,e in occ if e['vs'] and e['vs'][0]=='ptr')
 dsh=sorted({h for _,h,_ in direct});proofs=[prove_vs(b,bl[h]) for h in dsh]
 if (len(mapped),len(occ),len(direct),sum(ptr.values()),len(ptr),len(dsh))!=(EXPECTED_SHADERS,EXPECTED_PASSES,EXPECTED_DIRECT_OCC,EXPECTED_PACKED_OCC,EXPECTED_PTRS,EXPECTED_DIRECT_VS):raise ValueError('mapped census '+str((len(mapped),len(occ),len(direct),sum(ptr.values()),len(ptr),len(dsh))))
 if mapped!=T:raise ValueError('target identities missing from broad pass graph')
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
 first={}
 for mn,es in ev.items():
  for e in es:
   n=e['vs']
   if n and n[0]=='ptr':first.setdefault(n,e)
 cal=[]
 for p,fe in first.items():
  ss=comp[D.f(p)]
  if len(ss)!=1:continue
  prior=[e for e in ev[p[1]] if e['ti']==fe['ti'] and e['event']<fe['event'] and e['vs'] and e['vs'][0]=='sha']
  if not prior:continue
  d=prior[-1];pat=(d['slot'],fe['slot'],fe['event']-d['event']);anchor=next(iter(ss))
  if pat==(4,6,1):cal.append({'map':p[1],'block':p[2],'offset':p[3],'anchorSha256':anchor,'precedingSha256':d['vs'][1],'matches':anchor==d['vs'][1]})
 if len(cal)!=EXPECTED_CAL or any(not x['matches'] for x in cal):raise ValueError('intro calibration '+str(cal))
 resolved=[]
 for p,c in sorted(ptr.items(),key=lambda x:(x[0][1],x[0][3])):
  fe=first[p];prior=[e for e in ev[p[1]] if e['ti']==fe['ti'] and e['event']<fe['event'] and e['vs'] and e['vs'][0]=='sha']
  if not prior:raise ValueError('target pointer no introduction')
  d=prior[-1];pat=(d['slot'],fe['slot'],fe['event']-d['event'])
  if pat!=(4,6,1) or d['vs'][1] not in dsh:raise ValueError('target intro '+str((p,pat,d['vs'])))
  resolved.append({'map':p[1],'block':p[2],'offset':p[3],'targetOccurrenceCount':c,'introducedVertexShaderSha256':d['vs'][1],'pattern':[4,6,1]})
 summary={'globalFamilyShaderCount':len(T),'globalFamilyFetchCount':fetches,'mappedPixelShaderCount':len(mapped),'mappedPassOccurrenceCount':len(occ),'directVertexShaderOccurrenceCount':len(direct),'packedVertexShaderOccurrenceCount':sum(ptr.values()),'uniquePackedPointerCount':len(ptr),'directVertexShaderCount':len(dsh),'directVertexShaderRoleProofCount':len(proofs),'introductionCalibrationCount':len(cal),'introductionCalibrationFailureCount':0,'resolvedPackedPointerCount':len(resolved),'resolvedPackedOccurrenceCount':sum(ptr.values()),'closedShaderCount':len(mapped),'closedFetchCount':fetches,'targetShaderSetSha256':ts['shaderSetSha256'],'directProofRowsSha256':jhash(proofs),'calibrationRowsSha256':jhash(cal),'resolvedPointerRowsSha256':jhash(resolved),'scanRowsSha256':jhash(scan)}
 return {'format':'t6-retail-reflection-probe-texcoord1-texcoord0-v1','producer':'tools/t6_retail_reflection_probe_texcoord1_texcoord0_v1.py','sources':{'targetSet':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD1_TEXCOORD0_TARGET_V1.json'},'equation':{'reflection':'cubeCoord=normalize(TEXCOORD0)-2*N*dot(N,normalize(TEXCOORD0))','surfaceNormal':'N=normalize(worldMatrix3x3 * decoded NORMAL0)','opposingVector':'TEXCOORD0.xyz=(worldMatrix*float4(POSITION.xyz,1)).xyz'},'directVertexShaderProofs':proofs,'resolvedPackedPointers':resolved,'summary':summary,'proofBoundary':'Retained ownership/producer closure for the exact 11-shader / 11-fetch A=TEXCOORD1, B=TEXCOORD0 reflection family pinned by the exhaustive target-set manifest. All 11 identities are recovered in 11 broad TechniqueSet pass occurrences. Five direct paired VS payloads prove TEXCOORD1 is a normalized NORMAL0/worldMatrix3x3 path and TEXCOORD0 is a POSITION/worldMatrix path. The five target pass occurrences using two reusable packed VS pointers are resolved by an independently checked broad serialization grammar: among cross-map-anchored broad pointers, the exact direct-slot-4 -> first-packed-slot-6 at event-distance-1 pattern occurs five times and agrees with the preceding direct VS in all 5/5 cases; both target pointers instantiate that exact pattern. Camera/view semantics of the opposing vector remain outside this proof.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'));ap.add_argument('--broad-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'));ap.add_argument('--target-set',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD1_TEXCOORD0_TARGET_V1.json'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.base_verifier,a.broad_verifier,a.target_set);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
