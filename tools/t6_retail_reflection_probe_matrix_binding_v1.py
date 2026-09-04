#!/usr/bin/env python3
"""Retained T6 MaterialShaderArgument proof for reflection vertex matrices."""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path
EXPECTED_TARGET_SHADERS=4086;EXPECTED_PASSES=5676;CODE_VERTEX_CONST=3
WORLD=0xD5;VIEWPROJ=0xE5;SHADOW=0xED
OAT_COMMIT='6d44ed0568c9d5312cf04265e2e15f77cd0e4f3a'
NAMES={WORLD:'CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX',VIEWPROJ:'CONST_SRC_CODE_TRANSPOSE_VIEW_PROJECTION_MATRIX',SHADOW:'CONST_SRC_CODE_TRANSPOSE_SHADOW_LOOKUP_MATRIX'}
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def arg_records(d,p,n,blocks,prod):
 if p+12*n>len(d):raise ValueError('args eof')
 out=[];vals=[]
 for i in range(n):
  typ,loc,size,buf,u=struct.unpack_from('<HHHHI',d,p+12*i);idx=u&0xffff;first=(u>>16)&255;rows=(u>>24)&255
  if typ>=8:raise ValueError('bad arg type')
  out.append({'type':typ,'locationOffset':loc,'size':size,'buffer':buf,'codeIndex':idx,'firstRow':first,'rowCount':rows});vals.append((typ,u))
 q=p+12*n
 for typ,u in vals:
  if typ in (1,7):
   k=prod.ff_dec(u,blocks)[0]
   if k in ('following','insert'):q+=16
   elif k not in ('packed','null'):raise ValueError('bad literal pointer')
 return q,out
def collect(root,prod,target):
 occ=[];kinds=collections.Counter();orig=prod.ff_parse_args
 try:
  for mn,cfg in prod.PASS_MAPS.items():
   d=(root/cfg['rel']).read_bytes();h=hashlib.sha256(d).hexdigest()
   if h!=cfg['sha']:raise ValueError(f'{mn}: source mismatch {h}')
   blocks=prod.ff_front(d);count=cfg['q1']-cfg['q0']+1;rs=prod.ff_scan_tech(d,blocks,cfg['world'])[-count:]
   if len(rs)!=count:raise ValueError('TechniqueSet count')
   for ti,r in enumerate(rs):
    groups=[]
    def grab(dd,p,n,bb):
     q,z=arg_records(dd,p,n,bb,prod);groups.append(z);return q
    prod.ff_parse_args=grab
    nxt=rs[ti+1]['fixedStart'] if ti+1<len(rs) else cfg['world'];ts=prod.ff_parse_techset(d,r,nxt,blocks)
    gi=0
    for tr in ts['techniqueRefs']:
     it=tr.get('inlineTechnique')
     if not it:continue
     for pa in it['passes']:
      ak=pa['children']['args']['kind'];args=[]
      if ak in ('following','insert'):
       if gi>=len(groups):raise ValueError('argument group underflow')
       args=groups[gi];gi+=1
      ps=pa['children']['pixelShader'];pi=ps.get('inline')
      if not pi or not pi['program']['direct'] or pi['program']['sha256'] not in target:continue
      kinds[ak]+=1
      if pa['argCount'] and ak not in ('following','insert'):raise ValueError('target args not direct')
      occ.append({'map':mn,'techniqueSet':ts['name'],'worldVertFormat':ts['worldVertFormat'],'slot':tr['slot'],'passIndex':pa['passIndex'],'pixelShaderSha256':pi['program']['sha256'],'argCount':pa['argCount'],'arguments':args})
    if gi!=len(groups):raise ValueError('argument group overflow')
 finally:prod.ff_parse_args=orig
 return occ,kinds
def key(a):return (a['type'],a['locationOffset'],a['size'],a['buffer'],a['codeIndex'],a['firstRow'],a['rowCount'])
def build(root,producer_verifier,coordinate_verifier,mip_verifier,weight_verifier,angular_verifier,semantic_verifier,surface_verifier,shared_verifier,guard_path):
 prod=load(producer_verifier,'prod');coord=load(coordinate_verifier,'coord');mip=load(mip_verifier,'mip');weight=load(weight_verifier,'weight');angular=load(angular_verifier,'angular');sem=load(semantic_verifier,'sem');surf=load(surface_verifier,'surf');shared=load(shared_verifier,'shared');guard=load(guard_path,'guard')
 target=prod.collect_target_shaders(root,coord,mip,weight,angular,sem,surf,shared,guard)
 if len(target)!=EXPECTED_TARGET_SHADERS:raise ValueError('target shader count')
 occ,kinds=collect(root,prod,target)
 if len(occ)!=EXPECTED_PASSES:raise ValueError(f'pass count {len(occ)}')
 allcode=collections.Counter();rows=[];maps=collections.Counter();slots=collections.Counter()
 for r in occ:
  code=[a for a in r['arguments'] if a['type']==CODE_VERTEX_CONST]
  for a in code:allcode[key(a)]+=1
  w=[a for a in code if a['codeIndex']==WORLD]
  if len(w)!=1 or key(w[0])!=(3,0,64,3,WORLD,0,4):raise ValueError('world binding mismatch')
  maps[r['map']]+=1;slots[r['slot']]+=1;rows.append({k:r[k] for k in ('map','techniqueSet','worldVertFormat','slot','passIndex','pixelShaderSha256','argCount')})
 matrix=[]
 for k,n in sorted(allcode.items(),key=lambda x:(x[0][4],x[0])):
  typ,loc,size,buf,idx,first,rc=k
  if idx>=0xD3:matrix.append({'type':typ,'locationOffset':loc,'size':size,'buffer':buf,'codeIndex':idx,'codeIndexHex':f'0x{idx:02X}','codeName':NAMES.get(idx),'firstRow':first,'rowCount':rc,'passOccurrenceCount':n})
 by={ (q['codeIndex'],q['locationOffset'],q['size'],q['buffer'],q['firstRow'],q['rowCount']):q['passOccurrenceCount'] for q in matrix }
 exp={(WORLD,0,64,3,0,4):5676,(VIEWPROJ,576,64,0,0,4):5676,(SHADOW,768,64,0,0,4):2580}
 if by!=exp:raise ValueError(f'matrix census {by}')
 summary={'retainedMapCount':5,'surfaceNormalTargetShaderCount':len(target),'targetPassOccurrenceCount':len(occ),'targetPassArgumentPointerKinds':dict(sorted(kinds.items())),'worldMatrixBindingCheckCount':len(occ),'worldMatrixBindingFailureCount':0,'worldMatrixSourceIndex':WORLD,'worldMatrixDestinationBuffer':3,'worldMatrixDestinationOffset':0,'worldMatrixSizeBytes':64,'worldMatrixFirstRow':0,'worldMatrixRowCount':4,'transposeViewProjectionBindingCount':5676,'transposeShadowLookupBindingCount':2580,'occurrenceRowsSha256':jhash(rows),'matrixBindingRowsSha256':jhash(matrix),'mapCountsSha256':jhash(sorted(maps.items())),'slotCountsSha256':jhash(sorted(slots.items()))}
 return {'format':'t6-retail-reflection-probe-matrix-binding-v1','producer':'tools/t6_retail_reflection_probe_matrix_binding_v1.py','sources':{'texcoord5ProducerProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD5_PRODUCER_V1.json','packedVsAliasProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json','surfaceNormalProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_SURFACE_NORMAL_V1.json','t6AssetContract':{'project':'OpenAssetTools','commit':OAT_COMMIT,'path':'src/Common/Game/T6/T6_Assets.h'}},'worldMatrixBinding':{'argumentType':3,'argumentTypeName':'MTL_ARG_CODE_VERTEX_CONST','codeIndex':WORLD,'codeIndexHex':'0xD5','codeName':NAMES[WORLD],'locationOffset':0,'sizeBytes':64,'buffer':3,'firstRow':0,'rowCount':4,'shaderRdefDestination':'dlights.worldMatrix'},'matrixBindingCensus':matrix,'summary':summary,'proofBoundary':'Direct retained-byte MaterialShaderArgument proof over all 5,676 parsed pass occurrences whose physically direct pixel shader belongs to the 4,086-shader surface-normal reflection subset. Every occurrence contains exactly one type-3 code vertex constant binding source index 0xD5, firstRow 0, rowCount 4 to vertex constant buffer 3 offset 0, size 64. The pinned T6 asset contract names type 3 MTL_ARG_CODE_VERTEX_CONST and source 0xD5 CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX. This establishes the serialized engine source identity feeding the dlights.worldMatrix RDEF destination. It does not by itself prove whether T6 world matrices are camera-relative or assign view/incident semantics to TEXCOORD5.'}
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));a.add_argument('--producer-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord5_producer_v1.py'));a.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));a.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'));a.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'));a.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'));a.add_argument('--semantic-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_semantics_v1.py'));a.add_argument('--surface-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_surface_normal_v1.py'));a.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'));a.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));a.add_argument('--out',type=Path,required=True);q=a.parse_args();d=build(q.root,q.producer_verifier,q.coordinate_verifier,q.mip_verifier,q.weight_verifier,q.angular_verifier,q.semantic_verifier,q.surface_verifier,q.shared_verifier,q.guard);q.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
