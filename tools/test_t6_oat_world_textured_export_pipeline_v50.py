#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v50 as v50

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v50_') as td:
  root=Path(td);old=root/'m_v49.glb';gb=b'UNCHANGED-V49';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  final=side('final.json',{'format':v50.mbind.FINAL_FORMAT});tex=side('tex.json',{'format':v50.mbind.TEXTURE_FORMAT});mat=side('mat.json',{'format':v50.mbind.MATERIAL_FORMAT});oldm=root/'old.json';oldm.write_text('{}')
  base={'format':v50.v49.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputTextureResourceBindingV2':tex,'oatMaterialManifest':mat},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(oldm)}}
  savedrun=v50.v49.run_oat_textured_pipeline;savedbuild=v50.mbind.build;calls=[]
  try:
   v50.v49.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(a,b,c,*,oat_material_root):
    calls.append(str(oat_material_root));return {'format':v50.mbind.FORMAT,'materials':[],'summary':{'materialCount':120,'materialSamplerBindingCount':82,'uniqueMaterialSamplerBindingCount':79,'ambiguousMaterialSamplerBindingCount':3,'allMaterialSamplerBindingsUnique':False,'candidateCountHistogram':{'1':79,'2':3}},'rowsSha256':'a'*64}
   v50.mbind.build=fake
   result=v50.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_material_root=root/'materials')
  finally:v50.v49.run_oat_textured_pipeline=savedrun;v50.mbind.build=savedbuild
  assert calls==[str(root/'materials')]*2
  assert result['format']==v50.FORMAT
  assert result['validation']['v50MaterialSamplerBindingGenerated'] is True
  assert result['validation']['v50MaterialSamplerBindingCount']==82
  assert result['validation']['v50UniqueMaterialSamplerBindingCount']==79
  assert result['validation']['v50AmbiguousMaterialSamplerBindingCount']==3
  assert result['validation']['v50AllMaterialSamplerBindingsUnique'] is False
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedFinalOutputMaterialSamplerBinding']['path']).read_text())['format']==v50.mbind.FORMAT
  assert not oldm.exists()

  # Partial prerequisites are invalid rather than silently skipping the proof.
  old2=root/'n_v49.glb';old2.write_bytes(gb);om2=root/'old2.json';om2.write_text('{}');base2=copy.deepcopy(base);base2['outputs']['oatPortableTexturedGlb']['path']=str(old2);base2['outputs'].pop('oatMaterialManifest');base2['manifest']['path']=str(om2)
  savedrun=v50.v49.run_oat_textured_pipeline
  try:
   v50.v49.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base2)
   try:v50.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020',oat_material_root=root/'materials')
   except v50.OatTexturedPipelineV50Error as exc:assert 'partial v50 material-sampler prerequisites' in str(exc)
   else:raise AssertionError('v50 accepted partial material-sampler prerequisites')
  finally:v50.v49.run_oat_textured_pipeline=savedrun
 print('PASS: production v50 exact per-material sampled-image binding');return 0
if __name__=='__main__':raise SystemExit(main())
