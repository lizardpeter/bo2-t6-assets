#!/usr/bin/env python3
"""Retained T6 reflection-probe material-color square proof.

For all 4,236 fetches in the already-proven LOD=4-4*x / Q-pack family, isolate
the Q-independent P operand of the saturated reflection-factor interpolation.
The retained SM4 population must split exactly into:

  * 4,216 fetches: P.rgb = S.rgb * S.rgb, with both MUL inputs resolving by
    writer/component identity to the same S value in every RGB lane;
  * 20 fetches: P is the exact immediate scalar 0x3d23d70a (~0.04).

S is intentionally a mathematical/material dataflow label.  This stage records
its direct first-writer and RDEF texture provenance, but does not claim that the
square is a gamma/sRGB conversion or assign one universal physical semantic to
all recursively derived S values.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json
from pathlib import Path

EXPECTED_REFLECTION_SHADERS=5868
EXPECTED_TARGET_FETCHES=4236
EXPECTED_SQUARE=4216
EXPECTED_IMMEDIATE=20
P_IMMEDIATE_BITS=(0x3d23d70a,)
TYPE_TEMP=0; TYPE_INPUT=1; TYPE_IMM32=4; TYPE_CB=8
OP_MUL=56


def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def qdep(shared,e):return shared.has_q(e)

def operand_qdep(coord,weight,angular,shared,src,dest,before,pack_i,latest,inst):
 if src['type']!=TYPE_TEMP:return False
 try:comps=weight.eff(src,dest['comps'])
 except ValueError:comps=src['comps'] or 'x'
 cache={}
 return any(qdep(shared,shared.q_value(coord,weight,angular,before,src['idx'][0],ch,pack_i,latest,inst,cache)) for ch in set(comps))

def p_operand(coord,weight,angular,shared,factor,dest,before,pack_i,latest,inst):
 if factor['type']!=TYPE_TEMP:raise ValueError('reflection factor is not TEMP')
 try:comps=weight.eff(factor,dest['comps'])
 except ValueError:comps=factor['comps'] or 'x'
 wrs=[latest(before,factor['idx'][0],ch) for ch in set(comps)]
 if any(x is None for x in wrs) or len({x[0] for x in wrs})!=1:raise ValueError('reflection factor RGB writer split')
 wr=wrs[0];wi,p,op,fd,O=wr
 if op!=50 or not(inst[wi][3]&0x2000):raise ValueError('reflection factor writer is not MAD_SAT')
 deps=[operand_qdep(coord,weight,angular,shared,src,fd,wi,pack_i,latest,inst) for src in O[1:]]
 if not deps[2] or deps[0]==deps[1]:raise ValueError(f'cannot isolate Q-independent P operand: {deps}')
 return wi,fd,O[1 if not deps[0] else 2]

def used_component(weight,src,dest,dch):
 try:return weight.eff(src,dest['comps'])[dest['comps'].index(dch)]
 except (ValueError,IndexError):return (src['comps'] or 'x')[0]

def value_identity(weight,shared,w,src,dest,dch,before,latest):
 ch=used_component(weight,src,dest,dch)
 typ=src['type'];mod=src.get('modifier')
 if typ==TYPE_TEMP:
  if len(src['idx'])!=1 or not isinstance(src['idx'][0],int):raise ValueError('TEMP value index unresolved')
  wr=latest(before,src['idx'][0],ch)
  if wr is None:raise ValueError('TEMP value writer unresolved')
  return ('temp',wr[0],ch,mod)
 if typ==TYPE_CB:return ('cb',tuple(src['idx']),ch,mod)
 if typ==TYPE_INPUT:return ('input',tuple(src['idx']),ch,mod)
 if typ==TYPE_IMM32:return ('imm',tuple(shared.raw_imms(w,src)),ch,mod)
 return ('type',typ,tuple(src.get('idx',[])),ch,mod)

def resource_name(guard,resources,rr):
 names=sorted({r['name'] for r in resources if r['inputType']==guard.INPUT_TEXTURE and r['bindPoint']==rr})
 if len(names)!=1:raise ValueError(f't{rr}: reflected texture names {names}')
 return names[0]

def direct_sample_source(coord,mip,weight,guard,w,inst,src,dest,before,latest,resources):
 if src['type']!=TYPE_TEMP:return None
 try:cs=weight.eff(src,dest['comps'])
 except ValueError:cs=src['comps'] or 'x'
 wrs=[latest(before,src['idx'][0],ch) for ch in cs]
 if any(x is None for x in wrs) or len({x[0] for x in wrs})!=1:return None
 wr=wrs[0]
 if wr[2] not in coord.SAMPLE_OPS:return None
 O,_=coord.parse_sample(w,wr[1],wr[2]);sd,c,res,sam=O[:4]
 chans=''.join(mip.effective_scalar(res,sd['comps'],ch) for ch in cs)
 return (resource_name(guard,resources,res['idx'][0]),res['idx'][0],chans,coord.SAMPLE_OPS[wr[2]])

def first_writer_class(coord,weight,angular,src,dest,before,latest):
 if src['type']==TYPE_CB:return 'CB'
 if src['type']==TYPE_INPUT:return 'INPUT'
 if src['type']==TYPE_IMM32:return 'IMM'
 if src['type']!=TYPE_TEMP:return f'TYPE_{src["type"]}'
 try:cs=weight.eff(src,dest['comps'])
 except ValueError:cs=src['comps'] or 'x'
 wrs=[latest(before,src['idx'][0],ch) for ch in cs]
 if any(x is None for x in wrs):raise ValueError('S first writer unresolved')
 if len({x[0] for x in wrs})!=1:raise ValueError('S RGB first writer split')
 return angular.OPS[wrs[0][2]].upper()

def build(root:Path,coordinate_verifier:Path,mip_verifier:Path,weight_verifier:Path,angular_verifier:Path,shared_verifier:Path,guard_path:Path):
 coord=load(coordinate_verifier,'coord');mip=load(mip_verifier,'mip');weight=load(weight_verifier,'weight');angular=load(angular_verifier,'angular');shared=load(shared_verifier,'shared');guard=load(guard_path,'guard')
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
 square=imm=total=0;writer_counts=collections.Counter();direct=collections.Counter();rows=[]
 base_weight_latest=weight.latest_writer_any;base_coord_latest=coord.latest_writer
 for hh,(blob,resources,mapnames) in sorted(all_ref.items()):
  w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,coord_latest=shared.prep_shader(coord,weight,w,inst)
  weight.latest_writer_any=lambda _c,_i,_w,b,r,ch:latest(b,r,ch)
  coord.latest_writer=lambda _i,_w,b,r,ch:coord_latest(b,r,ch)
  local_square=local_imm=0;local_writers=collections.Counter()
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);sd,cube,res,sam=O[:4]
   if not(res['type']==7 and sam['type']==6 and res['idx']==[15] and sam['idx']==[15]):continue
   mq=mip.prove_fetch(coord,w,inst,si,p,op)
   if not(mq and mq['kind']=='affine_lod' and mq['scaleBits']=='c0800000' and mq['offsetBits']=='40800000'):continue
   dec=weight.first_rgb_consumer(coord,w,inst,si,sd,res);factor_use,dest,factor=angular.second_factor(weight,coord,w,inst,dec)
   xid=shared.x_identity(coord,mip,w,inst,latest,si,p,op)
   packs=[ii for ii in range(factor_use) if parsed[ii] and shared.is_pack(w,parsed[ii],xid,latest,ii,inst[ii][1],weight,angular)]
   if len(packs)!=1:raise ValueError(f'{hh}:{si}: Q pack count {len(packs)}')
   pi,pdest,P=p_operand(coord,weight,angular,shared,factor,dest,factor_use,packs[0],latest,inst)
   total+=1
   if P['type']==TYPE_IMM32:
    bits=tuple(shared.raw_imms(w,P))
    if bits!=P_IMMEDIATE_BITS:raise ValueError(f'{hh}:{si}: P immediate bits {bits}')
    imm+=1;local_imm+=1;continue
   if P['type']!=TYPE_TEMP:raise ValueError(f'{hh}:{si}: P is type {P["type"]}, expected TEMP or immediate')
   try:pcs=weight.eff(P,pdest['comps'])
   except ValueError:pcs=P['comps'] or 'x'
   wrs=[latest(pi,P['idx'][0],ch) for ch in pcs]
   if any(x is None for x in wrs) or len({x[0] for x in wrs})!=1:raise ValueError(f'{hh}:{si}: P RGB square writer split')
   mul=wrs[0];mi,mp,mop,md,M=mul
   if mop!=OP_MUL or len(M)!=3:raise ValueError(f'{hh}:{si}: P writer is not RGB MUL')
   a,b=M[1],M[2]
   for dch in md['comps']:
    ia=value_identity(weight,shared,w,a,md,dch,mi,latest);ib=value_identity(weight,shared,w,b,md,dch,mi,latest)
    if ia!=ib:raise ValueError(f'{hh}:{si}: P square source mismatch {dch}: {ia}!={ib}')
   square+=1;local_square+=1
   sclass=first_writer_class(coord,weight,angular,a,md,mi,latest);writer_counts[sclass]+=1;local_writers[sclass]+=1
   ds=direct_sample_source(coord,mip,weight,guard,w,inst,a,md,mi,latest,resources)
   if ds:direct[ds]+=1
  if local_square or local_imm:
   rows.append({'sha256':hh,'maps':sorted(mapnames),'squareFetchCount':local_square,'immediateFetchCount':local_imm,'sFirstWriterCounts':dict(sorted(local_writers.items()))})
  weight.latest_writer_any=base_weight_latest;coord.latest_writer=base_coord_latest
 if total!=EXPECTED_TARGET_FETCHES or square!=EXPECTED_SQUARE or imm!=EXPECTED_IMMEDIATE:raise ValueError(f'P split {(total,square,imm)}')
 expected_writers={'SAMPLE':1914,'MAD':1750,'MUL':380,'MOVC':132,'CB':40}
 if dict(writer_counts)!=expected_writers:raise ValueError(f'S first-writer census {writer_counts}')
 expected_direct={
  ('specularMapSampler',2,'xyz','SAMPLE'):1008,
  ('specularMapSampler',1,'xyz','SAMPLE'):440,
  ('SpecularAndGloss',2,'xyz','SAMPLE'):140,
  ('specularMapSampler',3,'xyz','SAMPLE'):86,
  ('SpecularAndGloss2',2,'xyz','SAMPLE'):60,
  ('SpecularAndGloss',3,'xyz','SAMPLE'):40,
  ('SpecularAndGloss',4,'xyz','SAMPLE'):40,
  ('specular_map',1,'xyz','SAMPLE'):20,
  ('SpecularGlossMap',1,'xyz','SAMPLE'):20,
  ('specular_map',4,'xyz','SAMPLE'):20,
  ('SpecularAndGloss',6,'xyz','SAMPLE'):20,
  ('Specular_Color_Map',3,'xyz','SAMPLE'):20,
 }
 if dict(direct)!=expected_direct:raise ValueError(f'direct S sample census {direct}')
 writer_rows=[{'firstWriter':k,'count':v} for k,v in sorted(writer_counts.items())]
 direct_rows=[{'resourceName':k[0],'resourceRegister':k[1],'channels':k[2],'opcode':k[3],'count':v} for k,v in sorted(direct.items())]
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':len(all_ref),'sharedParameterFetchCount':total,
          'squaredMaterialColorFetchCount':square,'immediateMaterialColorFetchCount':imm,'materialColorSquareFailureCount':0,
          'immediateMaterialColorBits':'3d23d70a','sFirstWriterCount':sum(writer_counts.values()),'directSampleSCount':sum(direct.values()),
          'shaderRowsSha256':jhash(rows),'sFirstWriterRowsSha256':jhash(writer_rows),'directSRowsSha256':jhash(direct_rows)}
 return {'format':'t6-retail-reflection-probe-material-color-v1','producer':'tools/t6_retail_reflection_probe_material_color_v1.py',
         'sources':{'sharedParameterProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_SHARED_PARAMETER_V1.json','angularProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_ANGULAR_V1.json','expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in guard.SOURCES.items()}},
         'equation':{'squaredFamily':'P.rgb = S.rgb * S.rgb','immediateFamilyBits':'3d23d70a','immediateFamilyValue':'~0.04','downstreamFromPriorProof':'reflectionFactor.rgb = saturate(P.rgb * (Qw - F) + F)'},
         'sFirstWriterCounts':writer_rows,'directSampleSSources':direct_rows,'mapCoverage':maps,'summary':summary,
         'proofBoundary':'Direct retained-SM4 writer/component-identity proof for the Q-independent P operand in all 4,236 members of the separately proven LOD=4-4*x shared-parameter reflection family. Exactly 4,216 P values are produced by an RGB MUL whose two operands resolve lane-by-lane to the identical source value S, proving P.rgb=S.rgb*S.rgb. The remaining 20 are the exact immediate scalar 0x3d23d70a (~0.04). S first-writer classes and direct reflected texture names are counted exactly. This proof does not claim that the square is gamma/sRGB decoding, does not assign one universal physical semantic to derived S, and does not reconstruct original HLSL.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
 ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'))
 ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
 ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'))
 ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'))
 ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.shared_verifier,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
