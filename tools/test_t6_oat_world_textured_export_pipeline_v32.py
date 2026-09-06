#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v32 as v32

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v32_') as td:
  root=Path(td);old=root/'m_v31.glb';gb=b'GLB-UNCHANGED-V31';old.write_bytes(gb)
  final=root/'final.json';final.write_text(json.dumps({'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]}))
  spec=root/'spec.json';spec.write_text(json.dumps({'format':'t6-generated-final-output-specular-state-anchor-v1','materials':[]}))
  om=root/'old.json';om.write_text('{}')
  base={'format':v32.v31.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':{'path':str(final),'file':final.name,'bytes':final.stat().st_size,'sha256':'f'},'generatedFinalOutputSpecularStateAnchor':{'path':str(spec),'file':spec.name,'bytes':spec.stat().st_size,'sha256':'s'}},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v32.v31.run_oat_textured_pipeline;oldbuild=v32.frontier.build;calls=[]
  try:
   v32.v31.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(fd,sp):
    calls.append((fd['format'],sp['format']))
    return {'format':v32.frontier.FORMAT,'materials':[{'material':'*m'}],'summary':{'materialCount':1,'channelCount':4,'channelWithResourceMixCount':3,'materialWithAnyResourceMixCount':1,'nearestResourceNameCounts':{'reflectionProbeSampler':2}},'rowsSha256':'a'*64}
   v32.frontier.build=fake
   result=v32.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v32.v31.run_oat_textured_pipeline=oldrun;v32.frontier.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v32.FORMAT
  assert result['validation']['v32SpecularConsumerFrontierGenerated'] is True
  assert result['validation']['v32SpecularChannelWithResourceMixCount']==3
  assert result['validation']['v32SpecularMaterialWithAnyResourceMixCount']==1
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  side=Path(result['outputs']['generatedFinalOutputSpecularConsumerFrontier']['path']);assert json.loads(side.read_text())['summary']['nearestResourceNameCounts']=={'reflectionProbeSampler':2}
  assert not om.exists()
 print('PASS: production v32 exact specular consumer frontier sidecar');return 0
if __name__=='__main__':raise SystemExit(main())
