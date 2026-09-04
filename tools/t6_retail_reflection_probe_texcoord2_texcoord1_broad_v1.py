#!/usr/bin/env python3
"""Broad retained pass-ownership extension for the T6 A=TEXCOORD2, B=TEXCOORD1 reflection family.

This stage inherits the exact 75-shader global family from the earlier proof and
scans the broader retained TechniqueSet population rather than only the
world-attached tail. Direct paired vertex shaders must prove TEXCOORD2 from
NORMAL0 through worldMatrix3x3 and TEXCOORD1 from homogeneous POSITION through
worldMatrix. Reusable packed VS pointers are accepted only when either cross-map
pass-key identity anchors them to one direct VS SHA or a serializer-spacing
candidate set is uniquely bounded using the 32 independently resolved pointer
pairs from the earlier packed-VS alias proof. All accepted candidate VS payloads
must prove identical relevant TEXCOORD roles. Unmapped family identities remain
explicitly unresolved.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

def load(p:Path,n:str):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

EXPECTED_GLOBAL=75;EXPECTED_MAPPED=54;EXPECTED_PASS=58;EXPECTED_DIRECT_OCC=17;EXPECTED_PACKED_OCC=41;EXPECTED_PTR=7;EXPECTED_DIRECT_VS=12
EXPECTED_PRIOR_CLOSED=20;EXPECTED_NEW=34;EXPECTED_REMAIN=21;EXPECTED_ANCHORED=3;EXPECTED_BOUNDED=4;CAL_PAIR_COUNT=32;CAL_MAX_DRIFT=12
FOLLOW=0xffffffff;INSERT=0xfffffffe;MASK=(1<<29)-1

def dec(v,bs):
 if v==0:return ('null',None,None)
 if v==FOLLOW:return ('following',None,None)
 if v==INSERT:return ('insert',None,None)
 e=(v-1)&0xffffffff;b=e>>29;o=e&MASK
 return ('packed',b,o) if b<8 and o<bs[b] else ('bad',b,o)

def front(d):
 bs=struct.unpack_from('<8I',d,8);p=40;sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',d,p);p+=24
 for n in (sc,dc):
  if n:
   ps=struct.unpack_from(f'<{n}I',d,p);p+=4*n
   for x in ps:
    if x==FOLLOW:p=d.index(b'\0',p)+1
 return bs

def cstr(d,p,lim=8192):
 e=d.find(b'\0',p,min(len(d),p+lim));b=d[p:e]
 if e<=p or any(x<32 or x>126 for x in b):raise ValueError('cstring')
 return b.decode(),e+1

def scan_sets(d,bs,before):
 import re
 out=[];p=100000;rx=re.compile(r'[A-Za-z0-9_./$@+~:#-]+')
 while True:
  p=d.find(b'\xff\xff\xff\xff',p,before)
  if p<0:break
  if p+152<before and d[p+4]<=8 and d[p+5:p+8]==b'\0\0\0':
   ps=struct.unpack_from('<36I',d,p+8)
   if any(ps) and all(dec(x,bs)[0]!='bad' for x in ps):
    try:n=cstr(d,p+152,512)[0]
    except:n=None
    if n and rx.fullmatch(n):out.append((p,d[p+4],n))
  p+=1
 return out

def parse_inline_shader(d,p,kind):
 # MaterialVertexShader / MaterialPixelShader: name ptr + program wrapper/loaddef.
 st=p;namep=struct.unpack_from('<I',d,p)[0];p+=4
 if namep==FOLLOW:name,p=cstr(d,p)
 else:name=None
 # program struct: runtime D3D ptr then loadDef {program ptr, programSize}; payload follows loadDef when FOLLOW.
 runtime,progptr,size=struct.unpack_from('<3I',d,p);p+=12
 if progptr!=FOLLOW:return {'name':name,'end':p,'direct':False,'kind':kind}
 blob=d[p:p+size]
 if len(blob)!=size or not blob.startswith(b'DXBC'):raise ValueError('direct shader payload')
 return {'name':name,'end':p+size,'direct':True,'kind':kind,'sha256':hashlib.sha256(blob).hexdigest(),'blob':blob,'start':p,'bytes':size}

def parse_child(d,p,bs,kind):
 v=struct.unpack_from('<I',d,p)[0];p+=4;k,b,o=dec(v,bs)
 if k in ('null','packed'):return {'kind':k,'block':b,'offset':o},p
 if k not in ('following','insert'):raise ValueError('child ptr '+str((kind,k,b,o)))
 q=parse_inline_shader(d,p,kind);return {'kind':'inline','inline':q},q['end']

def parse_tech(d,start,end,bs):
 # MaterialTechniqueSet header 152 bytes, name follows. Techniques are reusable children.
 p=start;v=struct.unpack_from('<I',d,p)[0];p+=4;count=d[p];p+=4;refs=list(struct.unpack_from('<36I',d,p));p+=144
 name,p=cstr(d,p)
 out=[]
 for slot,rv in enumerate(refs):
  if not rv:continue
  k,b,o=dec(rv,bs)
  if k=='packed':out.append({'slot':slot,'packedTechnique':(b,o)});continue
  if k not in ('following','insert'):continue
  # MaterialTechnique header: name pointer + flags/passCount + passArray pointer; reordered pass array precedes name.
  # Empirically retained T6 layout here is 12 bytes and pass records are 20 bytes before child payloads.
  th=p;np,flags_pc,passp=struct.unpack_from('<3I',d,p);p+=12;pc=(flags_pc>>16)&0xffff
  if not pc or pc>64:raise ValueError('pass count')
  passes=[]
  for pi in range(pc):
   if p+20>end:raise ValueError('pass header bounds')
   vs,vd,ps,a0,a1=struct.unpack_from('<5I',d,p);p+=20
   # The actual child objects are serialized after the full pass array, so retain raw ptrs first.
   passes.append({'passIndex':pi,'vsPtr':vs,'psPtr':ps})
  # child objects in pass order: reusable VS, vertex decl, reusable PS, args. We only need VS/PS.
  for pa in passes:
   for fld,kind in [('vs','vs'),('vd','vd'),('ps','ps')]:
    raw=pa['vsPtr'] if fld=='vs' else pa['psPtr'] if fld=='ps' else 0
    if fld=='vd':
     # vertex decl is reusable but not needed; following object is fixed-size/complex. Broad parser below uses legacy helper instead.
     continue
  # abort generic inline route; caller uses known robust parser helpers from prior proof.
  out.append({'slot':slot,'techniqueHeader':th,'passCount':pc})
 return {'name':name,'refs':out}

class DSU:
 def __init__(self):self.p={}
 def f(self,x):
  self.p.setdefault(x,x)
  if self.p[x]!=x:self.p[x]=self.f(self.p[x])
  return self.p[x]
 def u(self,a,b):
  a=self.f(a);b=self.f(b)
  if a!=b:self.p[b]=a

def configure(base_path,broad_path):
 b=load(base_path,'base');q=load(broad_path,'broad')
 return b,q

def prove_vs(b,blob):
 # Reuse the fail-closed role proof from the narrow 75-family verifier.
 return b.prove_vs(blob)

def broad_pass_events(root,target,b):
 # Reuse the broader TechniqueSet event walker from the TEXCOORD3 family verifier.
 q=load(Path(__file__).with_name('t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'),'tc3') if False else None
 raise RuntimeError('broad_pass_events must be provided by configured broad verifier')

def build(root:Path,base_path:Path,broad_path:Path,prior_alias_path:Path):
 b,q=configure(base_path,broad_path)
 G=b.global_target(root);T=set(G)
 if len(T)!=EXPECTED_GLOBAL:raise ValueError('global family count')
 ev,bl,objs,scan=q.broad_pass_events(root,T,b)
 occ=[(mn,e) for mn,es in ev.items() for e in es if e['ps'] in T and e['vs'] is not None]
 mapped={e['ps'] for _,e in occ};direct=[(mn,e['vs'][1],e) for mn,e in occ if e['vs'][0]=='sha'];ptr=collections.Counter(e['vs'] for _,e in occ if e['vs'][0]=='ptr')
 dsh=sorted({h for _,h,_ in direct});proofs=[prove_vs(b,bl[h]) for h in dsh]
 if (len(mapped),len(occ),len(direct),sum(ptr.values()),len(ptr),len(dsh))!=(EXPECTED_MAPPED,EXPECTED_PASS,EXPECTED_DIRECT_OCC,EXPECTED_PACKED_OCC,EXPECTED_PTR,EXPECTED_DIRECT_VS):raise ValueError('broad census '+str((len(mapped),len(occ),len(direct),sum(ptr.values()),len(ptr),len(dsh))))
 # Cross-map structural anchors.
 D=DSU();by=collections.defaultdict(set)
 for mn,es in ev.items():
  for e in es:
   if e['vs'] is not None:by[(e['ts'],e['slot'],e['pass'],e['fmt'])].add(e['vs'])
 for nodes in by.values():
  z=list(nodes)
  for n in z[1:]:D.u(z[0],n)
 comp=collections.defaultdict(set)
 for n in list(D.p):
  if n[0]=='sha':comp[D.f(n)].add(n[1])
 anchors={};conflicts=[]
 for p in ptr:
  ss=comp[D.f(p)]
  if len(ss)>1:conflicts.append((p,sorted(ss)))
  elif len(ss)==1:anchors[p]=next(iter(ss))
 if conflicts:raise ValueError('anchor conflicts '+str(conflicts))
 if len(anchors)!=EXPECTED_ANCHORED:raise ValueError('anchored ptr count '+str(len(anchors)))
 # Calibrate serializer spacing from prior independently resolved 64-pointer manifest.
 prior=json.loads(prior_alias_path.read_text());pa=prior['pointerAliases'];vt=prior['encoding']['vertexShaderTable']
 # Form adjacent pointer pairs by map and nearby offset order; the original proof alternates two producer classes.
 pp=[]
 bym=collections.defaultdict(list)
 for r in pa:bym[r[0]].append(r)
 for mn,rows in bym.items():
  rows=sorted(rows,key=lambda r:r[2])
  for i in range(0,len(rows)-1,2):
   a,z=rows[i],rows[i+1]
   if a[1]==z[1]:pp.append((mn,a,z))
 if len(pp)!=CAL_PAIR_COUNT:raise ValueError('calibration pair count '+str(len(pp)))
 # Direct object positions from broad event scan.
 objpos=collections.defaultdict(dict)
 for mn,es in ev.items():
  for e in es:
   if e['vs'] and e['vs'][0]=='sha' and 'vsObjectStart' in e:objpos[mn].setdefault(e['vs'][1],e['vsObjectStart'])
 drifts=[]
 for mn,a,z in pp:
  sa,sz=vt[a[4]],vt[z[4]]
  if sa not in objpos[mn] or sz not in objpos[mn]:continue
  drifts.append(abs((z[2]-a[2])-abs(objpos[mn][sz]-objpos[mn][sa])))
 if not drifts or max(drifts)>CAL_MAX_DRIFT:raise ValueError('serializer calibration drift '+str(max(drifts) if drifts else None))
 # Bound unanchored target pointer pairs to a unique pair of direct VS objects in the same map.
 bounded={};pairrows=[]
 for mn in b.MAPS:
  ups=sorted([p for p in ptr if p[1]==mn and p not in anchors],key=lambda p:p[3])
  if not ups:continue
  if len(ups)%2:raise ValueError('odd unanchored pointer population '+mn)
  for i in range(0,len(ups),2):
   p0,p1=ups[i],ups[i+1];pd=abs(p1[3]-p0[3]);cands=[]
   vals=sorted(objpos[mn].items(),key=lambda kv:kv[1])
   for a in range(len(vals)):
    for z in range(a+1,len(vals)):
     od=abs(vals[z][1]-vals[a][1]);dr=abs(pd-od)
     if dr<=CAL_MAX_DRIFT:cands.append((vals[a][0],vals[z][0],dr,od))
   if len(cands)!=1:raise ValueError(f'{mn}: serializer candidate ambiguity {p0} {p1} {cands[:8]}')
   s0,s1,dr,od=cands[0]
   if s0 not in dsh or s1 not in dsh:raise ValueError('bounded candidates not direct target VS')
   bounded[p0]={s0,s1};bounded[p1]={s0,s1};pairrows.append({'map':mn,'pointerOffsets':[p0[3],p1[3]],'pointerSpacing':pd,'candidateVertexShaderSha256':[s0,s1],'candidateObjectSpacing':od,'differentialDriftBytes':dr})
 if len(bounded)!=EXPECTED_BOUNDED:raise ValueError('bounded ptr count '+str(len(bounded)))
 if set(ptr)!=(set(anchors)|set(bounded)):raise ValueError('unresolved target packed ptr')
 # Ensure every candidate has the same relevant physical role proof.
 pmap={x['vertexShaderSha256']:x for x in proofs}
 for p,s in anchors.items():
  if s not in pmap:raise ValueError('anchor points outside proved VS')
 for p,ss in bounded.items():
  if any(s not in pmap for s in ss):raise ValueError('bounded candidate outside proved VS')
 summary={'inheritedGlobalFamilyShaderCount':len(T),'mappedPixelShaderCount':len(mapped),'mappedPassOccurrenceCount':len(occ),'directVertexShaderOccurrenceCount':len(direct),'packedVertexShaderOccurrenceCount':sum(ptr.values()),'uniquePackedPointerCount':len(ptr),'directVertexShaderCount':len(dsh),'directVertexShaderRoleProofCount':len(proofs),'crossMapAnchoredPackedPointerCount':len(anchors),'serializerBoundedPackedPointerCount':len(bounded),'anchorConflictCount':0,'priorAliasCalibrationPairCount':CAL_PAIR_COUNT,'priorAliasCalibrationMaxDifferentialDriftBytes':CAL_MAX_DRIFT,'newlyClosedBeyondPriorWorldTailCount':len(mapped)-EXPECTED_PRIOR_CLOSED,'remainingUnmappedFamilyShaderCount':len(T-mapped),'targetShaderSetSha256':hashlib.sha256(json.dumps(sorted(T),separators=(',',':')).encode()).hexdigest(),'mappedShaderSetSha256':hashlib.sha256(json.dumps(sorted(mapped),separators=(',',':')).encode()).hexdigest(),'directProofRowsSha256':jhash(proofs),'pairRowsSha256':jhash(pairrows),'scanRowsSha256':jhash(scan)}
 if summary['newlyClosedBeyondPriorWorldTailCount']!=EXPECTED_NEW or summary['remainingUnmappedFamilyShaderCount']!=EXPECTED_REMAIN:raise ValueError('closure delta')
 return {'format':'t6-retail-reflection-probe-texcoord2-texcoord1-broad-v1','producer':'tools/t6_retail_reflection_probe_texcoord2_texcoord1_broad_v1.py','sources':{'priorFamilyProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_V1.json','priorPackedAliasCalibration':'manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json'},'equation':{'reflection':'cubeCoord=normalize(TEXCOORD1)-2*N*dot(N,normalize(TEXCOORD1))','surfaceNormal':'N=normalize(worldMatrix3x3 * decoded NORMAL0) via TEXCOORD2','opposingVector':'TEXCOORD1.xyz=(worldMatrix*float4(POSITION.xyz,1)).xyz'},'directVertexShaderProofs':proofs,'serializerBoundedPointerPairs':pairrows,'summary':summary,'proofBoundary':'Broad retained-TechniqueSet ownership extension of the exact 75-shader A=TEXCOORD2, B=TEXCOORD1 reflection family. Fifty-four shader identities are now physically mapped in 58 retained pass occurrences. Twelve direct paired VS payloads independently prove TEXCOORD2 as NORMAL0/worldMatrix3x3 and TEXCOORD1 as homogeneous POSITION/worldMatrix. Three reusable packed pointer identities are cross-map structurally anchored to one direct VS SHA; four more are bounded in two pointer pairs to unique two-VS candidate sets using serializer differential spacing calibrated against 32 independently resolved pointer pairs from the earlier packed-VS alias proof. Every candidate VS has the same relevant TEXCOORD roles, so no pointer permutation is required. Twenty-one family shader identities remain explicitly unmapped/unresolved; camera/view semantics of TEXCOORD1 remain outside this proof.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'));ap.add_argument('--broad-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'));ap.add_argument('--prior-alias',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.base_verifier,a.broad_verifier,a.prior_alias);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
