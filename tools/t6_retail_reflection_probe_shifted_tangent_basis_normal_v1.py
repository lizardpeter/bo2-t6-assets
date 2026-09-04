#!/usr/bin/env python3
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def configure(closure_path,tangent_path,coordinate_path,weight_path,shared_path,surface_path,guard_path,mip_path,angular_path,semantic_path):
 C=load(closure_path,'closure');T,coord,weight,shared,surf,guard,mip,angular,sem=C.configure(tangent_path,coordinate_path,weight_path,shared_path,surface_path,guard_path,mip_path,angular_path,semantic_path)
 return C,T,coord,weight,shared,surf,guard,mip,angular,sem

def match(C,T,coord,weight,shared,surf,guard,mip,angular,sem,blob,res,si,p,op):
 sig=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst)
 roles=surf.formula_roles(coord,w,inst,latest,si,p,op);A=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);Opp=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
 if not A or not Opp:return None
 if not(Opp['raw']['type']==1 and sig.get(Opp['raw']['idx'][0])==('TEXCOORD',0) and Opp['rawComponents']=='xyz'):return None
 rw=T.latest_same(latest,A['normWriter'],A['raw'],A['rawComponents'])
 if rw is None or rw[2]!=T.OP_MAD:return None
 yi,yp,yop,yd,Y=rw;cand=[]
 for ny,bn,prev in ((Y[1],Y[2],Y[3]),(Y[2],Y[1],Y[3])):
  if T.replicated(ny,yd['comps']) and bn['type']==0 and prev['type']==0:cand.append((ny,bn,prev))
 if len(cand)!=1:return None
 Ny,bn,prev=cand[0];pw=T.latest_same(latest,yi,prev,yd['comps'])
 if pw is None or pw[2]!=T.OP_MAD:return None
 xi,xp,xop,xd,X=pw;cand=[]
 for nx,tan,base in ((X[1],X[2],X[3]),(X[2],X[1],X[3])):
  if T.replicated(nx,xd['comps']) and tan['type']==1 and base['type']==0:cand.append((nx,tan,base))
 if len(cand)!=1:return None
 Nx,Tan,base=cand[0]
 if len(Tan['idx'])!=1:return None
 tsem=sig.get(Tan['idx'][0]);
 if not tsem or tsem[0]!='TEXCOORD' or coord.effective_for_dest(Tan,xd['comps'])!='xyz':return None
 base_norm=surf.normalized_raw(coord,w,inst,latest,xi,base)
 if not base_norm or base_norm['raw']['type']!=1 or len(base_norm['raw']['idx'])!=1 or base_norm['rawComponents']!='xyz':return None
 bsem=sig.get(base_norm['raw']['idx'][0]);
 if not bsem or bsem[0]!='TEXCOORD':return None
 cross=C.cross_match_flexible(T,coord,latest,yi,bn,yd['comps'],base,Tan)
 if not cross or cross['packing']!='xyz':return None
 sw=T.latest_same(latest,yi,bn,yd['comps']);S=sw[4];scalar=None
 for z in S[1:]:
  if z['type']==1 and len(z.get('idx',[]))==1:scalar=z
 if scalar is None or sig.get(scalar['idx'][0])!=tsem:return None
 try:se=coord.effective_for_dest(scalar,sw[3]['comps'])
 except:return None
 if len(se)!=len(sw[3]['comps']) or set(se)!={'w'}:return None
 lx=T.leaves(w,inst,parsed,res,latest,Nx,xi,xd['comps']);ly=T.leaves(w,inst,parsed,res,latest,Ny,yi,yd['comps'])
 xl=sorted({(z[1],z[2],z[3],z[4]) for z in lx});yl=sorted({(z[1],z[2],z[3],z[4]) for z in ly})
 if xl!=[('NormalMap',0,'x','SAMPLE')] or yl!=[('NormalMap',0,'y','SAMPLE')]:return None
 return {'baseSemantic':f'TEXCOORD{bsem[1]}','tangentSemantic':f'TEXCOORD{tsem[1]}','packing':'xyz','xLeaves':xl,'yLeaves':yl}

def build(root,closure_path,tangent_path,coordinate_path,weight_path,shared_path,surface_path,guard_path,mip_path,angular_path,semantic_path):
 C,T,coord,weight,shared,surf,guard,mip,angular,sem=configure(closure_path,tangent_path,coordinate_path,weight_path,shared_path,surface_path,guard_path,mip_path,angular_path,semantic_path)
 allref={}
 for mn,(rel,sha) in guard.SOURCES.items():
  path=root/rel
  if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError(f'{mn}: source mismatch')
  valid,_=guard.scan_map(path)
  for hh,(blob,res) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in res):allref.setdefault(hh,(blob,res,set()))[2].add(mn)
 rows=[];patterns=collections.Counter();target=0
 for hh,(blob,res,maps) in sorted(allref.items()):
  sig=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst)
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);rr,ss=O[2],O[3]
   if not(rr['type']==7 and ss['type']==6 and rr['idx']==[15] and ss['idx']==[15]):continue
   roles=surf.formula_roles(coord,w,inst,latest,si,p,op);A=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);B=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
   if (C.raw_class(T,coord,surf,sig,latest,A),C.raw_class(T,coord,surf,sig,latest,B))!=('TEMP_OP50','TEXCOORD0.xyz'):continue
   target+=1;q=match(C,T,coord,weight,shared,surf,guard,mip,angular,sem,blob,res,si,p,op)
   if not q:raise ValueError(f'{hh}:{si}: shifted TBN mismatch')
   pat=(q['baseSemantic'],q['tangentSemantic']);patterns[pat]+=1
   rows.append({'sha256':hh,'maps':sorted(maps),'sampleInstructionIndex':si,**q})
 expected={('TEXCOORD1','TEXCOORD2'):12,('TEXCOORD2','TEXCOORD3'):12}
 if target!=24 or dict(patterns)!=expected:raise ValueError(f'target/pattern mismatch {target} {patterns}')
 summary={'uniqueReflectionProbeShaderCount':len(allref),'targetShaderCount':24,'targetFetchCount':24,'unclassifiedCount':0,
          'baseTangentPatternCounts':{f'{a}/{b}':n for (a,b),n in sorted(patterns.items())},'shaderRowsSha256':jhash(rows),'patternRowsSha256':jhash(sorted((list(k),v) for k,v in patterns.items()))}
 return {'format':'t6-retail-reflection-probe-shifted-tangent-basis-normal-v1','producer':'tools/t6_retail_reflection_probe_shifted_tangent_basis_normal_v1.py','sources':{'coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json','tempMadClosure':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEMP_MAD_TEXCOORD1_CLOSURE_ARCHIVE_V1.json'},'equations':{'surfaceNormal':'N=normalize(normalize(base)+NormalMap.x*tangent+NormalMap.y*(cross(normalize(base),tangent)*tangent.w))','reflection':'cubeCoord=normalize(TEXCOORD0)-2*N*dot(N,normalize(TEXCOORD0))'},'examples':rows[:3],'summary':summary,'proofBoundary':'Exhaustive retained-DXBC/RDEF proof for all 24 reflectionProbeSampler fetches whose reflect operands are a MAD-produced normalized vector against normalized TEXCOORD0.xyz. All 24 implement the same NormalMap.x/y tangent-basis surface-normal reconstruction, split evenly between base/tangent semantic pairs TEXCOORD1/TEXCOORD2 and TEXCOORD2/TEXCOORD3. Zero remain unclassified. Physical vertex semantics of those basis interpolators and camera/view semantics of TEXCOORD0 remain separate.'}

def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--closure-verifier',type=Path,required=True);a.add_argument('--tangent-verifier',type=Path,required=True);a.add_argument('--coordinate-verifier',type=Path,required=True);a.add_argument('--weight-verifier',type=Path,required=True);a.add_argument('--shared-verifier',type=Path,required=True);a.add_argument('--surface-verifier',type=Path,required=True);a.add_argument('--guard',type=Path,required=True);a.add_argument('--mip-verifier',type=Path,required=True);a.add_argument('--angular-verifier',type=Path,required=True);a.add_argument('--semantic-verifier',type=Path,required=True);a.add_argument('--out',type=Path,required=True);q=a.parse_args();d=build(q.root,q.closure_verifier,q.tangent_verifier,q.coordinate_verifier,q.weight_verifier,q.shared_verifier,q.surface_verifier,q.guard,q.mip_verifier,q.angular_verifier,q.semantic_verifier);q.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
