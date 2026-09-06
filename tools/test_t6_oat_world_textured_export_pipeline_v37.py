#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v37 as v37

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v37_') as td:
  root=Path(td);old=root/'m_v36.glb';gb=b'UNCHANGED-V36';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  docs={
   'generatedFinalOutputRgbTopology':side('top.json',{'format':'t6-generated-final-output-rgb-topology-v1','shaders':[]}),
   'generatedFinalOutputDiffuseDirectionalProductProbe':side('dd.json',{'format':'t6-generated-final-output-diffuse-directional-product-probe-v1','shaders':[]}),
   'generatedFinalOutputSpecularReflectionJoin':side('sr.json',{'format':'t6-generated-final-output-specular-reflection-join-v1','materials':[]}),
   'generatedSlot4FinalOutputSymbolic':side('final.json',{'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]}),
   'generatedFinalOutputRgbSquareAnchor':side('sq.json',{'format':'t6-generated-final-output-rgb-square-anchor-v1','shaders':[]}),
   'generatedFinalOutputDirectionalLightmapAnchor':side('dir.json',{'format':'t6-generated-final-output-directional-lightmap-anchor-v2','shaders':[]}),
   'generatedFinalOutputSpecularStateAnchor':side('spec.json',{'format':'t6-generated-final-output-specular-state-anchor-v1','materials':[]}),
   'generatedFinalOutputReflectionSampleIndex':side('refl.json',{'format':'t6-generated-final-output-reflection-sample-index-v1','shaders':[]}),
  }
  om=root/'old.json';om.write_text('{}')
  base={'format':v37.v36.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},**docs},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v37.v36.run_oat_textured_pipeline;oldbuild=v37.coverage.build;calls=[]
  try:
   v37.v36.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(*args,strict=False):
    calls.append((len(args),strict))
    return {'format':v37.coverage.FORMAT,'shaders':[{'sha256':'a'*64,'fullyCovered':False}],'summary':{'shaderCount':1,'rgbLaneCount':3,'syntacticLeafCount':5,'coveredLeafCount':4,'unclassifiedLeafCount':1,'fullyCoveredRgbLaneCount':2,'fullyCoveredShaderCount':0,'termFamilyCounts':{'direct_squared_rgb_times_directional':3,'unclassified':1,'standalone_reflection_sample':1},'strict':False},'authoritativeDagPreflight':{'authoritativeShaderCount':1,'nodeReferenceCheckCount':17,'allReferencedNodesExist':True},'rowsSha256':'a'*64,'documentSha256':'b'*64}
   v37.coverage.build=fake
   result=v37.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v37.v36.run_oat_textured_pipeline=oldrun;v37.coverage.build=oldbuild
  assert calls==[(8,False),(8,False)]
  assert result['format']==v37.FORMAT
  assert result['validation']['v37FinalRgbTermCoverageGenerated'] is True
  assert result['validation']['v37FinalRgbSyntacticLeafCount']==5
  assert result['validation']['v37FinalRgbCoveredLeafCount']==4
  assert result['validation']['v37FinalRgbUnclassifiedLeafCount']==1
  assert result['validation']['v37AuthoritativeDagNodeReferenceCheckCount']==17
  assert result['validation']['v37AllReferencedNodesExist'] is True
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  sidepath=Path(result['outputs']['generatedFinalOutputRgbTermCoverage']['path']);assert json.loads(sidepath.read_text())['summary']['unclassifiedLeafCount']==1
  assert not om.exists()
 print('PASS: production v37 exact final RGB term coverage diagnostic');return 0
if __name__=='__main__':raise SystemExit(main())
