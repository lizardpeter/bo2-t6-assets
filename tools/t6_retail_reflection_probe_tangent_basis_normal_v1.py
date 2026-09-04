from pathlib import Path
import argparse,json
import importlib.util,hashlib,collections

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
coord=weight=shared=surf=guard=mip=angular=sem=None

def configure(coordinate_verifier,weight_verifier,shared_verifier,surface_verifier,guard_path,mip_verifier,angular_verifier,semantic_verifier):
 global coord,weight,shared,surf,guard,mip,angular,sem
 coord=load(coordinate_verifier,'coord');weight=load(weight_verifier,'weight');shared=load(shared_verifier,'shared');surf=load(surface_verifier,'surf');guard=load(guard_path,'guard');mip=load(mip_verifier,'mip');angular=load(angular_verifier,'angular');sem=load(semantic_verifier,'sem')

OP_MAD=50;OP_MUL=56

def input_vec(src,dst,sig,idx,comps='xyz'):
 if src['type']!=1 or len(src['idx'])!=1 or sig.get(src['idx'][0])!=('TEXCOORD',idx):return False
 try:e=coord.effective_for_dest(src,dst)
 except:return False
 return e==comps

def replicated(src,dst):
 try:e=coord.effective_for_dest(src,dst)
 except:return False
 return len(e)==len(dst) and len(set(e))==1

def scalar_sem(src,dst,sig,idx,ch):
 if src['type']!=1 or len(src['idx'])!=1 or sig.get(src['idx'][0])!=('TEXCOORD',idx):return False
 try:e=coord.effective_for_dest(src,dst)
 except:return False
 return len(e)==len(dst) and set(e)=={ch}

def latest_same(latest,before,opnd,dst):
 if opnd['type']!=0 or len(opnd['idx'])!=1:return None
 try:e=coord.effective_for_dest(opnd,dst)
 except:return None
 ws=[latest(before,opnd['idx'][0],ch) for ch in set(e)]
 return ws[0] if all(ws) and len({x[0] for x in ws})==1 else None

def match_cross(w,inst,latest,sig,before,vec,dst,base_norm,tangent):
 wr=latest_same(latest,before,vec,dst)
 if wr is None or wr[2]!=OP_MUL:return None
 wi,p,op,d,O=wr
 if len(O)!=3:return None
 a,b=O[1:]
 cand=[]
 for scalar,cross in ((a,b),(b,a)):
  if scalar_sem(scalar,d['comps'],sig,4,'w') and cross['type']==0:cand.append(cross)
 if len(cand)!=1:return None
 cross=cand[0];cw=latest_same(latest,wi,cross,d['comps'])
 if cw is None or cw[2]!=OP_MAD:return None
 ci,cp,cop,cd,C=cw
 if len(C)!=4:return None
 ca,cb,cc=C[1:]
 if cc['type']!=0 or cc.get('modifier')!='neg':return None
 mw=latest_same(latest,ci,cc,cd['comps'])
 if mw is None or mw[2]!=OP_MUL:return None
 mi,mp,mop,md,M=mw
 if len(M)!=3:return None
 def samebase(x,ref):return coord.base_sig(x)==coord.base_sig(ref)
 def eff(x,dst):
  try:return coord.effective_for_dest(x,dst)
  except:return None
 c1,c2=ca,cb;m1,m2=M[1],M[2]
 okc=((samebase(c1,base_norm) and samebase(c2,tangent) and eff(c1,cd['comps'])=='yzx' and eff(c2,cd['comps'])=='zxy') or
      (samebase(c2,base_norm) and samebase(c1,tangent) and eff(c2,cd['comps'])=='yzx' and eff(c1,cd['comps'])=='zxy'))
 okm=((samebase(m1,base_norm) and samebase(m2,tangent) and eff(m1,md['comps'])=='zxy' and eff(m2,md['comps'])=='yzx') or
      (samebase(m2,base_norm) and samebase(m1,tangent) and eff(m2,md['comps'])=='zxy' and eff(m1,md['comps'])=='yzx'))
 return {'signMulIndex':wi,'crossMadIndex':ci,'crossMulIndex':mi} if okc and okm else None

def leaves(w,inst,parsed,res,latest,src,before,dst):
 return surf.scalar_leaves(coord,mip,weight,angular,sem,guard,w,inst,parsed,res,latest,src,before,dst)

def match(blob,res,si,p,op):
 sig=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst)
 roles=surf.formula_roles(coord,w,inst,latest,si,p,op)
 if not roles:return None
 A=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);B=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
 if not A or not B:return None
 if not (B['raw']['type']==1 and sig.get(B['raw']['idx'][0])==('TEXCOORD',1) and B['rawComponents']=='xyz'):return None
 raw=A['raw'];rw=latest_same(latest,A['normWriter'],raw,A['rawComponents'])
 if rw is None or rw[2]!=OP_MAD:return None
 yi,yp,yop,yd,Y=rw
 if len(Y)!=4:return None
 candidates=[]
 for ny,bn,prev in ((Y[1],Y[2],Y[3]),(Y[2],Y[1],Y[3])):
  if replicated(ny,yd['comps']) and bn['type']==0 and prev['type']==0:candidates.append((ny,bn,prev))
 if len(candidates)!=1:return None
 Ny,bn,prev=candidates[0]
 pw=latest_same(latest,yi,prev,yd['comps'])
 if pw is None or pw[2]!=OP_MAD:return None
 xi,xp,xop,xd,X=pw
 if len(X)!=4:return None
 cand=[]
 for nx,tan,base in ((X[1],X[2],X[3]),(X[2],X[1],X[3])):
  if replicated(nx,xd['comps']) and input_vec(tan,xd['comps'],sig,4,'xyz') and base['type']==0:cand.append((nx,tan,base))
 if len(cand)!=1:return None
 Nx,tan,base=cand[0]
 base_norm=surf.normalized_raw(coord,w,inst,latest,xi,base)
 if not base_norm or base_norm['raw']['type']!=1 or sig.get(base_norm['raw']['idx'][0])!=('TEXCOORD',3) or base_norm['rawComponents']!='xyz':return None
 cross=match_cross(w,inst,latest,sig,yi,bn,yd['comps'],base,tan)
 if not cross:return None
 lx=leaves(w,inst,parsed,res,latest,Nx,xi,xd['comps']);ly=leaves(w,inst,parsed,res,latest,Ny,yi,yd['comps'])
 nxn=[z for z in lx if 'normal' in z[1].lower()]; nyn=[z for z in ly if 'normal' in z[1].lower()]
 return {'Nx':Nx,'Ny':Ny,'lx':lx,'ly':ly,'nxn':nxn,'nyn':nyn,'baseNorm':base_norm,'cross':cross,'A':A,'B':B} if nxn and nyn else None

EXPECTED_REFLECTION_SHADERS=5868
EXPECTED_TARGET=995
EXPECTED_STANDARD=958
EXPECTED_ALTERNATE=37

def raw_class(sig,latest,z):
 r=z['raw']
 if r['type']==1:
  ss=sig.get(r['idx'][0]);return f'{ss[0]}{ss[1]}.{z["rawComponents"]}' if ss else f'INPUT{r["idx"][0]}.{z["rawComponents"]}'
 if r['type']==0:
  ws=[latest(z['normWriter'],r['idx'][0],ch) for ch in set(z['rawComponents'])]
  opn=ws[0][2] if all(ws) and len({x[0] for x in ws})==1 else -1
  return f'TEMP_OP{opn}'
 return f'TYPE{r["type"]}'

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def build(root:Path,coordinate_verifier:Path,weight_verifier:Path,shared_verifier:Path,surface_verifier:Path,guard_path:Path,mip_verifier:Path,angular_verifier:Path,semantic_verifier:Path):
 configure(coordinate_verifier,weight_verifier,shared_verifier,surface_verifier,guard_path,mip_verifier,angular_verifier,semantic_verifier)
 allref={};maps=[]
 for mn,(rel,sha) in guard.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=sha:raise ValueError(f'{mn}: source mismatch {actual}')
  valid,_=guard.scan_map(path);n=0
  for hh,(blob,res) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in res):
    n+=1;old=allref.setdefault(hh,(blob,res,set()))
    if old[0]!=blob:raise ValueError('reflection shader SHA collision')
    old[2].add(mn)
  maps.append({'map':mn,'reflectionProbeShaderCount':n})
 if len(allref)!=EXPECTED_REFLECTION_SHADERS:raise ValueError(f'reflection shader count {len(allref)}')
 target=standard=0;alt=[];rows=[];resources=collections.Counter();resource_patterns=collections.Counter()
 for hh,(blob,res,mapnames) in sorted(allref.items()):
  sig=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst);hits=0;std=0
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);rr,ss=O[2],O[3]
   if not(rr['type']==7 and ss['type']==6 and rr['idx']==[15] and ss['idx']==[15]):continue
   roles=surf.formula_roles(coord,w,inst,latest,si,p,op)
   if roles is None:raise ValueError(f'{hh}:{si}: reflect formula role mapping failed')
   A=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['A']);B=surf.normalized_raw(coord,w,inst,latest,roles['dotIndex'],roles['B'])
   if A is None or B is None:raise ValueError(f'{hh}:{si}: normalized operand unresolved')
   if (raw_class(sig,latest,A),raw_class(sig,latest,B))!=('TEMP_OP50','TEXCOORD1.xyz'):continue
   target+=1;hits+=1
   q=match(blob,res,si,p,op)
   if q is None:continue
   standard+=1;std+=1
   nx=sorted(set((z[1],z[2],z[3],z[4]) for z in q['nxn']));ny=sorted(set((z[1],z[2],z[3],z[4]) for z in q['nyn']))
   for z in nx:resources[('x',)+z]+=1
   for z in ny:resources[('y',)+z]+=1
   resource_patterns[(tuple(nx),tuple(ny))]+=1
   rows.append({'sha256':hh,'maps':sorted(mapnames),'sampleInstructionIndex':si,
                'baseNormalSelfDotInstructionIndex':q['baseNorm']['selfDotIndex'],
                'baseNormalNormalizeInstructionIndex':q['baseNorm']['normWriter'],
                'crossMulInstructionIndex':q['cross']['crossMulIndex'],
                'crossMadInstructionIndex':q['cross']['crossMadIndex'],
                'handednessMulInstructionIndex':q['cross']['signMulIndex'],
                'normalXNamedLeaves':nx,'normalYNamedLeaves':ny})
  if hits>1:raise ValueError(f'{hh}: target fetch count {hits}')
  if hits and not std:alt.append({'sha256':hh,'maps':sorted(mapnames)})
  if std>1:raise ValueError(f'{hh}: standard fetch count {std}')
 if target!=EXPECTED_TARGET:raise ValueError(f'target count {target}')
 if standard!=EXPECTED_STANDARD:raise ValueError(f'standard count {standard}')
 if len(alt)!=EXPECTED_ALTERNATE:raise ValueError(f'alternate count {len(alt)}')
 if len(rows)!=EXPECTED_STANDARD:raise ValueError('standard shader rows count')
 rr=[{'coefficient':k[0],'resourceName':k[1],'resourceRegister':k[2],'channel':k[3],'opcode':k[4],'ancestryOccurrenceCount':v} for k,v in sorted(resources.items())]
 rp=[{'normalXNamedLeaves':[list(x) for x in k[0]],'normalYNamedLeaves':[list(x) for x in k[1]],'shaderCount':v} for k,v in sorted(resource_patterns.items(),key=lambda kv:(-kv[1],kv[0]))]
 summary={'uniqueReflectionProbeShaderCount':len(allref),'targetTempMadTexcoord1ShaderCount':target,
          'standardTangentBasisShaderCount':standard,'standardTangentBasisFailureCount':0,
          'alternateTargetShaderCount':len(alt),'baseNormalNormalizationCheckCount':standard,
          'crossProductCheckCount':standard,'handednessCheckCount':standard,
          'normalXNamedAncestryCheckCount':standard,'normalYNamedAncestryCheckCount':standard,
          'shaderRowsSha256':jhash(rows),'normalResourceRowsSha256':jhash(rr),
          'normalResourcePatternRowsSha256':jhash(rp),'alternateShaderRowsSha256':jhash(alt)}
 return {'format':'t6-retail-reflection-probe-tangent-basis-normal-v1','producer':'tools/t6_retail_reflection_probe_tangent_basis_normal_v1.py',
         'sources':{'coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json',
                    'surfaceNormalProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_SURFACE_NORMAL_V1.json',
                    'expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in guard.SOURCES.items()}},
         'equations':{'baseNormal':'baseN = normalize(TEXCOORD3.xyz)',
                      'tangent':'T = TEXCOORD4.xyz',
                      'binormal':'B = cross(baseN,T) * TEXCOORD4.w',
                      'rawNormal':'rawN = baseN + normalX*T + normalY*B',
                      'surfaceVector':'surfaceVector = normalize(rawN)',
                      'opposingVector':'opposingVector = normalize(TEXCOORD1.xyz)',
                      'cubeCoord':'opposingVector - 2*surfaceVector*dot(surfaceVector,opposingVector)'},
         'normalNamedResourceAncestry':rr,'normalNamedResourcePatterns':rp,
         'standardShaderExamples':rows[:8],'alternateShaderRows':alt,'mapCoverage':maps,'summary':summary,
         'proofBoundary':'Direct retained-DXBC/RDEF proof for 958 of the 995 reflection-probe shaders whose reflect formula uses a MAD-produced normalized vector against normalized TEXCOORD1.xyz. In all 958, the MAD-produced vector is exactly normalize(normalize(TEXCOORD3.xyz) + normalX*TEXCOORD4.xyz + normalY*(cross(normalize(TEXCOORD3.xyz),TEXCOORD4.xyz)*TEXCOORD4.w)); both normalX and normalY have value ancestry to at least one normal-named reflected texture resource. This establishes a normal-map-driven tangent-basis reconstruction at the pixel-shader level. It does not assign physical vertex-normal/tangent semantics to the TEXCOORD basis, does not assign camera/view semantics to TEXCOORD1, and explicitly leaves the remaining 37 shaders in this operand family as a separate alternate reconstruction family.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
 ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
 ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'))
 ap.add_argument('--surface-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_surface_normal_v1.py'))
 ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
 ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'))
 ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'))
 ap.add_argument('--semantic-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_semantics_v1.py'))
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.weight_verifier,a.shared_verifier,a.surface_verifier,a.guard,a.mip_verifier,a.angular_verifier,a.semantic_verifier);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
