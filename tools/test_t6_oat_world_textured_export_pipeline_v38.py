#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v38 as v38

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v38_') as td:
  root=Path(td);old=root/'m_v37.glb';gb=b'UNCHANGED-V37';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  cov=side('cov.json',{'format':'t6-generated-final-output-rgb-term-coverage-v2','shaders':[],'summary':{'unclassifiedLeafCount':2}});final=side('final.json',{'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]});sq=side('sq.json',{'format':'t6-generated-final-output-rgb-square-anchor-v1','shaders':[]});dd=side('dir.json',{'format':'t6-generated-final-output-directional-lightmap-anchor-v2','shaders':[]});sp=side('spec.json',{'format':'t6-generated-final-output-specular-state-anchor-v1','materials':[]});ri=side('refl.json',{'format':'t6-generated-final-output-reflection-sample-index-v1','shaders':[]})
  om=root/'old.json';om.write_text('{}')
  base={'format':v38.v37.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedFinalOutputRgbTermCoverage':cov,'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputRgbSquareAnchor':sq,'generatedFinalOutputDirectionalLightmapAnchor':dd,'generatedFinalOutputSpecularStateAnchor':sp,'generatedFinalOutputReflectionSampleIndex':ri},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v38.v37.run_oat_textured_pipeline;oldbuild=v38.census.build;calls=[]
  try:
   v38.v37.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(*args):
    calls.append(len(args))
    return {'format':v38.census.FORMAT,'terms':[{'lane':'x'},{'lane':'y'}],'signatureGroups':[{'count':2,'observedLanes':['x','y']}],'summary':{'shaderCount':1,'unclassifiedLeafCount':2,'structuralSignatureCount':1,'v1LaneSpecificStructuralSignatureCount':2,'channelAgnosticGrouping':True,'rootOperationCounts':{'op:mul':2},'anchorAncestrySignatureCounts':{'squareRgb':2},'resourceSignatureCounts':{'unknownSampler':2}},'rowsSha256':'a'*64,'signatureGroupsSha256':'b'*64}
   v38.census.build=fake
   result=v38.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v38.v37.run_oat_textured_pipeline=oldrun;v38.census.build=oldbuild
  assert calls==[6,6]
  assert result['format']==v38.FORMAT
  assert result['validation']['v38UnclassifiedTermCensusGenerated'] is True
  assert result['validation']['v38UnclassifiedLeafCount']==2
  assert result['validation']['v38UnclassifiedStructuralSignatureCount']==1
  assert result['validation']['v38V1LaneSpecificStructuralSignatureCount']==2
  assert result['validation']['v38ChannelAgnosticGrouping'] is True
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  sidepath=Path(result['outputs']['generatedFinalOutputUnclassifiedTermCensus']['path']);assert json.loads(sidepath.read_text())['signatureGroups'][0]['observedLanes']==['x','y']
  assert not om.exists()
 print('PASS: production v38 channel-agnostic unclassified final RGB census');return 0
if __name__=='__main__':raise SystemExit(main())
