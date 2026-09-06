#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v33 as v33

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v33_') as td:
  root=Path(td);old=root/'m_v32.glb';gb=b'UNCHANGED-V32';old.write_bytes(gb)
  final=root/'final.json';final.write_text(json.dumps({'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]}))
  spec=root/'spec.json';spec.write_text(json.dumps({'format':'t6-generated-final-output-specular-state-anchor-v1','materials':[]}))
  om=root/'old.json';om.write_text('{}')
  base={'format':v33.v32.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':{'path':str(final),'file':final.name,'bytes':final.stat().st_size,'sha256':'f'},'generatedFinalOutputSpecularStateAnchor':{'path':str(spec),'file':spec.name,'bytes':spec.stat().st_size,'sha256':'s'}},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v33.v32.run_oat_textured_pipeline;oldbuild=v33.reflection_index.build;calls=[]
  try:
   v33.v32.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(fd,sp,strict_known_forms=True):
    calls.append(strict_known_forms)
    return {'format':v33.reflection_index.FORMAT,'shaders':[{'shaderSha256':'a'*64}],'summary':{'shaderCount':1,'reflectionSampleCount':2,'unknownFormCount':0,'coordinateSpecularDependentSampleCount':1,'lodBiasSpecularDependentSampleCount':1,'formCounts':{'affine_lod:c0800000:40800000':1,'bias:c0400000':1},'strictKnownForms':True},'rowsSha256':'a'*64}
   v33.reflection_index.build=fake
   result=v33.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v33.v32.run_oat_textured_pipeline=oldrun;v33.reflection_index.build=oldbuild
  assert calls==[True,True]
  assert result['format']==v33.FORMAT
  assert result['validation']['v33ReflectionSampleIndexGenerated'] is True
  assert result['validation']['v33ReflectionUnknownFormCount']==0
  assert result['validation']['v33ReflectionCoordinateSpecularDependentSampleCount']==1
  assert result['validation']['v33ReflectionLodBiasSpecularDependentSampleCount']==1
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  side=Path(result['outputs']['generatedFinalOutputReflectionSampleIndex']['path']);assert json.loads(side.read_text())['summary']['reflectionSampleCount']==2
  assert not om.exists()
 print('PASS: production v33 exact generated reflection sample index sidecar');return 0
if __name__=='__main__':raise SystemExit(main())
