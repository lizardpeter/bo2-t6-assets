#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v36 as v36

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v36_') as td:
  root=Path(td);old=root/'m_v35.glb';gb=b'UNCHANGED-V35';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  final=side('final.json',{'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]});sq=side('sq.json',{'format':'t6-generated-final-output-rgb-square-anchor-v1','shaders':[]});dd=side('dir.json',{'format':'t6-generated-final-output-directional-lightmap-anchor-v2','shaders':[]});sp=side('spec.json',{'format':'t6-generated-final-output-specular-state-anchor-v1','materials':[]});ri=side('refl.json',{'format':'t6-generated-final-output-reflection-sample-index-v1','shaders':[]})
  om=root/'old.json';om.write_text('{}')
  base={'format':v36.v35.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputRgbSquareAnchor':sq,'generatedFinalOutputDirectionalLightmapAnchor':dd,'generatedFinalOutputSpecularStateAnchor':sp,'generatedFinalOutputReflectionSampleIndex':ri},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v36.v35.run_oat_textured_pipeline;oldbuild=v36.topology.build;calls=[]
  try:
   v36.v35.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(fd,sq,dd,sp,ri):
    calls.append((fd['format'],sq['format'],dd['format'],sp['format'],ri['format']))
    return {'format':v36.topology.FORMAT,'shaders':[{'sha256':'a'*64}],'summary':{'shaderCount':1,'rgbLaneCount':3,'syntacticAdditiveLeafCount':5,'anchoredImmediateMulLeafCount':3,'leafAnchorSignatureCounts':{'squareRgb+directional:0':3,'specular:x+reflectionProbe':2}},'rowsSha256':'a'*64}
   v36.topology.build=fake
   result=v36.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v36.v35.run_oat_textured_pipeline=oldrun;v36.topology.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v36.FORMAT
  assert result['validation']['v36FinalRgbTopologyGenerated'] is True
  assert result['validation']['v36FinalRgbSyntacticAdditiveLeafCount']==5
  assert result['validation']['v36FinalRgbAnchoredImmediateMulLeafCount']==3
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedFinalOutputRgbTopology']['path']).read_text())['summary']['leafAnchorSignatureCounts']['squareRgb+directional:0']==3
  assert not om.exists()
 print('PASS: production v36 exact final RGB topology sidecar');return 0
if __name__=='__main__':raise SystemExit(main())
