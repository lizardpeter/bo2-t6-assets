#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v42 as v42

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v42_') as td:
  root=Path(td);old=root/'m_v41.glb';gb=b'UNCHANGED-V41';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  census=side('census3.json',{'format':v42.overlay.CENSUS_FORMAT,'terms':[],'summary':{}})
  values=side('values2.json',{'format':v42.overlay.VALUES_FORMAT,'materials':[],'summary':{}})
  om=root/'old.json';om.write_text('{}')
  base={'format':v42.v41.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedFinalOutputUnclassifiedTermCensusCbufferEnriched':census,'generatedFinalOutputMaterialCbufferValues':values},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v42.v41.run_oat_textured_pipeline;oldbuild=v42.overlay.build;calls=[]
  try:
   v42.v41.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(c,v):
    calls.append((copy.deepcopy(c),copy.deepcopy(v)))
    return {'format':v42.overlay.FORMAT,'terms':[{'lane':'x','hasResolvedMaterialValue':True,'hasMaterialValueVariation':True}],'materialValuePatternGroups':[{'count':1,'observedLanes':['x']}],'summary':{'termCount':1,'termWithResolvedMaterialValueCount':1,'termWithMaterialValueVariationCount':1,'varyingMaterialDependencyCount':1,'uniformResolvedMaterialDependencyCount':0,'materialValuePatternCount':1,'sourceClassOwnerOccurrenceCounts':{'material':2},'materialOwnerCount':2,'shaderCount':1},'rowsSha256':'a'*64,'patternGroupsSha256':'b'*64}
   v42.overlay.build=fake
   result=v42.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v42.v41.run_oat_textured_pipeline=oldrun;v42.overlay.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v42.FORMAT
  assert result['validation']['v42UnknownTermMaterialValueOverlayGenerated'] is True
  assert result['validation']['v42UnknownTermMaterialValueOverlayDeterministic'] is True
  assert result['validation']['v42TermWithResolvedMaterialValueCount']==1
  assert result['validation']['v42TermWithMaterialValueVariationCount']==1
  assert result['validation']['v42VaryingMaterialDependencyCount']==1
  assert result['validation']['v42MaterialValuePatternCount']==1
  assert result['validation']['v42VisualGlbByteIdenticalToV41'] is True
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  overlay_doc=json.loads(Path(result['outputs']['generatedFinalOutputUnclassifiedTermMaterialValues']['path']).read_text())
  assert overlay_doc['terms'][0]['hasMaterialValueVariation'] is True
  assert not om.exists()

  # If v41 did not have an expanded world, no values sidecar exists and v42 must
  # remain absent rather than infer values from the cbuffer variable names.
  old2=root/'m2_v41.glb';old2.write_bytes(gb);om2=root/'old2.json';om2.write_text('{}')
  optional=copy.deepcopy(base);optional['outputs']['oatPortableTexturedGlb']['path']=str(old2);optional['outputs'].pop('generatedFinalOutputMaterialCbufferValues');optional['manifest']={'path':str(om2)}
  oldrun=v42.v41.run_oat_textured_pipeline
  try:
   v42.v41.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(optional)
   result2=v42.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v42.v41.run_oat_textured_pipeline=oldrun
  assert result2['validation']['v42UnknownTermMaterialValueOverlayGenerated'] is False
  assert 'generatedFinalOutputUnclassifiedTermMaterialValues' not in result2['outputs']

  # Conversely, exact material values without the cbuffer-enriched census are an
  # inconsistent production state and must fail closed.
  old3=root/'m3_v41.glb';old3.write_bytes(gb);om3=root/'old3.json';om3.write_text('{}')
  broken=copy.deepcopy(base);broken['outputs']['oatPortableTexturedGlb']['path']=str(old3);broken['outputs'].pop('generatedFinalOutputUnclassifiedTermCensusCbufferEnriched');broken['manifest']={'path':str(om3)}
  oldrun=v42.v41.run_oat_textured_pipeline
  try:
   v42.v41.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(broken)
   try:v42.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
   except v42.OatTexturedPipelineV42Error as exc:assert 'census is missing' in str(exc)
   else:raise AssertionError('v42 accepted material values without the exact unknown-term census')
  finally:v42.v41.run_oat_textured_pipeline=oldrun
 print('PASS: production v42 unknown-term exact material-value overlay');return 0
if __name__=='__main__':raise SystemExit(main())
