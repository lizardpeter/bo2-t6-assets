#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v43 as v43

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v43_') as td:
  root=Path(td);old=root/'m_v42.glb';gb=b'UNCHANGED-V42';old.write_bytes(gb)
  cbp=root/'cb.json';cbp.write_text(json.dumps({'format':v43.code_identity.CBUFFER_FORMAT,'shaders':[]}))
  source=root/'oat_source';source.mkdir()
  om=root/'old.json';om.write_text('{}')
  base={'format':v43.v42.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedFinalOutputCbufferSignature':{'path':str(cbp),'file':cbp.name,'bytes':cbp.stat().st_size,'sha256':'c'}},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v43.v42.run_oat_textured_pipeline;oldtable=v43.code_table.build_from_root;oldidentity=v43.code_identity.build;table_calls=[];identity_calls=[];base_kwargs=[]
  try:
   def fake_base(**kw):
    base_kwargs.append(dict(kw));return copy.deepcopy(base)
   v43.v42.run_oat_textured_pipeline=fake_base
   def fake_table(path,verify_pinned_blobs=True):
    table_calls.append((Path(path),verify_pinned_blobs))
    return {'format':v43.code_table.FORMAT,'source':{'openAssetToolsCommit':v43.code_table.PINNED_OAT_COMMIT,'techsetConstants':{'gitBlobSha1':v43.code_table.CONSTANTS_BLOB},'t6Assets':{'gitBlobSha1':v43.code_table.ASSETS_BLOB}},'rows':[{'accessor':'sunDiffuse'}],'summary':{'codeConstantSourceCount':1,'arraySourceCount':0,'matrixPairSourceCount':0,'updateFrequencyCounts':{'CUSTOM':1},'materialConstantSourceEnumEntryCount':1,'uniqueAccessorCount':1,'rowsSha256':'a'*64},'enumAliasesByValue':{'1':['CONST_SRC_CODE_SUN_DIFFUSE']}}
   def fake_identity(cbuffer,table):
    identity_calls.append((copy.deepcopy(cbuffer),copy.deepcopy(table)))
    return {'format':v43.code_identity.FORMAT,'shaders':[{'sha256':'a'*64,'codeConstantAssignmentCount':1,'assignments':[{'sourceName':'sunDiffuse','resolvedEnumValue':1,'updateFrequency':'CUSTOM','runtimeValueResolved':False}]}],'summary':{'shaderCount':1,'codeConstantAssignmentCount':1,'arrayCodeConstantAssignmentCount':0,'uniqueAccessorCount':1,'uniqueResolvedEnumValueCount':1,'updateFrequencyAssignmentCounts':{'CUSTOM':1},'accessorAssignmentCounts':{'sunDiffuse':1},'rowsSha256':'b'*64},'proofBoundary':'fixture'}
   v43.code_table.build_from_root=fake_table;v43.code_identity.build=fake_identity
   result=v43.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_source_root=source,sentinel='passes-to-base')
  finally:v43.v42.run_oat_textured_pipeline=oldrun;v43.code_table.build_from_root=oldtable;v43.code_identity.build=oldidentity
  assert len(base_kwargs)==1 and base_kwargs[0]['sentinel']=='passes-to-base' and 'oat_source_root' not in base_kwargs[0]
  assert table_calls==[(source,True),(source,True)]
  assert len(identity_calls)==2 and identity_calls[0]==identity_calls[1]
  assert result['format']==v43.FORMAT
  assert result['validation']['v43CodeConstantIdentityRequested'] is True
  assert result['validation']['v43CodeConstantIdentityGenerated'] is True
  assert result['validation']['v43CodeConstantIdentityDeterministic'] is True
  assert result['validation']['v43PinnedCodeSourceTableDeterministic'] is True
  assert result['validation']['v43PinnedTechsetConstantsBlobVerified'] is True
  assert result['validation']['v43PinnedT6AssetsBlobVerified'] is True
  assert result['validation']['v43CodeConstantSourceCount']==1
  assert result['validation']['v43CodeConstantAssignmentCount']==1
  assert result['validation']['v43UniqueCodeConstantAccessorCount']==1
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  idoc=json.loads(Path(result['outputs']['generatedFinalOutputCodeConstantIdentity']['path']).read_text())
  assert idoc['shaders'][0]['assignments'][0]['runtimeValueResolved'] is False
  assert not om.exists()

  # Without an OAT source root the promotion is optional and cannot synthesize
  # enum/update-frequency identity from accessor spelling alone.
  old2=root/'m2_v42.glb';old2.write_bytes(gb);om2=root/'old2.json';om2.write_text('{}')
  optional=copy.deepcopy(base);optional['outputs']['oatPortableTexturedGlb']['path']=str(old2);optional['manifest']={'path':str(om2)}
  oldrun=v43.v42.run_oat_textured_pipeline
  try:
   v43.v42.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(optional)
   result2=v43.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_source_root=None)
  finally:v43.v42.run_oat_textured_pipeline=oldrun
  assert result2['validation']['v43CodeConstantIdentityRequested'] is False
  assert result2['validation']['v43CodeConstantIdentityGenerated'] is False
  assert 'generatedFinalOutputCodeConstantIdentity' not in result2['outputs']

  # A requested source-table join requires the exact cbuffer assignment sidecar.
  old3=root/'m3_v42.glb';old3.write_bytes(gb);om3=root/'old3.json';om3.write_text('{}')
  broken=copy.deepcopy(base);broken['outputs']['oatPortableTexturedGlb']['path']=str(old3);broken['outputs'].pop('generatedFinalOutputCbufferSignature');broken['manifest']={'path':str(om3)}
  oldrun=v43.v42.run_oat_textured_pipeline
  try:
   v43.v42.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(broken)
   try:v43.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_source_root=source)
   except v43.OatTexturedPipelineV43Error as exc:assert 'cbuffer signature sidecar is missing' in str(exc)
   else:raise AssertionError('v43 accepted OAT code table request without cbuffer signature')
  finally:v43.v42.run_oat_textured_pipeline=oldrun
 print('PASS: production v43 exact pinned T6 code-constant identities');return 0
if __name__=='__main__':raise SystemExit(main())
