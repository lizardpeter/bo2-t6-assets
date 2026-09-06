#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v44 as v44

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v44_') as td:
  root=Path(td);old=root/'m_v43.glb';gb=b'UNCHANGED-V43';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  census=side('census3.json',{'format':v44.overlay.CENSUS_FORMAT,'terms':[],'summary':{}})
  identity=side('identity.json',{'format':v44.overlay.IDENTITY_FORMAT,'shaders':[],'summary':{}})
  om=root/'old.json';om.write_text('{}')
  base={'format':v44.v43.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedFinalOutputUnclassifiedTermCensusCbufferEnriched':census,'generatedFinalOutputCodeConstantIdentity':identity},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v44.v43.run_oat_textured_pipeline;oldbuild=v44.overlay.build;calls=[]
  try:
   v44.v43.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(c,i):
    calls.append((copy.deepcopy(c),copy.deepcopy(i)))
    return {'format':v44.overlay.FORMAT,'terms':[{'lane':'x','hasCodeConstantDependency':True}],'codeConstantPatternGroups':[{'count':1,'observedLanes':['x']}],'summary':{'termCount':1,'termWithCodeConstantDependencyCount':1,'codeConstantAssignmentOccurrenceCount':2,'arrayCodeConstantAssignmentOccurrenceCount':1,'uniqueCodeConstantAccessorCount':2,'uniqueResolvedCodeEnumValueCount':2,'updateFrequencyAssignmentCounts':{'CUSTOM':1,'RARELY':1},'accessorAssignmentCounts':{'filterTap':1,'sunDiffuse':1},'codeConstantPatternCount':1},'rowsSha256':'a'*64,'patternGroupsSha256':'b'*64}
   v44.overlay.build=fake
   result=v44.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v44.v43.run_oat_textured_pipeline=oldrun;v44.overlay.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v44.FORMAT
  assert result['validation']['v44UnknownTermCodeConstantOverlayGenerated'] is True
  assert result['validation']['v44UnknownTermCodeConstantOverlayDeterministic'] is True
  assert result['validation']['v44TermWithCodeConstantDependencyCount']==1
  assert result['validation']['v44CodeConstantAssignmentOccurrenceCount']==2
  assert result['validation']['v44UniqueCodeConstantAccessorCount']==2
  assert result['validation']['v44UniqueResolvedCodeEnumValueCount']==2
  assert result['validation']['v44CodeConstantPatternCount']==1
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedFinalOutputUnclassifiedTermCodeConstants']['path']).read_text())['terms'][0]['hasCodeConstantDependency'] is True
  assert not om.exists()

  # If v43 had no OAT source root, no code identity exists and v44 remains absent.
  old2=root/'m2_v43.glb';old2.write_bytes(gb);om2=root/'old2.json';om2.write_text('{}')
  optional=copy.deepcopy(base);optional['outputs']['oatPortableTexturedGlb']['path']=str(old2);optional['outputs'].pop('generatedFinalOutputCodeConstantIdentity');optional['manifest']={'path':str(om2)}
  oldrun=v44.v43.run_oat_textured_pipeline
  try:
   v44.v43.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(optional)
   result2=v44.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v44.v43.run_oat_textured_pipeline=oldrun
  assert result2['validation']['v44UnknownTermCodeConstantOverlayGenerated'] is False
  assert 'generatedFinalOutputUnclassifiedTermCodeConstants' not in result2['outputs']

  # Identity without the authoritative unknown-term census is inconsistent.
  old3=root/'m3_v43.glb';old3.write_bytes(gb);om3=root/'old3.json';om3.write_text('{}')
  broken=copy.deepcopy(base);broken['outputs']['oatPortableTexturedGlb']['path']=str(old3);broken['outputs'].pop('generatedFinalOutputUnclassifiedTermCensusCbufferEnriched');broken['manifest']={'path':str(om3)}
  oldrun=v44.v43.run_oat_textured_pipeline
  try:
   v44.v43.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(broken)
   try:v44.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
   except v44.OatTexturedPipelineV44Error as exc:assert 'census is missing' in str(exc)
   else:raise AssertionError('v44 accepted code identity without cbuffer-enriched census')
  finally:v44.v43.run_oat_textured_pipeline=oldrun
 print('PASS: production v44 exact code constants on unknown final RGB terms');return 0
if __name__=='__main__':raise SystemExit(main())
