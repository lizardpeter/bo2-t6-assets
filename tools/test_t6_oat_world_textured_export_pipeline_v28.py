#!/usr/bin/env python3
from __future__ import annotations

import hashlib,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v28 as pipeline

def rec(p):
 d=p.read_bytes();return {'file':p.name,'path':str(p),'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}

def base(out,with_final=True):
 gb=b'v27-glb\0';gt=b'v27-gltf\n';g=out/'f.world_oat_portable_textured_v27.glb';t=out/'f.world_oat_portable_textured_v27.gltf';m=out/'f.v27.json';g.write_bytes(gb);t.write_bytes(gt);m.write_text('{}\n')
 o={'oatPortableTexturedGlb':rec(g),'oatPortableTexturedGltf':rec(t)}
 if with_final:
  f=out/'f.generated_slot4_final_output_symbolic_v3.json';f.write_text('{"format":"fixture"}\n');o['generatedSlot4FinalOutputSymbolic']=rec(f)
 return {'format':pipeline.v27.FORMAT,'outputs':o,'stats':{'s':27},'validation':{'v27VisualGlbByteIdenticalToV26':True},'policies':{'s':'keep'},'manifest':rec(m)},gb,gt

def anchored():
 return {'format':pipeline.directional.FORMAT,'summary':{'shaderCount':34,'directionalEquationCount':61,'zeroEquationShaderCount':0,'oneEquationShaderCount':7,'twoEquationShaderCount':27,'threeOrMoreEquationShaderCount':0,'anchoredShaderCount':34},'shaders':[]}

def main():
 with tempfile.TemporaryDirectory() as td:
  out=Path(td);b,gb,gt=base(out);oldr=pipeline.v27.run_oat_textured_pipeline;oldb=pipeline.directional.build;calls=[]
  try:
   pipeline.v27.run_oat_textured_pipeline=lambda **kw:b
   pipeline.directional.build=lambda doc,strict=True:(calls.append(strict) or anchored())
   r=pipeline.run_oat_textured_pipeline(map_name='fixture',output_dir=out)
  finally:pipeline.v27.run_oat_textured_pipeline=oldr;pipeline.directional.build=oldb
  assert calls==[True,True];assert r['format']==pipeline.FORMAT;assert r['stats']['s']==27;assert r['policies']['s']=='keep'
  assert r['validation']['v28DirectionalAnchoredShaderCount']==34 and r['validation']['v28DirectionalEquationCount']==61
  assert r['validation']['v28DirectionalZeroEquationShaderCount']==0 and r['validation']['v28DirectionalThreeOrMoreEquationShaderCount']==0
  assert Path(r['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb;assert Path(r['outputs']['oatPortableTexturedGltf']['path']).read_bytes()==gt
  a=Path(r['outputs']['generatedFinalOutputDirectionalLightmapAnchor']['path']);assert json.loads(a.read_text())['format']==pipeline.directional.FORMAT
 with tempfile.TemporaryDirectory() as td:
  out=Path(td);b,gb,_=base(out,False);old=pipeline.v27.run_oat_textured_pipeline
  try:pipeline.v27.run_oat_textured_pipeline=lambda **kw:b;r=pipeline.run_oat_textured_pipeline(map_name='fixture',output_dir=out)
  finally:pipeline.v27.run_oat_textured_pipeline=old
  assert r['validation']['v28DirectionalLightmapAnchorGenerated'] is False;assert Path(r['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
 with tempfile.TemporaryDirectory() as td:
  out=Path(td);b,_,_=base(out);oldr=pipeline.v27.run_oat_textured_pipeline;oldb=pipeline.directional.build
  try:
   pipeline.v27.run_oat_textured_pipeline=lambda **kw:b
   def fail(doc,strict=True):raise pipeline.directional.DirectionalLightmapAnchorV2Error('shader x: directional equation count 0 outside retained 1..2 invariant')
   pipeline.directional.build=fail
   try:pipeline.run_oat_textured_pipeline(map_name='fixture',output_dir=out)
   except pipeline.OatTexturedPipelineV28Error as e:assert 'strict semantic directional-lightmap anchoring failed' in str(e)
   else:raise AssertionError('strict directional failure was swallowed')
  finally:pipeline.v27.run_oat_textured_pipeline=oldr;pipeline.directional.build=oldb
 print('PASS: production v28 semantic directional-lightmap anchor')
 return 0
if __name__=='__main__':raise SystemExit(main())
