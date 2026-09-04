#!/usr/bin/env python3
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path

def load(p:Path,n:str):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def configure(tangent_path,coordinate_path,weight_path,shared_path,surface_path,guard_path,mip_path,angular_path,semantic_path):
 T=load(tangent_path,'tangent');T.configure(coordinate_path,weight_path,shared_path,surface_path,guard_path,mip_path,angular_path,semantic_path)
 return T,T.coord,T.weight,T.shared,T.surf,T.guard,T.mip,T.angular,T.sem

def samebase(coord,a,b):return coord.base_sig(a)==coord.base_sig(b)
def eff(coord,o,dst):
 try:return coord.effective_for_dest(o,dst)
 except:return None

def term_ok(coord,a,b,dest,A,B,pa,pb):
 return ((samebase(coord,a,A) and samebase(coord,b,B) and eff(coord,a,dest)==pa and eff(coord,b,dest)==pb) or
         (samebase(coord,b,A) and samebase(coord,a,B) and eff(coord,b,dest)==pa and eff(coord,a,dest)==pb))

def cross_match_flexible(T,coord,latest,before,vec,dst,N,Tan):
 wr=T.latest_same(latest,before,vec,dst)
 if wr is None or wr[2]!=T.OP_MUL:return None
 wi,wp,wop,wd,W=wr
 if len(W)!=3:return None
 cand=[]
 for scalar,cross in ((W[1],W[2]),(W[2],W[1])):
  if T.scalar_sem(scalar,wd['comps'],surf.input_signature_current if False else {},4,'w'):pass
 pairs=[]
 for scalar,cross in ((W[1],W[2]),(W[2],W[1])):
  if scalar['type']==1 and cross['type']==0 and len(scalar.get('idx',[]))==1:pairs.append((scalar,cross))
 if len(pairs)!=1:return None
 scalar,cross=pairs[0]
 try:se=coord.effective_for_dest(scalar,wd['comps'])
 except:return None
 if len(se)!=len(wd['comps']) or set(se)!={'w'}:return None
 cw=T.latest_same(latest,wi,cross,wd['comps'])
 if cw is None or cw[2]!=T.OP_MAD:return None
 ci,cp,cop,cd,C=cw
 if len(C)!=4:return None
 ca,cb,cc=C[1:]
 if cc['type']!=0 or cc.get('modifier')!='neg':return None
 mw=T.latest_same(latest,ci,cc,cd['comps'])
 if mw is None or mw[2]!=T.OP_MUL:return None
 mi,mp,mop,md,M=mw
 if len(M)!=3:return None
 if term_ok(coord,ca,cb,cd['comps'],N,Tan,'yzx','zxy') and term_ok(coord,M[1],M[2],md['comps'],N,Tan,'zxy','yzx'):
  return {'signMulIndex':wi,'crossMadIndex':ci,'crossMulIndex':mi,'packing':'xyz'}
 def raw_pair(a,b,Npat,Tpat):
  return ((samebase(coord,a,N) and samebase(coord,b,Tan) and a.get('comps')==Npat and b.get('comps')==Tpat) or
          (samebase(coord,b,N) and samebase(coord,a,Tan) and b.get('comps')==Npat and a.get('comps')==Tpat))
 if raw_pair(ca,cb,'zwyz','zxyz') and raw_pair(M[1],M[2],'wyzw','yzxy'):
  return {'signMulIndex':wi,'crossMadIndex':ci,'crossMulIndex':mi,'packing':'yzw'}
 return None

def tbn_math(T,coord,weight,shared,surf,guard,mip,angular,sem,blob,res,si,p,op):
 sig=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst)
 roles=surf.formula_roles(coord,w,inst,latest,si,p,op)
 if not roles:return None
 A=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);Opp=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
 if not A or not Opp:return None
 if not(Opp['raw']['type']==1 and sig.get(Opp['raw']['idx'][0])==('TEXCOORD',1) and Opp['rawComponents']=='xyz'):return None
 rw=T.latest_same(latest,A['normWriter'],A['raw'],A['rawComponents'])
 if rw is None or rw[2]!=T.OP_MAD:return None
 yi,yp,yop,yd,Y=rw
 if len(Y)!=4:return None
 cand=[]
 for ny,bn,prev in ((Y[1],Y[2],Y[3]),(Y[2],Y[1],Y[3])):
  if T.replicated(ny,yd['comps']) and bn['type']==0 and prev['type']==0:cand.append((ny,bn,prev))
 if len(cand)!=1:return None
 Ny,bn,prev=cand[0]
 pw=T.latest_same(latest,yi,prev,yd['comps'])
 if pw is None or pw[2]!=T.OP_MAD:return None
 xi,xp,xop,xd,X=pw
 if len(X)!=4:return None
 cand=[]
 for nx,tan,base in ((X[1],X[2],X[3]),(X[2],X[1],X[3])):
  if T.replicated(nx,xd['comps']) and tan['type']==1 and base['type']==0:cand.append((nx,tan,base))
 if len(cand)!=1:return None
 Nx,Tan,base=cand[0]
 if not T.input_vec(Tan,xd['comps'],sig,4,'xyz'):return None
 base_norm=surf.normalized_raw(coord,w,inst,latest,xi,base)
 if not base_norm or base_norm['raw']['type']!=1 or sig.get(base_norm['raw']['idx'][0])!=('TEXCOORD',3) or base_norm['rawComponents']!='xyz':return None
 cross=cross_match_flexible(T,coord,latest,yi,bn,yd['comps'],base,Tan)
 if not cross:return None
 lx=T.leaves(w,inst,parsed,res,latest,Nx,xi,xd['comps']);ly=T.leaves(w,inst,parsed,res,latest,Ny,yi,yd['comps'])
 return {'A':A,'Opp':Opp,'Nx':Nx,'Ny':Ny,'lx':lx,'ly':ly,'baseNorm':base_norm,'cross':cross,
         'madXIndex':xi,'madYIndex':yi}

def water_cross(T,coord,weight,shared,surf,guard,mip,angular,sem,blob,res,si,p,op):
 sig=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst)
 roles=surf.formula_roles(coord,w,inst,latest,si,p,op)
 if not roles:return None
 A=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);Opp=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
 if not A or not Opp:return None
 if not(Opp['raw']['type']==1 and sig.get(Opp['raw']['idx'][0])==('TEXCOORD',1) and Opp['rawComponents']=='xyz'):return None
 rw=T.latest_same(latest,A['normWriter'],A['raw'],A['rawComponents'])
 if rw is None or rw[2]!=T.OP_MAD:return None
 yi,yp,yop,yd,Y=rw
 cand=[]
 if len(Y)!=4:return None
 for ny,basis2,prev in ((Y[1],Y[2],Y[3]),(Y[2],Y[1],Y[3])):
  if T.replicated(ny,yd['comps']) and basis2['type']==1 and prev['type']==0:cand.append((ny,basis2,prev))
 if len(cand)!=1:return None
 Ny,BasisB,prev=cand[0]
 pw=T.latest_same(latest,yi,prev,yd['comps'])
 if pw is None or pw[2]!=T.OP_MAD:return None
 xi,xp,xop,xd,X=pw;cand=[]
 if len(X)!=4:return None
 for nx,basis1,cross in ((X[1],X[2],X[3]),(X[2],X[1],X[3])):
  if T.replicated(nx,xd['comps']) and basis1['type']==1 and cross['type']==0:cand.append((nx,basis1,cross))
 if len(cand)!=1:return None
 Nx,BasisT,cross=cand[0]
 if not T.input_vec(BasisT,xd['comps'],sig,4,'xyz') or not T.input_vec(BasisB,yd['comps'],sig,5,'xyz'):return None
 cw=T.latest_same(latest,xi,cross,xd['comps'])
 if cw is None or cw[2]!=T.OP_MAD:return None
 ci,cp,cop,cd,C=cw
 if len(C)!=4 or C[3]['type']!=0 or C[3].get('modifier')!='neg':return None
 mw=T.latest_same(latest,ci,C[3],cd['comps'])
 if mw is None or mw[2]!=T.OP_MUL:return None
 M=mw[4]
 if len(M)!=3:return None
 if not term_ok(coord,C[1],C[2],cd['comps'],BasisT,BasisB,'yzx','zxy'):return None
 if not term_ok(coord,M[1],M[2],M[0]['comps'],BasisT,BasisB,'zxy','yzx'):return None
 lx=T.leaves(w,inst,parsed,res,latest,Nx,xi,xd['comps']);ly=T.leaves(w,inst,parsed,res,latest,Ny,yi,yd['comps'])
 nxn=[z for z in lx if 'normal' in z[1].lower()];nyn=[z for z in ly if 'normal' in z[1].lower()]
 if not nxn or not nyn:return None
 return {'A':A,'Opp':Opp,'Nx':Nx,'Ny':Ny,'lx':lx,'ly':ly,'crossMadIndex':ci,'crossMulIndex':mw[0],'madXIndex':xi,'madYIndex':yi}

def raw_class(T,coord,surf,sig,latest,z):
 r=z['raw']
 if r['type']==1:
  ss=sig.get(r['idx'][0]);return f'{ss[0]}{ss[1]}.{z["rawComponents"]}' if ss else f'INPUT{r["idx"][0]}.{z["rawComponents"]}'
 if r['type']==0:
  ws=[latest(z['normWriter'],r['idx'][0],ch) for ch in set(z['rawComponents'])]
  opn=ws[0][2] if all(ws) and len({x[0] for x in ws})==1 else -1
  return f'TEMP_OP{opn}'
 return f'TYPE{r["type"]}'

def build(root,tangent_path,coordinate_path,weight_path,shared_path,surface_path,guard_path,mip_path,angular_path,semantic_path):
 T,coord,weight,shared,surf,guard,mip,angular,sem=configure(tangent_path,coordinate_path,weight_path,shared_path,surface_path,guard_path,mip_path,angular_path,semantic_path)
 allref={}
 for mn,(rel,sha) in guard.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=sha:raise ValueError(f'{mn}: source mismatch')
  valid,_=guard.scan_map(path)
  for hh,(blob,res) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in res):
    q=allref.setdefault(hh,(blob,res,set()));q[2].add(mn)
 if len(allref)!=5868:raise ValueError('reflection shader count')
 rows=[];classes=collections.Counter();packing=collections.Counter();resource_roles=collections.Counter();target=0
 for hh,(blob,res,maps) in sorted(allref.items()):
  sig=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst)
  hits=0
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);rr,ss=O[2],O[3]
   if not(rr['type']==7 and ss['type']==6 and rr['idx']==[15] and ss['idx']==[15]):continue
   roles=surf.formula_roles(coord,w,inst,latest,si,p,op)
   if not roles:raise ValueError(f'{hh}: formula roles')
   A=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);Opp=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
   if not A or not Opp:raise ValueError(f'{hh}: normalized operands')
   if (raw_class(T,coord,surf,sig,latest,A),raw_class(T,coord,surf,sig,latest,Opp))!=('TEMP_OP50','TEXCOORD1.xyz'):continue
   target+=1;hits+=1
   q0=T.match(blob,res,si,p,op)
   cls=None;meta={}
   if q0:
    cls='normalNamedTangentBasis';packing['xyz']+=1
    meta={'packing':'xyz','xLeaves':sorted({(z[1],z[2],z[3],z[4]) for z in q0['lx']}),'yLeaves':sorted({(z[1],z[2],z[3],z[4]) for z in q0['ly']})}
   else:
    q=tbn_math(T,coord,weight,shared,surf,guard,mip,angular,sem,blob,res,si,p,op)
    if q:
     xn=[z for z in q['lx'] if 'normal' in z[1].lower()];yn=[z for z in q['ly'] if 'normal' in z[1].lower()]
     if xn and yn:cls='normalNamedTangentBasis'
     else:
      xl=sorted({(z[1],z[2],z[3],z[4]) for z in q['lx']});yl=sorted({(z[1],z[2],z[3],z[4]) for z in q['ly']})
      if xl and yl and all(z[0]=='Camo_Detail_Map' for z in xl+yl):cls='camoDetailTangentBasis'
      else:raise ValueError(f'{hh}: unclassified TBN leaves {xl} {yl}')
     packing[q['cross']['packing']]+=1
     meta={'packing':q['cross']['packing'],'xLeaves':sorted({(z[1],z[2],z[3],z[4]) for z in q['lx']}),'yLeaves':sorted({(z[1],z[2],z[3],z[4]) for z in q['ly']})}
    else:
     q=water_cross(T,coord,weight,shared,surf,guard,mip,angular,sem,blob,res,si,p,op)
     if q:
      cls='waterCrossBasis';meta={'xLeaves':sorted({(z[1],z[2],z[3],z[4]) for z in q['lx']}),'yLeaves':sorted({(z[1],z[2],z[3],z[4]) for z in q['ly']})}
     else:raise ValueError(f'{hh}:{si}: 995-family residual unclassified')
   classes[cls]+=1
   for role,ls in [('x',meta['xLeaves']),('y',meta['yLeaves'])]:
    for z in ls:resource_roles[(cls,role)+tuple(z)]+=1
   rows.append({'sha256':hh,'maps':sorted(maps),'sampleInstructionIndex':si,'class':cls,**meta})
  if hits>1:raise ValueError(f'{hh}: multiple target fetches')
 if target!=995 or classes!={'normalNamedTangentBasis':964,'camoDetailTangentBasis':20,'waterCrossBasis':11}:raise ValueError(f'closure counts target={target} classes={classes}')
 rr=[{'class':k[0],'coefficient':k[1],'resourceName':k[2],'resourceRegister':k[3],'channel':k[4],'opcode':k[5],'shaderAncestryCount':v} for k,v in sorted(resource_roles.items())]
 summary={'uniqueReflectionProbeShaderCount':len(allref),'targetTempMadTexcoord1ShaderCount':target,
          'normalNamedTangentBasisShaderCount':classes['normalNamedTangentBasis'],
          'camoDetailTangentBasisShaderCount':classes['camoDetailTangentBasis'],
          'waterCrossBasisShaderCount':classes['waterCrossBasis'],'unclassifiedShaderCount':0,
          'xyzCrossPackingShaderCount':packing['xyz'],'yzwCrossPackingShaderCount':packing['yzw'],
          'shaderRowsSha256':jhash(rows),'resourceRoleRowsSha256':jhash(rr),'classCountsSha256':jhash(sorted(classes.items()))}
 return {'format':'t6-retail-reflection-probe-temp-mad-texcoord1-closure-v1','producer':'tools/t6_retail_reflection_probe_temp_mad_texcoord1_closure_v1.py',
         'sources':{'tangentBasisProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TANGENT_BASIS_NORMAL_ARCHIVE_V1.json','coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json'},
         'equations':{'tangentBasis':'N=normalize(normalize(TEXCOORD3)+x*TEXCOORD4.xyz+y*(cross(normalize(TEXCOORD3),TEXCOORD4.xyz)*TEXCOORD4.w))',
                      'waterCrossBasis':'N=normalize(cross(TEXCOORD4.xyz,TEXCOORD5.xyz)+x*TEXCOORD4.xyz+y*TEXCOORD5.xyz)',
                      'reflection':'cubeCoord=normalize(TEXCOORD1)-2*N*dot(N,normalize(TEXCOORD1))'},
         'classSemantics':{'normalNamedTangentBasis':'x/y reach normal-named reflected texture resources','camoDetailTangentBasis':'same exact TBN normal equation; x/y reach Camo_Detail_Map channels','waterCrossBasis':'cross(TEXCOORD4,TEXCOORD5) base with x/y reaching normalMap00/normalMap01'},
         'resourceRoleRows':rr,'examples':{c:[r for r in rows if r['class']==c][:2] for c in sorted(classes)},'summary':summary,
         'proofBoundary':'Exhaustive retained-DXBC closure of all 995 unique reflectionProbeSampler shaders whose coordinate formula uses a MAD-produced normalized operand against normalized TEXCOORD1.xyz. Exactly 964 use a normal-named texture-driven tangent-basis reconstruction, including seven equivalent yzw-packed cross-product encodings; 20 use the identical tangent-basis reconstruction with perturbation coefficients sourced from Camo_Detail_Map.x/y; 11 use a distinct water cross-basis reconstruction with coefficients reaching normalMap00/normalMap01. Zero shaders remain unclassified. This proves formula-A is a reconstructed surface-orientation/normal vector by arithmetic role for all 995. Physical vertex semantics of TEXCOORD3/4/5 and camera/view semantics of opposing TEXCOORD1 remain separate except where independently proven by other pass/VS artifacts.'}

def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--tangent-verifier',type=Path,required=True);a.add_argument('--coordinate-verifier',type=Path,required=True);a.add_argument('--weight-verifier',type=Path,required=True);a.add_argument('--shared-verifier',type=Path,required=True);a.add_argument('--surface-verifier',type=Path,required=True);a.add_argument('--guard',type=Path,required=True);a.add_argument('--mip-verifier',type=Path,required=True);a.add_argument('--angular-verifier',type=Path,required=True);a.add_argument('--semantic-verifier',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
 q=a.parse_args();d=build(q.root,q.tangent_verifier,q.coordinate_verifier,q.weight_verifier,q.shared_verifier,q.surface_verifier,q.guard,q.mip_verifier,q.angular_verifier,q.semantic_verifier);q.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
