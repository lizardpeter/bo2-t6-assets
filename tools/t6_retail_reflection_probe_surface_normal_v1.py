#!/usr/bin/env python3
"""Retained T6 reflection-probe surface-normal role proof.

For the retained reflectionProbeSampler population this stage aligns the
mathematical reflect-form operands with their actual formula roles:

    cubeCoord = B - 2 * A * dot(A,B)

It promotes A to a normal-map-derived surface-normal path only for fetches where
all of the following are directly proven from retained DXBC/RDEF bytes:

  * A is immediately normalized from a TEMP raw vector;
  * rawA = TEXCOORD1.xyz + Nx*TEXCOORD3.xyz + Ny*TEXCOORD2.xyz via two MADs;
  * both Nx and Ny have value ancestry to at least one texture resource whose
    reflected RDEF name contains "normal";
  * B is immediately normalized from ISGN TEXCOORD5.xyz.

The proof intentionally leaves B named TEXCOORD5/viewCandidate rather than
claiming physical view/incident semantics before its vertex-producer provenance
is closed.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

EXPECTED_SHADERS=5868
EXPECTED_FETCHES=5888
EXPECTED_TARGET=4086
TYPE_TEMP=0; TYPE_INPUT=1; TYPE_RESOURCE=7; TYPE_SAMPLER=6
OP_MAD=50; OP_MUL=56; OP_ADD=0; OP_DP3=16


def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def input_signature(blob:bytes):
 cc=struct.unpack_from('<I',blob,28)[0];out={};seen=0
 for off in struct.unpack_from('<'+'I'*cc,blob,32):
  if blob[off:off+4]!=b'ISGN':continue
  seen+=1;n=struct.unpack_from('<I',blob,off+4)[0];r=blob[off+8:off+8+n]
  count=struct.unpack_from('<I',r,0)[0]
  for i in range(count):
   q=8+i*24
   if q+24>len(r):raise ValueError('ISGN entry overflow')
   no,si,sv,ct,reg,maskrw=struct.unpack_from('<6I',r,q);e=r.find(b'\0',no)
   if e<0:raise ValueError('unterminated ISGN semantic')
   out[reg]=(r[no:e].decode('utf-8'),si)
 if seen!=1:raise ValueError(f'ISGN chunk count {seen}')
 return out

def effective(coord,src,dst):return coord.effective_for_dest(src,dst)

def replicated(coord,src,dst):
 try:s=effective(coord,src,dst)
 except ValueError:return False
 return len(s)==len(dst) and len(set(s))==1

def input_vec(coord,src,dst,sig,semantic_index):
 if src['type']!=TYPE_INPUT or len(src['idx'])!=1 or sig.get(src['idx'][0])!=('TEXCOORD',semantic_index):return False
 try:s=effective(coord,src,dst)
 except ValueError:return False
 return s=='xyz'

def normalized_raw(coord,w,inst,latest,before,v):
 if v['type']!=TYPE_TEMP or len(v['idx'])!=1 or not isinstance(v['idx'][0],int):return None
 logical=v['comps'][:3]
 if len(logical)!=3:return None
 ws=[latest(before,v['idx'][0],ch) for ch in set(logical)]
 if any(x is None for x in ws) or len({x[0] for x in ws})!=1:return None
 wi,wp,wop,wd,O=ws[0]
 if wop!=OP_MUL or len(O)!=3:return None
 md,s1,s2=O;cand=[]
 for scalar,raw in ((s1,s2),(s2,s1)):
  try:se=effective(coord,scalar,md['comps']);re=effective(coord,raw,md['comps'])
  except ValueError:continue
  if len(se)==3 and len(set(se))==1 and len(re)==3 and len(set(re))>=2:cand.append((scalar,raw,se,re))
 if len(cand)!=1:return None
 scalar,raw,se,re=cand[0]
 sw=latest(wi,scalar['idx'][0],se[0]) if scalar['type']==TYPE_TEMP and len(scalar['idx'])==1 else None
 if sw is None or sw[2]!=68:return None
 rsq=sw[4]
 if len(rsq)!=2 or rsq[1]['type']!=TYPE_TEMP or len(rsq[1]['idx'])!=1:return None
 rw=latest(sw[0],rsq[1]['idx'][0],rsq[1]['comps'][0])
 if rw is None or rw[2]!=OP_DP3:return None
 dp=rw[4]
 if len(dp)!=3 or coord.base_sig(dp[1])!=coord.base_sig(dp[2]) or dp[1]['comps'][:3]!=dp[2]['comps'][:3]:return None
 if coord.base_sig(raw)!=coord.base_sig(dp[1]) or re!=dp[1]['comps'][:3]:return None
 return {'normWriter':wi,'raw':raw,'rawComponents':re,'selfDotIndex':rw[0]}

def formula_roles(coord,w,inst,latest,si,p,op):
 O,_=coord.parse_sample(w,p,op);dst,cube,res,sam=O[:4]
 if not(res['type']==TYPE_RESOURCE and sam['type']==TYPE_SAMPLER and res['idx']==[15] and sam['idx']==[15]):return None
 if cube['type']!=TYPE_TEMP or len(cube['idx'])!=1:return None
 logical=cube['comps'][:3];ws=[latest(si,cube['idx'][0],ch) for ch in set(logical)]
 if any(x is None for x in ws) or len({x[0] for x in ws})!=1:return None
 mi,mp,mop,md,M=ws[0]
 if mop!=OP_MAD or len(M)!=4:return None
 mdst,ma,neg2,mb=M
 if neg2['type']!=TYPE_TEMP or neg2['modifier']!='neg' or len(set(neg2['comps'][:3]))!=1:return None
 aw=latest(mi,neg2['idx'][0],neg2['comps'][0])
 if aw is None or aw[2]!=OP_ADD:return None
 add=aw[4]
 if len(add)!=3:return None
 s1,s2=add[1:]
 sig=lambda x:(x['type'],tuple(x['idx']),x['comps'],x['modifier'])
 if sig(s1)!=sig(s2) or s1['type']!=TYPE_TEMP:return None
 dw=latest(aw[0],s1['idx'][0],s1['comps'][0])
 if dw is None or dw[2]!=OP_DP3:return None
 dot=dw[4];d1,d2=dot[1],dot[2]
 def pick(m):
  if coord.base_sig(d1)==coord.base_sig(m):return d1
  if coord.base_sig(d2)==coord.base_sig(m):return d2
  return None
 A=pick(ma);B=pick(mb)
 if A is None or B is None or coord.base_sig(A)==coord.base_sig(B):return None
 return {'A':A,'B':B,'dotIndex':dw[0],'coordMadIndex':mi}

def scalar_leaves(coord,mip,weight,angular,sem,guard,w,inst,parsed,resources,latest,src,before,dst):
 if src['type']!=TYPE_TEMP or len(src['idx'])!=1:return set()
 try:ch=effective(coord,src,dst)[0]
 except ValueError:return set()
 return sem.sample_leaves(coord,mip,weight,angular,guard,w,inst,parsed,resources,latest,src['idx'][0],ch,before,{})

def prove_surface_normal(coord,mip,weight,angular,sem,guard,w,inst,parsed,resources,latest,sig,roles):
 A=normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);B=normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
 if A is None or B is None:return None
 if B['raw']['type']!=TYPE_INPUT or len(B['raw']['idx'])!=1 or sig.get(B['raw']['idx'][0])!=('TEXCOORD',5) or B['rawComponents']!='xyz':return None
 raw=A['raw']
 if raw['type']!=TYPE_TEMP or len(raw['idx'])!=1:return None
 ws=[latest(A['normWriter'],raw['idx'][0],ch) for ch in set(A['rawComponents'])]
 if any(x is None for x in ws) or len({x[0] for x in ws})!=1:return None
 yi,yp,yop,yd,Y=ws[0]
 if yop!=OP_MAD or len(Y)!=4:return None
 ydst,ya,yb,ybase=Y
 if replicated(coord,ya,ydst['comps']) and input_vec(coord,yb,ydst['comps'],sig,2):Ny=ya
 elif replicated(coord,yb,ydst['comps']) and input_vec(coord,ya,ydst['comps'],sig,2):Ny=yb
 else:return None
 if ybase['type']!=TYPE_TEMP or len(ybase['idx'])!=1:return None
 try:be=effective(coord,ybase,ydst['comps'])
 except ValueError:return None
 bws=[latest(yi,ybase['idx'][0],ch) for ch in set(be)]
 if any(x is None for x in bws) or len({x[0] for x in bws})!=1:return None
 xi,xp,xop,xd,X=bws[0]
 if xop!=OP_MAD or len(X)!=4:return None
 xdst,xa,xb,xbase=X
 if replicated(coord,xa,xdst['comps']) and input_vec(coord,xb,xdst['comps'],sig,3):Nx=xa
 elif replicated(coord,xb,xdst['comps']) and input_vec(coord,xa,xdst['comps'],sig,3):Nx=xb
 else:return None
 if not input_vec(coord,xbase,xdst['comps'],sig,1):return None
 lx=scalar_leaves(coord,mip,weight,angular,sem,guard,w,inst,parsed,resources,latest,Nx,xi,xdst['comps'])
 ly=scalar_leaves(coord,mip,weight,angular,sem,guard,w,inst,parsed,resources,latest,Ny,yi,ydst['comps'])
 nx=[z for z in lx if 'normal' in z[1].lower()];ny=[z for z in ly if 'normal' in z[1].lower()]
 if not nx or not ny:return None
 if any(z[3] not in ('x','y') for z in nx+ny):raise ValueError('normal-named sample ancestry uses non-XY channel')
 return {'normalXLeaves':lx,'normalYLeaves':ly,'normalXNamedLeaves':nx,'normalYNamedLeaves':ny}

def build(root:Path,coordinate_verifier:Path,mip_verifier:Path,weight_verifier:Path,angular_verifier:Path,semantic_verifier:Path,shared_verifier:Path,guard_path:Path):
 coord=load(coordinate_verifier,'coord');mip=load(mip_verifier,'mip');weight=load(weight_verifier,'weight');angular=load(angular_verifier,'angular');sem=load(semantic_verifier,'sem');shared=load(shared_verifier,'shared');guard=load(guard_path,'guard')
 all_ref={};maps=[]
 for mn,(rel,sha) in guard.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=sha:raise ValueError(f'{mn}: expanded SHA mismatch {actual}')
  valid,_=guard.scan_map(path);n=0
  for hh,(blob,res) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in res):
    n+=1;old=all_ref.setdefault(hh,(blob,res,set()))
    if old[0]!=blob:raise ValueError('reflection shader SHA collision')
    old[2].add(mn)
  maps.append({'map':mn,'validDxbcCount':len(valid),'reflectionProbeShaderCount':n})
 if len(all_ref)!=EXPECTED_SHADERS:raise ValueError(f'reflection shader count {len(all_ref)}')
 total=target=0;formula_patterns=collections.Counter();normal_resources=collections.Counter();control_resources=collections.Counter();rows=[]
 for hh,(blob,resources,mapnames) in sorted(all_ref.items()):
  sig=input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,coord_latest=shared.prep_shader(coord,weight,w,inst);local=0
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);res,sam=O[2],O[3]
   if not(res['type']==TYPE_RESOURCE and sam['type']==TYPE_SAMPLER and res['idx']==[15] and sam['idx']==[15]):continue
   total+=1;roles=formula_roles(coord,w,inst,latest,si,p,op)
   if roles is None:raise ValueError(f'{hh}:{si}: reflect formula role mapping failed')
   A=normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);B=normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
   def rawclass(z):
    if z is None:return 'unresolved'
    r=z['raw']
    if r['type']==TYPE_INPUT and len(r['idx'])==1:
     ss=sig.get(r['idx'][0]);return f'{ss[0]}{ss[1]}.{z["rawComponents"]}' if ss else f'INPUT{r["idx"][0]}.{z["rawComponents"]}'
    if r['type']==TYPE_TEMP:
     ws=[latest(z['normWriter'],r['idx'][0],ch) for ch in set(z['rawComponents'])]
     opn=ws[0][2] if all(ws) and len({x[0] for x in ws})==1 else -1
     return f'TEMP_OP{opn}'
    return f'TYPE{r["type"]}'
   formula_patterns[(rawclass(A),rawclass(B))]+=1
   q=prove_surface_normal(coord,mip,weight,angular,sem,guard,w,inst,parsed,resources,latest,sig,roles)
   if q is None:continue
   target+=1;local+=1
   for z in q['normalXNamedLeaves']+q['normalYNamedLeaves']:normal_resources[(z[1],z[2],z[3],z[4])]+=1
   for z in q['normalXLeaves']|q['normalYLeaves']:
    if 'normal' not in z[1].lower():control_resources[(z[1],z[2],z[3],z[4])]+=1
  if local:rows.append({'sha256':hh,'maps':sorted(mapnames),'surfaceNormalReflectionFetchCount':local})
 if total!=EXPECTED_FETCHES:raise ValueError(f'reflection fetch count {total}')
 if target!=EXPECTED_TARGET:raise ValueError(f'surface-normal target count {target}')
 expected_pair=('TEMP_OP50','TEXCOORD5.xyz')
 if formula_patterns[expected_pair]!=EXPECTED_TARGET:raise ValueError(f'formula-role target count {formula_patterns[expected_pair]}')
 nr=[{'resourceName':k[0],'resourceRegister':k[1],'channel':k[2],'opcode':k[3],'ancestryOccurrenceCount':v} for k,v in sorted(normal_resources.items())]
 cr=[{'resourceName':k[0],'resourceRegister':k[1],'channel':k[2],'opcode':k[3],'ancestryOccurrenceCount':v} for k,v in sorted(control_resources.items())]
 fr=[{'formulaA':k[0],'formulaB':k[1],'count':v} for k,v in sorted(formula_patterns.items())]
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':len(all_ref),'reflectionCubeFetchCount':total,'surfaceNormalRoleFetchCount':target,'surfaceNormalRoleFailureCount':0,'surfaceNormalBasisCheckCount':target,'normalNamedXAncestryCheckCount':target,'normalNamedYAncestryCheckCount':target,'texcoord5OpposingVectorCheckCount':target,'formulaRoleRowsSha256':jhash(fr),'normalResourceRowsSha256':jhash(nr),'controlResourceRowsSha256':jhash(cr),'shaderRowsSha256':jhash(rows)}
 return {'format':'t6-retail-reflection-probe-surface-normal-v1','producer':'tools/t6_retail_reflection_probe_surface_normal_v1.py','sources':{'coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json','materialSemanticProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_MATERIAL_SEMANTICS_V1.json','expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in guard.SOURCES.items()}},'equation':{'cubeCoord':'viewCandidate - 2 * surfaceNormal * dot(surfaceNormal, viewCandidate)','surfaceNormalRaw':'TEXCOORD1.xyz + normalX * TEXCOORD3.xyz + normalY * TEXCOORD2.xyz','surfaceNormal':'surfaceNormalRaw * rsq(dot(surfaceNormalRaw,surfaceNormalRaw))','viewCandidate':'normalize(TEXCOORD5.xyz)'},'formulaRolePatterns':fr,'normalNamedResourceAncestry':nr,'nonNormalControlResourceAncestry':cr,'mapCoverage':maps,'summary':summary,'proofBoundary':'Direct retained-DXBC/RDEF role proof for the 4,086 reflectionProbeSampler fetches whose formula-A raw vector exactly matches TEXCOORD1.xyz + Nx*TEXCOORD3.xyz + Ny*TEXCOORD2.xyz and whose Nx/Ny value ancestry each reaches at least one normal-named reflected texture resource. Formula-B in all 4,086 is independently normalized ISGN TEXCOORD5.xyz. This promotes formula A to a normal-map-derived surface-normal path for this proven subset and rewrites the reflect equation accordingly. TEXCOORD5 remains viewCandidate: this stage does not yet prove its vertex-shader/camera-space provenance, and it does not assign surface-normal semantics to the remaining 1,802 reflection fetches.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'));ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'));ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'));ap.add_argument('--semantic-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_semantics_v1.py'));ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.semantic_verifier,a.shared_verifier,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
