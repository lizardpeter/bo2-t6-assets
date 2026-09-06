#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v46 as v46

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v46_') as td:
  root=Path(td);old=root/'m_v45.glb';gb=b'UNCHANGED-V45';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  final=side('final.json',{'format':v46.specialization.v1.FINAL_FORMAT,'materials':[],'shaders':[]})
  resolution=side('resolution.json',{'format':v46.specialization.v1.RESOLUTION_FORMAT,'terms':[],'summary':{}})
  om=root/'old.json';om.write_text('{}')
  base={'format':v46.v45.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputUnclassifiedTermCbufferResolution':resolution},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v46.v45.run_oat_textured_pipeline;oldbuild=v46.specialization.build;calls=[]
  try:
   v46.v45.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(fd,rd):
    calls.append((copy.deepcopy(fd),copy.deepcopy(rd)))
    return {'format':v46.specialization.FORMAT,'baseFormat':v46.specialization.v1.FORMAT,'cbufferCoveragePreflight':{'termCount':1,'rows':[],'rowsSha256':'c'*64},'terms':[{'sha256':'a'*64,'lane':'x','node':3,'materialOwnerCount':2,'distinctSpecializedProfileCount':2,'variesAcrossMaterialOwners':True,'variants':[]}],'specializedProfileGroups':[{'count':1},{'count':1}],'summary':{'termCount':1,'materialVariantCount':2,'termWithMaterialSpecializationVariationCount':1,'uniqueSpecializedProfileCount':2,'fullyMaterialLiteralCbufferVariantCount':0,'variantWithDynamicCodeConstantCount':2,'variantWithUnresolvedCbufferCount':0,'exactCbufferCoverageTermCount':1,'cbufferCoverageRowsSha256':'c'*64},'rowsSha256':'a'*64,'profileGroupsSha256':'b'*64}
   v46.specialization.build=fake
   result=v46.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v46.v45.run_oat_textured_pipeline=oldrun;v46.specialization.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v46.FORMAT
  assert result['validation']['v46UnknownTermSpecializationGenerated'] is True
  assert result['validation']['v46UnknownTermSpecializationDeterministic'] is True
  assert result['validation']['v46ExactCbufferCoverageTermCount']==1
  assert result['validation']['v46MaterialVariantCount']==2
  assert result['validation']['v46TermWithMaterialSpecializationVariationCount']==1
  assert result['validation']['v46UniqueSpecializedProfileCount']==2
  assert result['validation']['v46VariantWithDynamicCodeConstantCount']==2
  assert result['validation']['v46VariantWithUnresolvedCbufferCount']==0
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedFinalOutputUnclassifiedTermSpecialization']['path']).read_text())['terms'][0]['variesAcrossMaterialOwners'] is True
  assert not om.exists()

  # Without a v45 resolution sidecar there is nothing to specialize, and v46
  # remains absent rather than applying raw cbuffer names as if they were values.
  old2=root/'m2_v45.glb';old2.write_bytes(gb);om2=root/'old2.json';om2.write_text('{}')
  optional=copy.deepcopy(base);optional['outputs']['oatPortableTexturedGlb']['path']=str(old2);optional['outputs'].pop('generatedFinalOutputUnclassifiedTermCbufferResolution');optional['manifest']={'path':str(om2)}
  oldrun=v46.v45.run_oat_textured_pipeline
  try:
   v46.v45.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(optional)
   result2=v46.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v46.v45.run_oat_textured_pipeline=oldrun
  assert result2['validation']['v46UnknownTermSpecializationGenerated'] is False
  assert 'generatedFinalOutputUnclassifiedTermSpecialization' not in result2['outputs']

  # Resolution without the authoritative final DAG is an inconsistent state.
  old3=root/'m3_v45.glb';old3.write_bytes(gb);om3=root/'old3.json';om3.write_text('{}')
  broken=copy.deepcopy(base);broken['outputs']['oatPortableTexturedGlb']['path']=str(old3);broken['outputs'].pop('generatedSlot4FinalOutputSymbolic');broken['manifest']={'path':str(om3)}
  oldrun=v46.v45.run_oat_textured_pipeline
  try:
   v46.v45.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(broken)
   try:v46.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
   except v46.OatTexturedPipelineV46Error as exc:assert 'final-output DAG is missing' in str(exc)
   else:raise AssertionError('v46 accepted specialization without authoritative final-output DAG')
  finally:v46.v45.run_oat_textured_pipeline=oldrun
 print('PASS: production v46 exact per-material unknown-term specialization');return 0
if __name__=='__main__':raise SystemExit(main())
