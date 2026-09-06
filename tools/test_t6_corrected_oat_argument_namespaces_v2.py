#!/usr/bin/env python3
from __future__ import annotations
import tempfile
from pathlib import Path
import t6_tech_argument_source_identity_v2 as src
import t6_generated_final_output_cbuffer_signature_v1 as cb1
import t6_generated_final_output_cbuffer_signature_v2 as cb2
import t6_generated_final_output_code_constant_identity_v2 as cid
import t6_generated_final_output_texture_resource_binding_v2 as tb2
import t6_generated_final_output_code_sampler_identity_v2 as sid

def main()->int:
 assert src.source_identity('material.colorMap')['sourceKind']=='material'
 assert src.source_identity('constant.sunDiffuse')['sourceKind']=='constant'
 assert src.source_identity('sampler.reflectionProbeSampler')['sourceKind']=='sampler'
 assert src.source_identity('code.legacy')['sourceKind']=='legacy_code'

 base={'format':cb1.FORMAT,'shaders':[{'sha256':'a'*64,'techniqueSets':['t'],'rdef':{},'usedCbufferSymbols':[
  {'symbol':'cb0[0].x','nodeIds':[1],'buffer':{'name':'Globals'},'variable':{'name':'sunDiffuse','relativeScalarIndex':0},'techniqueAssignments':[{'techniqueSet':'t','sourceClass':'other','sourceExpression':'constant.sunDiffuse','sourceName':None}]},
  {'symbol':'cb0[1].x','nodeIds':[2],'buffer':{'name':'Globals'},'variable':{'name':'zNear','relativeScalarIndex':0},'techniqueAssignments':[{'techniqueSet':'t','sourceClass':'unassigned','sourceExpression':None,'sourceName':None}]},
 ]}],'summary':{'techniqueAssignmentSourceClassCounts':{}},'rowsSha256':'x'}
 promoted=cb2.promote(base)
 a0=promoted['shaders'][0]['usedCbufferSymbols'][0]['techniqueAssignments'][0];assert a0['sourceClass']=='code' and a0['sourceNamespace']=='constant' and a0['sourceName']=='sunDiffuse'
 table={'format':cid.TABLE_FORMAT,'rows':[
  {'accessor':'sunDiffuse','enumSymbol':'CONST_SRC_CODE_SUN_DIFFUSE','enumValue':0x23,'enumValueHex':'0x23','enumAliases':['CONST_SRC_CODE_SUN_DIFFUSE'],'arrayCount':0,'updateFrequency':'CUSTOM','techFlags':None,'transposedMatrixEnumSymbol':None,'transposedMatrixEnumValue':None},
  {'accessor':'zNear','enumSymbol':'CONST_SRC_CODE_ZNEAR','enumValue':0x22,'enumValueHex':'0x22','enumAliases':['CONST_SRC_CODE_ZNEAR'],'arrayCount':0,'updateFrequency':'CUSTOM','techFlags':None,'transposedMatrixEnumSymbol':None,'transposedMatrixEnumValue':None},
 ],'enumAliasesByValue':{'34':['CONST_SRC_CODE_ZNEAR'],'35':['CONST_SRC_CODE_SUN_DIFFUSE']},'source':{}}
 ids=cid.build(promoted,table);rows=ids['shaders'][0]['assignments'];assert {r['bindingMode'] for r in rows}=={'explicitTechAssignment','implicitSameAccessorAutoCreate'}

 with tempfile.TemporaryDirectory(prefix='t6_oat_ns_v2_') as td:
  root=Path(td);(root/'tech').mkdir();(root/'tech'/'a.tech').write_text('colorMapSampler = material.colorMap;\n')
  final={'format':tb2.FINAL_FORMAT,'shaders':[{'sha256':'b'*64,'techniqueSets':['t'],'nodes':[
   {'id':1,'kind':'textureSample','resource':'colorMapSampler','resourceRegister':0,'sampler':'s0','samplerRegister':0,'opcode':'sample','channel':'x','args':[]},
   {'id':2,'kind':'textureSample','resource':'reflectionProbeSampler','resourceRegister':15,'sampler':'s15','samplerRegister':15,'opcode':'sample_l','channel':'x','args':[]},
  ]}]}
  old=tb2.resolve_slot_shader
  try:
   tb2.resolve_slot_shader=lambda oat_root,technique,slot_index:{'techniqueAsset':'a','techniqueFile':'tech/a.tech','pixelShaders':[{'sha256':'b'*64}]}
   bindings=tb2.build(final,oat_root=root)
  finally:tb2.resolve_slot_shader=old
  resources={r['resource']:r for r in bindings['shaders'][0]['resources']}
  assert resources['colorMapSampler']['techniqueAssignments'][0]['sourceClass']=='material'
  assert resources['reflectionProbeSampler']['techniqueAssignments'][0]['sourceClass']=='unassigned'
  stable={'format':sid.TABLE_FORMAT,'source':{},'rows':[{'accessor':'reflectionProbeSampler','enumSymbol':'TEXTURE_SRC_CODE_REFLECTION_PROBE','enumValue':0x1A,'enumValueHex':'0x1a','enumAliases':['TEXTURE_SRC_CODE_REFLECTION_PROBE'],'updateFrequency':'CUSTOM','techFlags':None,'customSamplerIndex':'CUSTOM_SAMPLER_REFLECTION_PROBE'}]}
  joined=sid.build(bindings,stable);probe={r['resource']:r for r in joined['shaders'][0]['resources']}['reflectionProbeSampler']['techniqueAssignments'][0]
  assert probe['bindingMode']=='implicitSameAccessorAutoCreate' and probe['codeSamplerIdentity']['enumValue']==0x1A
 print('PASS: corrected current OAT constant/sampler namespaces and same-accessor auto-create');return 0
if __name__=='__main__':raise SystemExit(main())
