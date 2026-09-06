#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v47 as v47

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v47_') as td:
  root=Path(td);old=root/'m_v46.glb';gb=b'UNCHANGED-V46';old.write_bytes(gb)
  finalp=root/'final.json';finalp.write_text(json.dumps({'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]}))
  oldm=root/'old.json';oldm.write_text('{}')
  base={'format':v47.v46.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':{'path':str(finalp),'file':finalp.name,'bytes':finalp.stat().st_size,'sha256':'f'}},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(oldm)}}
  oldrun=v47.v46.run_oat_textured_pipeline;oldbuild=v47.texbind.build;calls=[]
  try:
   v47.v46.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(doc,*,oat_root):
    calls.append((doc['format'],str(oat_root)))
    return {'format':v47.texbind.FORMAT,'shaders':[],'summary':{'shaderCount':1,'sampledTextureResourceCount':7,'textureSampleNodeCount':13,'sourceClassAssignmentCounts':{'code':2,'material':5},'resourceAssignmentCounts':{},'rowsSha256':'a'*64},'rowsSha256':'a'*64}
   v47.texbind.build=fake
   result=v47.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_shader_root=root/'oat')
  finally:v47.v46.run_oat_textured_pipeline=oldrun;v47.texbind.build=oldbuild
  assert calls==[('t6-generated-slot4-final-output-symbolic-v3',str(root/'oat'))]*2
  assert result['format']==v47.FORMAT
  assert result['validation']['v47TextureResourceBindingGenerated'] is True
  assert result['validation']['v47TextureResourceBindingDeterministic'] is True
  assert result['validation']['v47SampledTextureResourceCount']==7
  assert result['validation']['v47TextureSampleNodeCount']==13
  assert result['validation']['v47VisualGlbByteIdenticalToV46'] is True
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedFinalOutputTextureResourceBinding']['path']).read_text())['format']==v47.texbind.FORMAT
  assert not oldm.exists()

  # A final-output DAG cannot be promoted without the exact OAT slot-4 source tree.
  old2=root/'n_v46.glb';old2.write_bytes(gb);oldm2=root/'old2.json';oldm2.write_text('{}')
  base2=copy.deepcopy(base);base2['outputs']['oatPortableTexturedGlb']['path']=str(old2);base2['manifest']['path']=str(oldm2)
  oldrun=v47.v46.run_oat_textured_pipeline
  try:
   v47.v46.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base2)
   try:v47.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
   except v47.OatTexturedPipelineV47Error as exc:assert 'oat_shader_root is absent' in str(exc)
   else:raise AssertionError('v47 accepted final DAG without exact OAT shader root')
  finally:v47.v46.run_oat_textured_pipeline=oldrun
 print('PASS: production v47 exact final-output texture resource binding');return 0
if __name__=='__main__':raise SystemExit(main())
