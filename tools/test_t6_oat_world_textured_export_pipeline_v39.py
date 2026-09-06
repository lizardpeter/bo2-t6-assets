#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v39 as v39

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v39_') as td:
  root=Path(td);old=root/'m_v38.glb';gb=b'UNCHANGED-V38';old.write_bytes(gb)
  final_path=root/'final.json';final_doc={'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[{'sha256':'a'*64,'techniqueSets':['lit_sm_fixture'],'nodes':[]}]};final_path.write_text(json.dumps(final_doc))
  om=root/'old.json';om.write_text('{}')
  base={'format':v39.v38.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':{'path':str(final_path),'file':final_path.name,'bytes':final_path.stat().st_size,'sha256':'f'}},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v39.v38.run_oat_textured_pipeline;oldbuild=v39.cb_sig.build;calls=[]
  try:
   v39.v38.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(final_output,oat_root):
    calls.append((copy.deepcopy(final_output),Path(oat_root)))
    return {'format':v39.cb_sig.FORMAT,'shaders':[{'sha256':'a'*64,'usedCbufferSymbolCount':2,'usedCbufferNodeCount':3,'usedCbufferSymbols':[{'symbol':'cb1[59].x','nodeIds':[4,8],'buffer':{'name':'PerMaterial'},'variable':{'name':'alphaRevealParms1'},'techniqueAssignments':[{'techniqueSet':'lit_sm_fixture','sourceClass':'material','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1'}]},{'symbol':'cb2[3].y','nodeIds':[11],'buffer':{'name':'PerCode'},'variable':{'name':'sunColor'},'techniqueAssignments':[{'techniqueSet':'lit_sm_fixture','sourceClass':'code','sourceExpression':'code.sunColor','sourceName':'sunColor'}]}]}],'summary':{'shaderCount':1,'usedCbufferSymbolCount':2,'usedCbufferNodeCount':3,'uniqueReflectedVariableCount':2,'techniqueAssignmentSourceClassCounts':{'code':1,'material':1}},'rowsSha256':'b'*64,'proofBoundary':'fixture'}
   v39.cb_sig.build=fake
   result=v39.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_shader_root=root/'oat')
  finally:
   v39.v38.run_oat_textured_pipeline=oldrun;v39.cb_sig.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert calls[0][0]==final_doc and calls[0][1]==root/'oat'
  assert result['format']==v39.FORMAT
  assert result['validation']['v39FinalOutputCbufferSignatureGenerated'] is True
  assert result['validation']['v39FinalOutputCbufferSignatureDeterministic'] is True
  assert result['validation']['v39UsedCbufferSymbolCount']==2
  assert result['validation']['v39UsedCbufferNodeCount']==3
  assert result['validation']['v39UniqueReflectedVariableCount']==2
  assert result['validation']['v39VisualGlbByteIdenticalToV38'] is True
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  side=Path(result['outputs']['generatedFinalOutputCbufferSignature']['path'])
  doc=json.loads(side.read_text())
  assert doc['shaders'][0]['usedCbufferSymbols'][0]['variable']['name']=='alphaRevealParms1'
  assert result['stats']['generatedFinalOutputCbufferSignature']['techniqueAssignmentSourceClassCounts']=={'code':1,'material':1}
  assert not om.exists()

  # Final-output proof without the exact OAT root must fail before any cbuffer
  # identity can be fabricated from raw cb register numbers.
  oldrun=v39.v38.run_oat_textured_pipeline
  try:
   v39.v38.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   try:
    v39.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_shader_root=None)
   except v39.OatTexturedPipelineV39Error as exc:
    assert 'oat_shader_root is absent' in str(exc)
   else:
    raise AssertionError('v39 accepted final-output DAG without exact OAT shader root')
  finally:v39.v38.run_oat_textured_pipeline=oldrun
 print('PASS: production v39 exact final-output cbuffer signatures');return 0
if __name__=='__main__':raise SystemExit(main())
