#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v35 as v35

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v35_') as td:
  root=Path(td);old=root/'m_v34.glb';gb=b'UNCHANGED-V34';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  final=side('final.json',{'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]});square=side('sq.json',{'format':'t6-generated-final-output-rgb-square-anchor-v1','shaders':[]});direc=side('dir.json',{'format':'t6-generated-final-output-directional-lightmap-anchor-v2','shaders':[]});normal=side('norm.json',{'format':'t6-generated-final-output-layered-normal-anchor-v1','shaders':[]})
  om=root/'old.json';om.write_text('{}')
  base={'format':v35.v34.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputRgbSquareAnchor':square,'generatedFinalOutputDirectionalLightmapAnchor':direc,'generatedFinalOutputLayeredNormalAnchor':normal},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v35.v34.run_oat_textured_pipeline;oldbuild=v35.probe.build;calls=[]
  try:
   v35.v34.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(fd,sq,dd,nn):
    calls.append((fd['format'],sq['format'],dd['format'],nn['format']))
    return {'format':v35.probe.FORMAT,'shaders':[{'sha256':'a'*64}],'summary':{'shaderCount':1,'directionalEquationCount':2,'directProductCount':3,'shaderWithAnyDirectProductCount':1,'layeredNormalEquationDirectRgbLaneCount':3,'layeredNormalEquationAllRgbDirectProductCount':1},'rowsSha256':'a'*64}
   v35.probe.build=fake
   result=v35.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v35.v34.run_oat_textured_pipeline=oldrun;v35.probe.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v35.FORMAT
  assert result['validation']['v35DiffuseDirectionalProductProbeGenerated'] is True
  assert result['validation']['v35DirectProductCount']==3
  assert result['validation']['v35LayeredNormalEquationAllRgbDirectProductCount']==1
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedFinalOutputDiffuseDirectionalProductProbe']['path']).read_text())['summary']['directionalEquationCount']==2
  assert not om.exists()
 print('PASS: production v35 diffuse-directional direct product diagnostic');return 0
if __name__=='__main__':raise SystemExit(main())
