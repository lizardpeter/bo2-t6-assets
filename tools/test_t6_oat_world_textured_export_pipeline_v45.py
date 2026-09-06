#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v45 as v45

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v45_') as td:
  root=Path(td);old=root/'m_v44.glb';gb=b'UNCHANGED-V44';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  census=side('census3.json',{'format':v45.resolution.CENSUS_FORMAT,'terms':[],'summary':{}})
  values=side('values2.json',{'format':v45.resolution.VALUES_FORMAT,'materials':[],'summary':{}})
  code=side('code.json',{'format':v45.resolution.CODE_FORMAT,'shaders':[],'summary':{}})
  om=root/'old.json';om.write_text('{}')
  base={'format':v45.v44.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedFinalOutputUnclassifiedTermCensusCbufferEnriched':census,'generatedFinalOutputMaterialCbufferValues':values,'generatedFinalOutputCodeConstantIdentity':code},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v45.v44.run_oat_textured_pipeline;oldbuild=v45.resolution.build;calls=[]
  try:
   v45.v44.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(c,m,k):
    calls.append((copy.deepcopy(c),copy.deepcopy(m),copy.deepcopy(k)))
    return {'format':v45.resolution.FORMAT,'terms':[{'lane':'x','allCbufferSourceIdentitiesResolved':True,'allCbufferRuntimeValuesResolved':False}],'summary':{'termCount':1,'cbufferDependencyCount':2,'termWithAllCbufferSourceIdentitiesResolvedCount':1,'termWithAllCbufferRuntimeValuesResolvedCount':0,'dependencyWithAllSourceIdentitiesResolvedCount':2,'dependencyWithAllRuntimeValuesResolvedCount':1,'sourceClassAssignmentCounts':{'code':1,'material':1},'resolutionKindAssignmentCounts':{'retail_material_constant':1,'t6_code_constant_dynamic':1},'materialValuesInputAvailable':m is not None,'codeIdentityInputAvailable':k is not None},'rowsSha256':'a'*64}
   v45.resolution.build=fake
   result=v45.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v45.v44.run_oat_textured_pipeline=oldrun;v45.resolution.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v45.FORMAT
  assert result['validation']['v45UnknownTermCbufferResolutionGenerated'] is True
  assert result['validation']['v45UnknownTermCbufferResolutionDeterministic'] is True
  assert result['validation']['v45TermCount']==1 and result['validation']['v45CbufferDependencyCount']==2
  assert result['validation']['v45TermWithAllCbufferSourceIdentitiesResolvedCount']==1
  assert result['validation']['v45TermWithAllCbufferRuntimeValuesResolvedCount']==0
  assert result['validation']['v45DependencyWithAllSourceIdentitiesResolvedCount']==2
  assert result['validation']['v45DependencyWithAllRuntimeValuesResolvedCount']==1
  assert result['validation']['v45MaterialValuesInputAvailable'] is True
  assert result['validation']['v45CodeIdentityInputAvailable'] is True
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert not om.exists()

  # Optional inputs are passed as None and must be represented by the resolution
  # tool rather than causing the production wrapper to invent values/identities.
  old2=root/'m2_v44.glb';old2.write_bytes(gb);om2=root/'old2.json';om2.write_text('{}')
  degraded=copy.deepcopy(base);degraded['outputs']['oatPortableTexturedGlb']['path']=str(old2);degraded['outputs'].pop('generatedFinalOutputMaterialCbufferValues');degraded['outputs'].pop('generatedFinalOutputCodeConstantIdentity');degraded['manifest']={'path':str(om2)}
  seen=[];oldrun=v45.v44.run_oat_textured_export_pipeline if hasattr(v45.v44,'run_oat_textured_export_pipeline') else None
  oldbase=v45.v44.run_oat_textured_pipeline;oldbuild=v45.resolution.build
  try:
   v45.v44.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(degraded)
   def fake_degraded(c,m,k):
    seen.append((m,k));return {'format':v45.resolution.FORMAT,'terms':[],'summary':{'termCount':0,'cbufferDependencyCount':0,'termWithAllCbufferSourceIdentitiesResolvedCount':0,'termWithAllCbufferRuntimeValuesResolvedCount':0,'dependencyWithAllSourceIdentitiesResolvedCount':0,'dependencyWithAllRuntimeValuesResolvedCount':0,'sourceClassAssignmentCounts':{},'resolutionKindAssignmentCounts':{},'materialValuesInputAvailable':False,'codeIdentityInputAvailable':False},'rowsSha256':'b'*64}
   v45.resolution.build=fake_degraded
   result2=v45.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v45.v44.run_oat_textured_pipeline=oldbase;v45.resolution.build=oldbuild
  assert seen==[(None,None),(None,None)]
  assert result2['validation']['v45MaterialValuesInputAvailable'] is False
  assert result2['validation']['v45CodeIdentityInputAvailable'] is False

  # Without the authoritative unknown-term census there is nothing to classify.
  old3=root/'m3_v44.glb';old3.write_bytes(gb);om3=root/'old3.json';om3.write_text('{}')
  no_census=copy.deepcopy(base);no_census['outputs']['oatPortableTexturedGlb']['path']=str(old3);no_census['outputs'].pop('generatedFinalOutputUnclassifiedTermCensusCbufferEnriched');no_census['manifest']={'path':str(om3)}
  oldbase=v45.v44.run_oat_textured_pipeline
  try:
   v45.v44.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(no_census)
   result3=v45.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v45.v44.run_oat_textured_pipeline=oldbase
  assert result3['validation']['v45UnknownTermCbufferResolutionGenerated'] is False
  assert 'generatedFinalOutputUnclassifiedTermCbufferResolution' not in result3['outputs']
 print('PASS: production v45 unknown-term cbuffer replay completeness');return 0
if __name__=='__main__':raise SystemExit(main())
