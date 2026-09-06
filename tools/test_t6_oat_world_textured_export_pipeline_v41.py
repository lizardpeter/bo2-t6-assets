#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v41 as v41

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v41_') as td:
  root=Path(td);old=root/'m_v40.glb';gb=b'UNCHANGED-V40';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  final=side('final.json',{'format':v41.material_values.v1.FINAL_FORMAT,'materials':[],'shaders':[]})
  cb=side('cb.json',{'format':v41.material_values.v1.CBUFFER_FORMAT,'shaders':[]})
  expanded=root/'world.expanded.bin';expanded.write_bytes(b'RETAIL-WORLD')
  om=root/'old.json';om.write_text('{}')
  base={'format':v41.v40.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputCbufferSignature':cb},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v41.v40.run_oat_textured_pipeline;oldconst=v41.retail_constants.build;oldvalues=v41.material_values.build;const_calls=[];value_calls=[]
  try:
   v41.v40.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake_constants(name,path,generated_only=False):
    const_calls.append((name,Path(path),generated_only))
    return {'format':v41.retail_constants.FORMAT,'map':name,'source':{'file':Path(path).name,'bytes':11,'sha256':'a'*64},'generatedOnly':generated_only,'materials':[{'material':'*m','constantCount':1,'constants':[]}],'stats':{'materialCount':1,'constantCount':1,'uniqueConstantHashCount':1},'proofBoundary':'fixture'}
   def fake_values(fd,cbd,constants):
    value_calls.append((copy.deepcopy(fd),copy.deepcopy(cbd),copy.deepcopy(constants)))
    return {'format':v41.material_values.FORMAT,'baseFormat':v41.material_values.v1.FORMAT,'materials':[{'material':'*m','pixelShaderSha256':'a'*64,'materialResolvedValueSignatureSha256':'b'*64}],'shaderMaterialValueVariation':[{'pixelShaderSha256':'a'*64,'materialOwnerCount':1,'distinctMaterialValueSignatureCount':1,'variesAcrossMaterialOwners':False,'owners':[]}],'summary':{'materialCount':1,'materialSourceBindingOccurrenceCount':3,'resolvedMaterialSourceBindingOccurrenceCount':3,'unresolvedNonMaterialSourceBindingOccurrenceCount':2,'uniqueMaterialConstantNameCount':2,'uniqueResolvedValueSignatureCount':3,'techniqueAssignmentSourceClassCounts':{'material':3,'code':2},'shaderCountWithMaterialValueVariation':0,'shaderCountWithMultipleMaterialOwners':0,'shaderMaterialValueVariationRowsSha256':'c'*64},'rowsSha256':'d'*64,'proofBoundary':'fixture'}
   v41.retail_constants.build=fake_constants;v41.material_values.build=fake_values
   result=v41.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',generated_shader_expanded_world_path=expanded)
  finally:v41.v40.run_oat_textured_pipeline=oldrun;v41.retail_constants.build=oldconst;v41.material_values.build=oldvalues
  assert const_calls==[('mp_nuketown_2020',expanded,True),('mp_nuketown_2020',expanded,True)]
  assert len(value_calls)==2 and value_calls[0]==value_calls[1]
  assert result['format']==v41.FORMAT
  assert result['validation']['v41MaterialCbufferValuesRequested'] is True
  assert result['validation']['v41MaterialCbufferValuesGenerated'] is True
  assert result['validation']['v41MaterialCbufferValuesDeterministic'] is True
  assert result['validation']['v41GeneratedMaterialConstantArchiveDeterministic'] is True
  assert result['validation']['v41GeneratedMaterialCount']==1
  assert result['validation']['v41GeneratedMaterialConstantCount']==1
  assert result['validation']['v41MaterialSourceBindingOccurrenceCount']==3
  assert result['validation']['v41ResolvedMaterialSourceBindingOccurrenceCount']==3
  assert result['validation']['v41UnresolvedNonMaterialSourceBindingOccurrenceCount']==2
  assert result['validation']['v41UniqueMaterialConstantNameCount']==2
  assert result['validation']['v41ShaderCountWithMaterialValueVariation']==0
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedRetailMaterialConstants']['path']).read_text())['generatedOnly'] is True
  assert json.loads(Path(result['outputs']['generatedFinalOutputMaterialCbufferValues']['path']).read_text())['summary']['resolvedMaterialSourceBindingOccurrenceCount']==3
  assert not om.exists()

  # Without an expanded retail source the promotion remains optional and does
  # not invent material-specific values from shader-level metadata.
  oldrun=v41.v40.run_oat_textured_pipeline
  try:
   base2=copy.deepcopy(base);newold=root/'m2_v40.glb';newold.write_bytes(gb);base2['outputs']['oatPortableTexturedGlb']['path']=str(newold);base2['manifest']={'path':str(root/'old2.json')};Path(base2['manifest']['path']).write_text('{}')
   v41.v40.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base2)
   optional=v41.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',generated_shader_expanded_world_path=None)
  finally:v41.v40.run_oat_textured_pipeline=oldrun
  assert optional['validation']['v41MaterialCbufferValuesRequested'] is False
  assert optional['validation']['v41MaterialCbufferValuesGenerated'] is False
  assert 'generatedFinalOutputMaterialCbufferValues' not in optional['outputs']

  broken=copy.deepcopy(base);broken['outputs'].pop('generatedFinalOutputCbufferSignature');brokenold=root/'m3_v40.glb';brokenold.write_bytes(gb);broken['outputs']['oatPortableTexturedGlb']['path']=str(brokenold);broken['manifest']={'path':str(root/'old3.json')};Path(broken['manifest']['path']).write_text('{}')
  oldrun=v41.v40.run_oat_textured_pipeline
  try:
   v41.v40.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(broken)
   try:v41.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',generated_shader_expanded_world_path=expanded)
   except v41.OatTexturedPipelineV41Error as exc:assert 'final-output/cbuffer sidecar is missing' in str(exc)
   else:raise AssertionError('v41 accepted expanded-world value recovery without exact cbuffer sidecar')
  finally:v41.v40.run_oat_textured_pipeline=oldrun
 print('PASS: production v41 exact per-material final-output cbuffer values');return 0
if __name__=='__main__':raise SystemExit(main())
