#!/usr/bin/env python3
from __future__ import annotations
import tempfile
from pathlib import Path
import t6_generated_final_output_texture_resource_binding_v1 as binding

SHA='a'*64;TECH='lit_sm_fixture'

def final_doc():
 return {'format':binding.FINAL_FORMAT,'shaders':[{'sha256':SHA,'techniqueSets':[TECH],'nodes':[
  {'id':0,'kind':'symbol','name':'v0.x'},
  {'id':1,'kind':'textureSample','resource':'colorMapSampler','resourceRegister':0,'sampler':'colorMapSampler_s','samplerRegister':0,'opcode':'sample','channel':'x','args':[0]},
  {'id':2,'kind':'textureSample','resource':'reflectionProbeSampler','resourceRegister':15,'sampler':'reflectionProbeSampler_s','samplerRegister':15,'opcode':'sample_l','channel':'x','args':[0]},
  {'id':3,'kind':'textureSample','resource':'colorMapSampler','resourceRegister':0,'sampler':'colorMapSampler_s','samplerRegister':0,'opcode':'sample','channel':'w','args':[0]},
 ]}]}

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_texture_binding_') as td:
  root=Path(td);(root/'techniques').mkdir();techfile=root/'techniques'/'fixture.tech';techfile.write_text('''
colorMapSampler = material.colorMap;
reflectionProbeSampler = code.reflectionProbeSampler;
''')
  old=binding.resolve_slot_shader
  try:
   binding.resolve_slot_shader=lambda oat_root,technique,slot_index:{'techniqueSet':technique,'techniqueAsset':'fixture','techniqueFile':'techniques/fixture.tech','pixelShaders':[{'sha256':SHA}]}
   doc=binding.build(final_doc(),oat_root=root)
  finally:binding.resolve_slot_shader=old
  assert doc['format']==binding.FORMAT
  assert doc['summary']['shaderCount']==1
  assert doc['summary']['sampledTextureResourceCount']==2
  assert doc['summary']['textureSampleNodeCount']==3
  assert doc['summary']['sourceClassAssignmentCounts']=={'code':1,'material':1}
  rows={row['resource']:row for row in doc['shaders'][0]['resources']}
  color=rows['colorMapSampler'];assert color['sampleNodeIds']==[1,3] and color['resourceRegisters']==[0] and color['channels']==['w','x'];assert color['techniqueAssignments'][0]['sourceClass']=='material' and color['techniqueAssignments'][0]['sourceName']=='colorMap'
  probe=rows['reflectionProbeSampler'];assert probe['resourceRegisters']==[15] and probe['samplerRegisters']==[15] and probe['opcodes']==['sample_l'];assert probe['techniqueAssignments'][0]['sourceClass']=='code' and probe['techniqueAssignments'][0]['sourceName']=='reflectionProbeSampler'

  # Same TechniqueSet with a different PS identity cannot bind the final DAG.
  old=binding.resolve_slot_shader
  try:
   binding.resolve_slot_shader=lambda oat_root,technique,slot_index:{'techniqueAsset':'fixture','techniqueFile':'techniques/fixture.tech','pixelShaders':[{'sha256':'b'*64}]}
   try:binding.build(final_doc(),oat_root=root)
   except binding.TextureResourceBindingError as exc:assert '!= final-output' in str(exc)
   else:raise AssertionError('texture binding accepted a different slot-4 CSO')
  finally:binding.resolve_slot_shader=old

  techfile.write_text('colorMapSampler = material.colorMap;\n')
  old=binding.resolve_slot_shader
  try:
   binding.resolve_slot_shader=lambda oat_root,technique,slot_index:{'techniqueAsset':'fixture','techniqueFile':'techniques/fixture.tech','pixelShaders':[{'sha256':SHA}]}
   try:binding.build(final_doc(),oat_root=root)
   except binding.TextureResourceBindingError as exc:assert 'has no exact .tech assignment' in str(exc)
   else:raise AssertionError('sampled resource missing from .tech was accepted')
  finally:binding.resolve_slot_shader=old
 print('PASS: exact generated final-output texture resource binding v1');return 0
if __name__=='__main__':raise SystemExit(main())
