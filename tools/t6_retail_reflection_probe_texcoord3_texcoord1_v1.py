#!/usr/bin/env python3
"""Retained proof for T6 reflection family A=TEXCOORD3, B=TEXCOORD1.

Global DXBC classification is exhaustive over the five pinned retail expanded worlds.
Physical role promotion is limited to shader identities recoverable through retained
TechniqueSet/pass ownership. The broader TechniqueSet scan is needed because this
family is not confined to the GfxWorld-attached TechniqueSet tail used by earlier
proofs.

For the mapped subset, four direct VS payloads independently prove:
  TEXCOORD3 = normalize(worldMatrix3x3 * decoded NORMAL0)
  TEXCOORD1.xyz = (worldMatrix * float4(POSITION.xyz,1)).xyz

Two Hijacked packed pointers are cross-map anchored exactly to two direct Raid VS
payloads. Two Nuketown packed pointer identities are bounded to the two directly
introduced Nuketown VS payloads by the same serializer differential invariant used
by the prior TEXCOORD2/TEXCOORD1 proof, calibrated against the 32 independently
resolved alias pairs in the committed packed-VS manifest. Both candidate programs
have identical relevant semantics, so permutation identity is unnecessary.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,re,struct
from pathlib import Path

EXPECTED_GLOBAL=42
EXPECTED_MAPPED=22
EXPECTED_PASSES=24
EXPECTED_DIRECT_OCC=4
EXPECTED_PACKED_OCC=20
EXPECTED_PTRS=4
EXPECTED_DIRECT_VS=4
EXPECTED_TARGET_FETCHES=42

def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def target_match(row):
 a,b=row
 return (a and b and a[0]==('TEXCOORD',3) and b[0]==('TEXCOORD',1))

def global_target(root:Path,base):
 out={};rows=[];target_fetches=0
 for mn,cfg in base.MAPS.items():
  p=root/cfg['rel'];d=p.read_bytes();actual=hashlib.sha256(d).hexdigest()
  if actual!=base.SHAS[mn]:raise ValueError(f'{mn}: expanded SHA mismatch {actual}')
  seen=set()
  for pos,b in base.all_dxbc(d):
   if b'reflectionProbeSampler\x00' not in b:continue
   h=hashlib.sha256(b).hexdigest()
   if h in seen:continue
   seen.add(h)
   try:r=base.family_roles(b)
   except Exception:continue
   mm=[x for x in r if target_match(x)]
   if not mm:continue
   old=out.setdefault(h,{'blob':b,'maps':set(),'roles':r,'targetMatches':len(mm)})
   if old['blob']!=b:raise ValueError('DXBC SHA collision')
   old['maps'].add(mn)
 for h,q in sorted(out.items()):
  target_fetches+=q['targetMatches']
  rows.append({'sha256':h,'maps':sorted(q['maps']),'targetFetchCount':q['targetMatches'],'roleRows':q['roles']})
 if len(out)!=EXPECTED_GLOBAL:raise ValueError(f'global target shader count {len(out)}')
 if target_fetches!=EXPECTED_TARGET_FETCHES:raise ValueError(f'target fetch count {target_fetches}')
 return out,rows,target_fetches

def parse_set_loose(base,d,row,blocks):
 s=row['start'];name,p=base.cstr(d,s+152);refs=[]
 for slot,raw in enumerate(struct.unpack_from('<36I',d,s+8)):
  q=base.ptr(raw,blocks);q['slot']=slot
  if q['kind'] in ('following','insert'):
   p,t=base.technique(d,p,blocks);q['tech']=t
  refs.append(q)
 return p,{'name':name,'fmt':row['fmt'],'refs':refs}

def broad_pass_events(root:Path,target:set[str],base):
 all_events={};blobs={};objects={};scan_rows=[]
 for mn,cfg in base.MAPS.items():
  d=(root/cfg['rel']).read_bytes();bs=base.front(d);rawrows=[]
  # same strict candidate scan as base, but retain all candidates before GfxWorld.
  raw=base.scan_sets(d,bs,cfg['world'])
  # base.scan_sets returns tuples in committed 75 verifier; normalize.
  for r in raw:
   if isinstance(r,tuple): rawrows.append({'start':r[0],'fmt':r[1],'name':r[2]})
   else: rawrows.append(r)
  ev=[];bad=0
  for ti,r in enumerate(rawrows):
   try:end,ts=parse_set_loose(base,d,r,bs)
   except Exception:
    bad+=1;continue
   nxt=rawrows[ti+1]['start'] if ti+1<len(rawrows) else cfg['world']
   if end>nxt:
    bad+=1;continue
   for tr in ts['refs']:
    t=tr.get('tech')
    if not t:continue
    for pa in t['passes']:
     v=pa['c']['vs'];vi=v.get('inline');vn=None
     if vi and vi['prog'] and 'sha' in vi['prog']:
      h=vi['prog']['sha'];vn=('sha',h);blobs.setdefault(h,vi['prog']['blob']);objects[(mn,h)]=vi['start']
     elif v['kind']=='packed':vn=('ptr',mn,v['block'],v['offset'])
     ps=pa['c']['ps'];pi=ps.get('inline');ph=pi['prog']['sha'] if pi and pi['prog'] and 'sha' in pi['prog'] else None
     ev.append({'event':len(ev),'ti':ti,'ts':ts['name'],'fmt':ts['fmt'],'slot':tr['slot'],'pass':pa['i'],'ps':ph,'vs':vn})
  all_events[mn]=ev
  scan_rows.append({'map':mn,'techniqueSetCandidateCount':len(rawrows),'rejectedCandidateCount':bad,'parsedPassCount':len(ev),'targetPassCount':sum(e['ps'] in target for e in ev)})
 return all_events,blobs,objects,scan_rows

class DSU:
 def __init__(self):self.p={}
 def f(self,x):
  self.p.setdefault(x,x)
  if self.p[x]!=x:self.p[x]=self.f(self.p[x])
  return self.p[x]
 def u(self,a,b):
  a=self.f(a);b=self.f(b)
  if a!=b:self.p[b]=a

def prove_vs_tc3(base,b:bytes):
 w=base.words(b);inst=list(base.walk(w));si=base.signature(b,b'ISGN');so=base.signature(b,b'OSGN')
 def oreg(sem):
  a=[r for r,s in so.items() if s==sem]
  if len(a)!=1:raise ValueError('output semantic '+str(sem))
  return a[0]
 # normal path: TC3 xyz must be MOV from normalized TEMP whose raw source leaves are NORMAL0 only.
 r=oreg(('TEXCOORD',3));ow=[base.latest(inst,w,len(inst),base.OUTPUT,r,c) for c in 'xyz']
 if any(x is None for x in ow) or len({x[0] for x in ow})!=1 or ow[0][2]!=54:raise ValueError('TC3 writer')
 O=ow[0][4];src=O[1] if len(O)>1 else None
 if not src or src['type']!=base.TEMP:raise ValueError('TC3 source')
 nr=src['idx'][0];nw=[base.latest(inst,w,ow[0][0],base.TEMP,nr,c) for c in 'xyz']
 if any(x is None for x in nw) or len({x[0] for x in nw})!=1 or nw[0][2]!=56:raise ValueError('TC3 normalize MUL')
 mul=nw[0][4];vec=None
 for scalar,raw in ((mul[1],mul[2]),(mul[2],mul[1])):
  if scalar['type']==base.TEMP and len(set(scalar['comps'][:3]))==1 and raw['type']==base.TEMP:vec=raw
 if vec is None:raise ValueError('TC3 normalize split')
 leaves=base.input_leaves(b,w,inst,nw[0][0],vec,si)
 if leaves!={('NORMAL',0)}:raise ValueError('TC3 normal leaves '+str(leaves))
 # ensure raw transformed vector is three DP3s against cb3 rows 0,1,2.
 vr=vec['idx'][0];dps=[base.latest(inst,w,nw[0][0],base.TEMP,vr,c) for c in 'xyz']
 if any(x is None for x in dps) or [x[2] for x in dps]!=[16,16,16]:raise ValueError('TC3 world DP3')
 rows=[]
 for q in dps:
  cbs=[x for x in q[4][1:] if x['type']==base.CB and len(x['idx'])>=2]
  if len(cbs)!=1 or cbs[0]['idx'][0]!=3:raise ValueError('TC3 world cb')
  rows.append(cbs[0]['idx'][1])
 if rows!=[0,1,2]:raise ValueError('TC3 world rows '+str(rows))
 # position path: TC1 xyz traces POSITION0 only and is DP4 cb3 rows 0,1,2.
 rp=oreg(('TEXCOORD',1));pw=[base.latest(inst,w,len(inst),base.OUTPUT,rp,c) for c in 'xyz']
 if any(x is None for x in pw) or len({x[0] for x in pw})!=1 or pw[0][2]!=54:raise ValueError('TC1 writer')
 PO=pw[0][4];psrc=PO[1] if len(PO)>1 else None
 if not psrc:raise ValueError('TC1 source')
 pleaves=base.input_leaves(b,w,inst,pw[0][0],psrc,si)
 if pleaves!={('POSITION',0)}:raise ValueError('TC1 leaves '+str(pleaves))
 cur=psrc;before=pw[0][0]
 for _ in range(4):
  if cur['type']!=base.TEMP or len(cur['idx'])!=1:break
  sr=cur['idx'][0];ww=[base.latest(inst,w,before,base.TEMP,sr,c) for c in 'xyz']
  if any(x is None for x in ww) or len({x[0] for x in ww})!=1 or ww[0][2]!=54:break
  OO=ww[0][4]
  if len(OO)!=2 or OO[1]['type']!=base.TEMP:break
  before=ww[0][0];cur=OO[1]
 sr=cur['idx'][0];pdps=[base.latest(inst,w,before,base.TEMP,sr,c) for c in 'xyz']
 if any(x is None for x in pdps) or [x[2] for x in pdps]!=[17,17,17]:raise ValueError('TC1 world DP4')
 prows=[]
 for q in pdps:
  cbs=[x for x in q[4][1:] if x['type']==base.CB and len(x['idx'])>=2]
  if len(cbs)!=1 or cbs[0]['idx'][0]!=3:raise ValueError('TC1 world cb')
  prows.append(cbs[0]['idx'][1])
 if prows!=[0,1,2]:raise ValueError('TC1 world rows '+str(prows))
 return {'vertexShaderSha256':hashlib.sha256(b).hexdigest(),'texcoord3InputLeaves':sorted(map(list,leaves)),'texcoord3WorldMatrixRows':rows,'texcoord1InputLeaves':sorted(map(list,pleaves)),'texcoord1WorldMatrixRows':prows}

def build(root:Path,base_path:Path,prior_alias_path:Path):
 base=load(base_path,'base75')
 target,grows,target_fetches=global_target(root,base);T=set(target)
 events,blobs,objects,scan_rows=broad_pass_events(root,T,base)
 # all retained nodes joined by exact TechniqueSet/slot/pass/worldVertFormat identity across maps
 ds=DSU();by=collections.defaultdict(set)
 for mn,ev in events.items():
  for e in ev:
   if e['vs'] is not None:by[(e['ts'],e['slot'],e['pass'],e['fmt'])].add(e['vs'])
 for nodes in by.values():
  q=list(nodes)
  for n in q[1:]:ds.u(q[0],n)
 comp=collections.defaultdict(set)
 for n in list(ds.p):
  if n[0]=='sha':comp[ds.f(n)].add(n[1])
 occ=[];ptrs=collections.Counter();direct=[]
 for mn,ev in events.items():
  for e in ev:
   if e['ps'] not in T:continue
   occ.append((mn,e));n=e['vs']
   if n and n[0]=='sha':direct.append((mn,n[1]))
   elif n:ptrs[n]+=1
 mapped={e['ps'] for _,e in occ}
 if (len(mapped),len(occ),len(direct),sum(ptrs.values()),len(ptrs))!=(EXPECTED_MAPPED,EXPECTED_PASSES,EXPECTED_DIRECT_OCC,EXPECTED_PACKED_OCC,EXPECTED_PTRS):
  raise ValueError('mapped census '+str((len(mapped),len(occ),len(direct),sum(ptrs.values()),len(ptrs))))
 structural={};conf=[]
 for p in ptrs:
  s=comp[ds.f(p)]
  if len(s)==1:structural[p]=next(iter(s))
  elif len(s)>1:conf.append((p,sorted(s)))
 if conf:raise ValueError('structural conflicts '+str(conf))
 # Hijacked pair must exact-anchor cross-map; Nuketown pair remains set-bounded.
 hij=[p for p in ptrs if p[1]=='mp_hijacked'];nuke=[p for p in ptrs if p[1]=='mp_nuketown_2020']
 if len(hij)!=2 or len(nuke)!=2 or any(p not in structural for p in hij) or any(p in structural for p in nuke):raise ValueError('pointer anchor split')
 direct_shas=sorted({h for _,h in direct})
 if len(direct_shas)!=EXPECTED_DIRECT_VS:raise ValueError('direct VS count')
 proofs=[prove_vs_tc3(base,blobs[h]) for h in direct_shas]
 # Cross-map Hijacked anchors must land on the two direct Raid candidates.
 raid={h for mn,h in direct if mn=='mp_raid'}
 if {structural[p] for p in hij}!=raid:raise ValueError('Hijacked anchor candidates')
 # Calibrate serializer differential from prior 64-pointer alias proof, then bound Nuketown pair.
 prior=json.loads(prior_alias_path.read_text());drifts=base.calibrate(root,prior,objects);maxd=max(drifts)
 if len(drifts)!=32 or maxd!=12:raise ValueError('calibration')
 np=sorted(p[3] for p in nuke);pd=np[1]-np[0]
 starts={h:s for (mn,h),s in objects.items() if mn=='mp_nuketown_2020'}
 pairs=[];hs=sorted(starts)
 for i,a in enumerate(hs):
  for b in hs[i+1:]:
   od=abs(starts[b]-starts[a]);drift=abs(od-pd)
   if drift<=maxd:pairs.append((drift,a,b,od))
 nuke_direct={h for mn,h in direct if mn=='mp_nuketown_2020'}
 if len(pairs)!=1 or set(pairs[0][1:3])!=nuke_direct:raise ValueError('Nuketown candidate pair '+str(pairs))
 # Every mapped PS has a target role exactly A=TC3.xyz, B=TC1.xyz.
 mapped_rows=[]
 for h in sorted(mapped):
  mm=[x for x in target[h]['roles'] if target_match(x)]
  if len(mm)!=1 or mm[0][0][1]!='xyz' or mm[0][1][1]!='xyz':raise ValueError('mapped role shape '+h)
  mapped_rows.append(h)
 summary={
  'globalFamilyShaderCount':len(target),'globalFamilyFetchCount':target_fetches,
  'mappedPixelShaderCount':len(mapped),'mappedPassOccurrenceCount':len(occ),'unmappedPixelShaderCount':len(target)-len(mapped),
  'directVertexShaderOccurrenceCount':len(direct),'packedVertexShaderOccurrenceCount':sum(ptrs.values()),'uniquePackedPointerCount':len(ptrs),
  'directVertexShaderCount':len(direct_shas),'directVertexShaderRoleProofCount':len(proofs),
  'crossMapAnchoredPackedPointerCount':len(structural),'crossMapAnchorConflictCount':0,
  'priorAliasCalibrationPairCount':len(drifts),'priorAliasCalibrationMaxDifferentialDriftBytes':maxd,
  'nuketownTargetPointerSpacingBytes':pd,'nuketownCandidateObjectSpacingBytes':pairs[0][3],'nuketownDifferentialDriftBytes':pairs[0][0],
  'nuketownCandidatePairAmbiguityCount':0,'closedMappedShaderCount':len(mapped),'remainingUnmappedFamilyShaderCount':len(target)-len(mapped),
  'globalShaderRowsSha256':jhash(grows),'mappedShaderSetSha256':jhash(mapped_rows),'directVertexShaderProofRowsSha256':jhash(proofs),'scanRowsSha256':jhash(scan_rows)
 }
 return {
  'format':'t6-retail-reflection-probe-texcoord3-texcoord1-v1',
  'producer':'tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py',
  'equation':{
   'reflection':'cubeCoord=normalize(TEXCOORD1)-2*N*dot(N,normalize(TEXCOORD1))',
   'mappedSurfaceNormal':'N=normalize(worldMatrix3x3 * decoded NORMAL0)',
   'mappedOpposingVector':'TEXCOORD1.xyz=(worldMatrix*float4(POSITION.xyz,1)).xyz'
  },
  'directVertexShaderProofs':proofs,'scanCoverage':scan_rows,'summary':summary,
  'proofBoundary':'Global retained-DXBC census contains exactly 42 unique reflection shaders with one formula-A fetch normalizing TEXCOORD3 against formula-B TEXCOORD1. Physical role promotion is restricted to 22 identities recovered through the broader retained TechniqueSet graph (24 pass occurrences). Four direct VS payloads independently prove TEXCOORD3 has only NORMAL0 ancestry through normalized cb3/worldMatrix 3x3 transformation and TEXCOORD1 has only homogeneous POSITION ancestry through cb3 rows 0..2. Two Hijacked packed pointers are cross-map anchored exactly to the two direct Raid VS payloads. Two Nuketown packed pointer identities are bounded to the two direct Nuketown VS payloads by the serializer differential invariant calibrated against 32 independently resolved pointer pairs: prior maximum differential drift is 12 bytes; among all direct Nuketown VS objects exactly one pair lies within that bound of the target pointer-pair spacing, namely the two candidates, at 5-byte drift. All four candidates prove identical relevant roles, so pointer permutation identity is unnecessary. Twenty globally retained shader identities remain without retained pass/VS producer mapping and are not promoted.'
 }

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'))
 ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'))
 ap.add_argument('--prior-alias',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json'))
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.base_verifier,a.prior_alias);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
