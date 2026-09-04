#!/usr/bin/env python3
"""Retained T6 reflection-probe shared mip/material parameter proof.

For the 4,236 reflectionProbeSampler cube fetches whose proven mip equation is

    LOD = 4 - 4*x

this verifier proves by value/writer identity that the exact same scalar x is
also consumed by one and only one four-lane parameter-pack MAD:

    Q = x * A + B

with exact retained SM4 immediate vectors A/B.  It then requires all four Q
lanes to be value ancestors of the material factor multiplied into decoded
probe RGB and reduces that factor to the two retained compiler encodings of the
same lane-wise equation.

The proof deliberately retains x and P as dataflow labels.  Direct texture
origins are tied to reflected RDEF names, but no universal physical semantic
such as gloss/roughness is asserted for x or P by this stage.
"""
from __future__ import annotations
import argparse, bisect, collections, functools, hashlib, importlib.util, json, struct
from pathlib import Path

EXPECTED_REFLECTION_SHADERS=5868
EXPECTED_TARGET_FETCHES=4236
TYPE_TEMP=0; TYPE_INPUT=1; TYPE_IMM32=4; TYPE_SAMPLER=6; TYPE_RESOURCE=7; TYPE_CB=8
OP_MAD=50
PACK_A_BITS=(0x3f855556,0x3ef33333,0x3c955567,0x3e800000)
PACK_B_BITS=(0x00000000,0x00000000,0xbc800000,0x3f400000)
EXPECTED_FORMS={
 ('mad_sat(P,add(neg(mad(Qx,min(P,Qy),Qz)),Qw),mad(Qx,min(P,Qy),Qz))',)*3:4216,
 ('mad_sat(add(neg(mad(Qx,min(P,Qy),Qz)),Qw),P,mad(Qx,min(P,Qy),Qz))',)*3:20,
}


def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def f32(bits:int):return struct.unpack('<f',struct.pack('<I',bits))[0]

def bits_label(bits:int):
 v=f32(bits)
 if v==0.0:return '0'
 return format(v,'.9g')

def raw_imms(w,o):
 if o['type']!=TYPE_IMM32:return None
 p=o['start']+1
 if o['token']&0x80000000:
  while True:
   if p>=len(w):raise ValueError('truncated extended immediate operand')
   t=w[p];p+=1
   if not t&0x80000000:break
 n=1 if (o['token']&3)==1 else 4 if (o['token']&3)==2 else 0
 if n==0:raise ValueError('unsupported immediate component form')
 if p+n>len(w):raise ValueError('truncated immediate payload')
 return tuple(w[p:p+n])

def prep_shader(coord,weight,w,inst):
 parsed=[]
 for p,op,ln,tok in inst:
  parsed.append([] if op in weight.DCL_OPS or op==53 else weight.parse_all(coord,w,p,ln))
 writer_lists=collections.defaultdict(list);coord_writer_lists=collections.defaultdict(list)
 for ii,((p,op,ln,tok),O) in enumerate(zip(inst,parsed)):
  for d in weight.writer_dests(op,O):
   if d['type']==TYPE_TEMP and len(d['idx'])==1 and isinstance(d['idx'][0],int):
    for ch in d['comps'] or 'x':writer_lists[(d['idx'][0],ch)].append(ii)
  if op in coord.WRITER_OPS:
   d=coord.dest(w,p,op)
   if d and d['type']==TYPE_TEMP and len(d['idx'])==1 and isinstance(d['idx'][0],int):
    for ch in d['comps'] or 'x':coord_writer_lists[(d['idx'][0],ch)].append(ii)
 @functools.lru_cache(maxsize=None)
 def latest(before,reg,ch):
  arr=writer_lists.get((reg,ch),());k=bisect.bisect_left(arr,before)-1
  if k<0:return None
  ii=arr[k];p,op,ln,tok=inst[ii];O=parsed[ii]
  for d in weight.writer_dests(op,O):
   if d['type']==TYPE_TEMP and d['idx']==[reg] and ch in (d['comps'] or 'x'):return ii,p,op,d,O
  raise ValueError('indexed writer lookup mismatch')
 @functools.lru_cache(maxsize=None)
 def coord_latest(before,reg,ch):
  arr=coord_writer_lists.get((reg,ch),());k=bisect.bisect_left(arr,before)-1
  if k<0:return None
  ii=arr[k];p,op,ln,tok=inst[ii];d=coord.dest(w,p,op)
  if not d:raise ValueError('indexed coordinate writer lookup mismatch')
  return ii,p,op,d
 return parsed,latest,coord_latest

def src_component(mip,src,dstcomps,dch):return mip.effective_scalar(src,dstcomps,dch)

def x_identity(coord,mip,w,inst,latest,sample_i,p,op):
 O,_=coord.parse_sample(w,p,op)
 if len(O)!=5:raise ValueError('target reflection sample does not have LOD operand')
 extra=O[4]
 if extra['type']!=TYPE_TEMP or len(extra['idx'])!=1 or len(extra['comps'])!=1:raise ValueError('target LOD is not TEMP scalar')
 wr=latest(sample_i,extra['idx'][0],extra['comps'][0])
 if wr is None or wr[2]!=OP_MAD:raise ValueError('target LOD is not MAD-produced')
 wi,wp,wop,md,M=wr
 if len(M)!=4:raise ValueError('LOD MAD arity mismatch')
 x=M[1];scale=M[2];offset=M[3]
 if raw_imms(w,scale)!=(0xc0800000,) or raw_imms(w,offset)!=(0x40800000,):raise ValueError('target LOD MAD is not exact 4-4x')
 xc=src_component(mip,x,md['comps'],extra['comps'][0])
 if x['type']==TYPE_CB:
  if len(x['idx'])!=2 or not all(isinstance(z,int) for z in x['idx']):raise ValueError('x CB index unresolved')
  return ('cb',tuple(x['idx']),xc,x.get('modifier'))
 if x['type']!=TYPE_TEMP or len(x['idx'])!=1 or not isinstance(x['idx'][0],int):raise ValueError('x is neither direct CB nor TEMP')
 xw=latest(wi,x['idx'][0],xc)
 if xw is None:raise ValueError('x TEMP writer unresolved')
 return ('temp',xw[0],xc,x.get('modifier'))

def read_components(weight,angular,src,dest,op):
 if src['type'] not in (TYPE_TEMP,TYPE_CB):return []
 if op in angular.DP_WIDTH:return list(src['comps'][:angular.DP_WIDTH[op]])
 try:return list(weight.eff(src,dest['comps']))
 except ValueError:return list(src['comps'] or 'x')

def is_x_source(weight,angular,src,dest,op,before,xid,latest):
 comps=read_components(weight,angular,src,dest,op);hits=[]
 if src['type']==TYPE_CB:
  for ch in comps:
   if ('cb',tuple(src['idx']),ch,src.get('modifier'))==xid:hits.append(ch)
 elif src['type']==TYPE_TEMP and len(src['idx'])==1:
  for ch in comps:
   wr=latest(before,src['idx'][0],ch)
   if wr and ('temp',wr[0],ch,src.get('modifier'))==xid:hits.append(ch)
 return hits

def is_pack(w,O,xid,latest,ii,op,weight,angular):
 if op!=OP_MAD or len(O)!=4 or O[0]['comps']!='xyzw':return False
 if raw_imms(w,O[2])!=PACK_A_BITS or raw_imms(w,O[3])!=PACK_B_BITS:return False
 return bool(is_x_source(weight,angular,O[1],O[0],op,ii,xid,latest))

def pack_ancestor_components(weight,angular,factor,dest,before,pack_i,latest,inst,parsed):
 found=set();todo=[];seen=set()
 try:comps=weight.eff(factor,dest['comps'])
 except ValueError:comps=factor['comps'] or 'x'
 if factor['type']!=TYPE_TEMP:return found
 for ch in set(comps):todo.append((before,factor['idx'][0],ch))
 while todo:
  b,r,ch=todo.pop();key=(b,r,ch)
  if key in seen:continue
  seen.add(key);wr=latest(b,r,ch)
  if not wr:continue
  wi,p,op,d,O=wr
  if wi==pack_i:
   found.add(ch);continue
  if op in weight.DCL_OPS or op in (weight.OP_RET,weight.OP_ELSE,weight.OP_ENDIF,weight.OP_IF,weight.OP_DISCARD):continue
  srcs=O[2:] if op==weight.OP_SINCOS else O[1:]
  for src in srcs:
   if src['type']!=TYPE_TEMP or len(src['idx'])!=1:continue
   if op in angular.DP_WIDTH:ss=src['comps'][:angular.DP_WIDTH[op]]
   else:
    try:ss=weight.eff(src,d['comps'])
    except ValueError:ss=src['comps'] or 'x'
   for q in set(ss):todo.append((wi,src['idx'][0],q))
 return found

def has_q(e):return isinstance(e,tuple) and (e[0].startswith('Q') or any(has_q(x) for x in e[1:] if isinstance(x,tuple)))

def expr_string(e):
 if e==('P',):return 'P'
 if e and e[0].startswith('Q'):return e[0]
 return e[0]+'('+','.join(expr_string(x) for x in e[1:])+')'

def source_component(weight,src,d,ch):
 try:return weight.eff(src,d['comps'])[d['comps'].index(ch)]
 except (ValueError,IndexError):return (src['comps'] or 'x')[0]

def q_value(coord,weight,angular,before,reg,ch,pack_i,latest,inst,cache,depth=0):
 key=(before,reg,ch,pack_i)
 if key in cache:return cache[key]
 if depth>96:raise ValueError('Q expression recursion depth exceeded')
 wr=latest(before,reg,ch)
 if not wr:return ('P',)
 wi,p,op,d,O=wr
 if wi==pack_i:
  e=('Q'+ch,);cache[key]=e;return e
 if op in weight.DCL_OPS or op in (weight.OP_RET,weight.OP_ELSE,weight.OP_ENDIF,weight.OP_IF,weight.OP_DISCARD):return ('P',)
 def one(src):
  if src['type']!=TYPE_TEMP or len(src['idx'])!=1:return ('P',)
  sc=source_component(weight,src,d,ch);e=q_value(coord,weight,angular,wi,src['idx'][0],sc,pack_i,latest,inst,cache,depth+1)
  if has_q(e) and src.get('modifier'):e=(src['modifier'],e)
  return e
 if op in angular.DP_WIDTH:
  args=[]
  for src in O[1:3]:
   vv=[]
   if src['type']==TYPE_TEMP and len(src['idx'])==1:
    for sc in src['comps'][:angular.DP_WIDTH[op]]:vv.append(q_value(coord,weight,angular,wi,src['idx'][0],sc,pack_i,latest,inst,cache,depth+1))
   else:vv=[('P',)]*angular.DP_WIDTH[op]
   args.append(tuple(vv))
  if any(has_q(z) for grp in args for z in grp):e=(angular.OPS[op],)+tuple(('vec',)+grp for grp in args)
  else:e=('P',)
 elif op in coord.SAMPLE_OPS:e=('P',)
 elif op==weight.OP_SINCOS:e=(angular.OPS[op],one(O[2]))
 else:
  args=[one(src) for src in O[1:]]
  e=(angular.OPS[op]+('_sat' if inst[wi][3]&0x2000 else ''),)+tuple(args)
  if not any(has_q(a) for a in args):e=('P',)
 cache[key]=e;return e

def factor_qexpr(coord,weight,angular,factor,d,before,pack_i,latest,inst):
 if factor['type']!=TYPE_TEMP:return ('P',)
 try:comps=weight.eff(factor,d['comps'])
 except ValueError:comps=factor['comps'] or 'x'
 cache={};out=[]
 for sc in comps:out.append(q_value(coord,weight,angular,before,factor['idx'][0],sc,pack_i,latest,inst,cache))
 return tuple(expr_string(x) for x in out)

def build(root:Path,coordinate_verifier:Path,mip_verifier:Path,weight_verifier:Path,angular_verifier:Path,guard_path:Path):
 coord=load(coordinate_verifier,'coord');mip=load(mip_verifier,'mip');weight=load(weight_verifier,'weight');angular=load(angular_verifier,'angular');guard=load(guard_path,'guard')
 all_ref={};maps=[]
 for mapname,(rel,expected_sha) in guard.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=expected_sha:raise ValueError(f'{mapname}: expanded SHA mismatch {actual}')
  valid,_=guard.scan_map(path);local=0
  for hh,(blob,resources) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in resources):
    local+=1;old=all_ref.setdefault(hh,(blob,resources,set()))
    if old[0]!=blob:raise ValueError('reflection shader SHA collision')
    old[2].add(mapname)
  maps.append({'map':mapname,'validDxbcCount':len(valid),'reflectionProbeShaderCount':local})
 if len(all_ref)!=EXPECTED_REFLECTION_SHADERS:raise ValueError(f'reflection shader count {len(all_ref)}')
 origin_counts=collections.Counter();direct_sources=collections.Counter();forms=collections.Counter();rows=[];total=0;pack_count=0;all_lane_count=0
 base_weight_latest=weight.latest_writer_any;base_coord_latest=coord.latest_writer
 for hh,(blob,resources,mapnames) in sorted(all_ref.items()):
  w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,coord_latest=prep_shader(coord,weight,w,inst)
  weight.latest_writer_any=lambda _c,_i,_w,b,r,ch:latest(b,r,ch)
  coord.latest_writer=lambda _i,_w,b,r,ch:coord_latest(b,r,ch)
  local=0;local_forms=collections.Counter()
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);sd,cube,res,sam=O[:4]
   if not(res['type']==TYPE_RESOURCE and sam['type']==TYPE_SAMPLER and res['idx']==[15] and sam['idx']==[15]):continue
   mq=mip.prove_fetch(coord,w,inst,si,p,op)
   if not(mq and mq['kind']=='affine_lod' and mq['scaleBits']=='c0800000' and mq['offsetBits']=='40800000'):continue
   coord.prove_sample(w,inst,si,p,op)
   decoded=weight.first_rgb_consumer(coord,w,inst,si,sd,res);factor_use,dest,factor=angular.second_factor(weight,coord,w,inst,decoded)
   xid=x_identity(coord,mip,w,inst,latest,si,p,op)
   packs=[ii for ii,(pp,oo,ll,tt) in enumerate(inst[:factor_use]) if parsed[ii] and is_pack(w,parsed[ii],xid,latest,ii,oo,weight,angular)]
   if len(packs)!=1:raise ValueError(f'{hh}:{si}: exact Q pack count {len(packs)}')
   pack_i=packs[0];pack_count+=1
   used=pack_ancestor_components(weight,angular,factor,dest,factor_use,pack_i,latest,inst,parsed)
   if used!=set('xyzw'):raise ValueError(f'{hh}:{si}: Q factor ancestry lanes {sorted(used)}')
   all_lane_count+=1
   form=factor_qexpr(coord,weight,angular,factor,dest,factor_use,pack_i,latest,inst)
   if form not in EXPECTED_FORMS:raise ValueError(f'{hh}:{si}: unexpected Q factor form {form}')
   forms[form]+=1;local_forms[jhash(form)]+=1;local+=1;total+=1
   origin=mq['sourceOrigin'];origin_counts[(origin['kind'],origin.get('firstWriter','CB'))]+=1
   if 'sampleResourceRegister' in origin:
    rr=origin['sampleResourceRegister'];names=sorted({r['name'] for r in resources if r['inputType']==guard.INPUT_TEXTURE and r['bindPoint']==rr})
    if len(names)!=1:raise ValueError(f'{hh}:{si}: x direct source t{rr} reflected names {names}')
    direct_sources[(names[0],rr,origin['sampleChannel'],origin['sampleOpcode'])]+=1
  if local:rows.append({'sha256':hh,'maps':sorted(mapnames),'targetFetchCount':local,'factorFormCounts':dict(sorted(local_forms.items()))})
  weight.latest_writer_any=base_weight_latest;coord.latest_writer=base_coord_latest
 if total!=EXPECTED_TARGET_FETCHES:raise ValueError(f'target 4-4x fetch count {total}')
 expected_origins={('constant_buffer','CB'):40,('temp','MAD'):1350,('temp','MUL'):822,('temp','SAMPLE'):2024}
 if dict(origin_counts)!=expected_origins:raise ValueError(f'x source origin census {origin_counts}')
 if dict(forms)!=EXPECTED_FORMS:raise ValueError(f'factor form census {forms}')
 if pack_count!=total or all_lane_count!=total:raise ValueError('Q pack/ancestry count mismatch')
 form_rows=[]
 for form,count in sorted(forms.items(),key=lambda kv:(-kv[1],kv[0])):
  form_rows.append({'formSha256':jhash(form),'count':count,'laneExpressions':list(form)})
 direct_rows=[{'resourceName':k[0],'resourceRegister':k[1],'channel':k[2],'opcode':k[3],'count':v} for k,v in sorted(direct_sources.items())]
 origin_rows=[{'sourceKind':k[0],'firstWriter':k[1],'count':v} for k,v in sorted(origin_counts.items())]
 A=[{'bits':f'{b:08x}','value':bits_label(b)} for b in PACK_A_BITS];B=[{'bits':f'{b:08x}','value':bits_label(b)} for b in PACK_B_BITS]
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':len(all_ref),'affine4Minus4xFetchCount':total,
          'sameXPackCheckCount':total,'sameXPackFailureCount':0,'uniqueQPackPerFetchCount':pack_count,'allFourQLanesReachFactorCount':all_lane_count,
          'qFactorFormCount':len(form_rows),'qFactorDominantFormCount':4216,'qFactorCommutedFormCount':20,
          'xSourceOriginCount':sum(origin_counts.values()),'directTextureXSourceCount':sum(direct_sources.values()),
          'shaderRowsSha256':jhash(rows),'factorFormRowsSha256':jhash(form_rows),'xOriginRowsSha256':jhash(origin_rows),'directXSourceRowsSha256':jhash(direct_rows)}
 return {'format':'t6-retail-reflection-probe-shared-parameter-v1','producer':'tools/t6_retail_reflection_probe_shared_parameter_v1.py',
         'sources':{'coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json','mipProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_MIP_V1.json','weightProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_WEIGHT_V1.json','angularProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_ANGULAR_V1.json','expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in guard.SOURCES.items()}},
         'equation':{'lod':'4 - 4*x','qPack':'Q = x*A + B','A':A,'B':B,
                     'lanes':{'Qx':'1.0416667461395264*x','Qy':'0.4749999940395355*x','Qz':'0.018229199573397636*x - 0.015625','Qw':'0.25*x + 0.75'},
                     'angularInputFromPriorProof':'E = 2^(-9.28*saturate(dot(U,-V)))','C':'min(E,Qy)','F':'Qx*C + Qz',
                     'reflectionFactorRgb':'saturate(P.rgb * (Qw - F) + F)','decodedProbeRgb':'probe.rgb / (probe.a + 1e-6)','reflectionRgb':'decodedProbe.rgb * reflectionFactor.rgb'},
         'xSourceOriginCounts':origin_rows,'directTextureXSources':direct_rows,'factorForms':form_rows,'mapCoverage':maps,'summary':summary,
         'proofBoundary':'Direct retained-SM4 value/writer-identity proof for all 4,236 reflectionProbeSampler fetches whose already-proven mip equation is LOD = 4 - 4*x. The exact same scalar x is required to feed exactly one four-lane MAD Q=x*A+B with the pinned immediate vectors, all four Q lanes must be ancestors of the post-decode reflection factor, and that factor must match one of two retained compiler encodings that are algebraically identical to saturate(P.rgb*(Qw-(Qx*min(E,Qy)+Qz)) + (Qx*min(E,Qy)+Qz)), with E inherited from the separately proven angular stage. Direct x texture origins are tied to RDEF names/channels. This proof does not assign one universal physical gloss/roughness meaning to x, does not name P.rgb physically, and does not reconstruct original HLSL.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
 ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'))
 ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
 ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'))
 ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
