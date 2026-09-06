#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v49 as v49

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v49_') as td:
  root=Path(td);old=root/'m_v46.glb';gb=b'UNCHANGED-V46';old.write_bytes(gb);finalp=root/'final.json';finalp.write_text(json.dumps({'format':'t6-generated-slot4-final-output-symbolic-v3'}));oldm=root/'old.json';oldm.write_text('{}')
  base={'format':v49.v46.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':{'path':str(finalp),'file':finalp.name,'bytes':finalp.stat().st_size,'sha256':'f'}},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(oldm)}}
  cbuf={'format':v49.cb2.FORMAT,'summary':{'techniqueAssignmentCount':2}};tex={'format':v49.tb2.FORMAT,'summary':{'unassignedTechniqueBindingCount':1}};ct={'format':v49.const_table.FORMAT,'summary':{}};st={'format':v49.sampler_table.FORMAT,'summary':{}};ci={'format':v49.cid2.FORMAT,'summary':{'explicitCodeConstantAssignmentCount':2,'implicitSameAccessorCodeConstantAssignmentCount':1}};si={'format':v49.sid2.FORMAT,'summary':{'explicitCodeSamplerAssignmentCount':1,'implicitSameAccessorCodeSamplerAssignmentCount':1,'unresolvedUnassignedSamplerBindingCount':0}}
  saved=(v49.v46.run_oat_textured_pipeline,v49.cb2.build,v49.tb2.build,v49.const_table.build_from_root,v49.sampler_table.build_from_root,v49.cid2.build,v49.sid2.build);calls=[]
  try:
   v49.v46.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   v49.cb2.build=lambda final,rootp:(calls.append('cb') or copy.deepcopy(cbuf))
   v49.tb2.build=lambda final,*,oat_root:(calls.append('tb') or copy.deepcopy(tex))
   v49.const_table.build_from_root=lambda rootp,verify_pinned_blobs=True:(calls.append('ct') or copy.deepcopy(ct))
   v49.sampler_table.build_from_root=lambda rootp,verify_pinned_blobs=True:(calls.append('st') or copy.deepcopy(st))
   v49.cid2.build=lambda a,b:(calls.append('ci') or copy.deepcopy(ci))
   v49.sid2.build=lambda a,b:(calls.append('si') or copy.deepcopy(si))
   result=v49.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_shader_root=root/'shader',oat_source_root=root/'source')
  finally:
   v49.v46.run_oat_textured_pipeline,v49.cb2.build,v49.tb2.build,v49.const_table.build_from_root,v49.sampler_table.build_from_root,v49.cid2.build,v49.sid2.build=saved
  assert calls==['cb','cb','tb','tb','ct','ct','st','st','ci','ci','si','si']
  assert result['format']==v49.FORMAT and Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert result['validation']['v49CorrectedArgumentProvenanceGenerated'] is True
  assert result['validation']['v49ImplicitSameAccessorCodeConstantAssignmentCount']==1
  assert result['validation']['v49ImplicitSameAccessorCodeSamplerAssignmentCount']==1
  assert result['validation']['v49UnresolvedUnassignedSamplerBindingCount']==0
  assert 'generatedFinalOutputCbufferSignatureV2' in result['outputs'] and 'generatedFinalOutputCodeSamplerIdentityV2' in result['outputs']
  assert not oldm.exists()

  old2=root/'n_v46.glb';old2.write_bytes(gb);om2=root/'old2.json';om2.write_text('{}');base2=copy.deepcopy(base);base2['outputs']['oatPortableTexturedGlb']['path']=str(old2);base2['manifest']['path']=str(om2)
  savedrun=v49.v46.run_oat_textured_pipeline
  try:
   v49.v46.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base2)
   try:v49.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_shader_root=root/'shader')
   except v49.OatTexturedPipelineV49Error as exc:assert 'oat_source_root is absent' in str(exc)
   else:raise AssertionError('v49 accepted final DAG without pinned OAT source root')
  finally:v49.v46.run_oat_textured_pipeline=savedrun
 print('PASS: production v49 corrected OAT argument provenance');return 0
if __name__=='__main__':raise SystemExit(main())
