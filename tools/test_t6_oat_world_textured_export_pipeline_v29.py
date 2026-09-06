#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v29 as pipeline

def rec(p):
 d=p.read_bytes();return {'file':p.name,'path':str(p),'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}
def base(out,full=True):
 gb=b'v28-glb-exact\0';gt=b'v28-gltf-exact\n';g=out/'f.world_oat_portable_textured_v28.glb';t=out/'f.world_oat_portable_textured_v28.gltf';m=out/'f.v28.json';g.write_bytes(gb);t.write_bytes(gt);m.write_text('{}\n');o={'oatPortableTexturedGlb':rec(g),'oatPortableTexturedGltf':rec(t)}
 if full:
  f=out/'f.generated_slot4_final_output_symbolic_v3.json';f.write_text('{"format":"fixture-final"}\n');d=out/'f.generated_final_output_directional_lightmap_anchor_v2.json';d.write_text('{"format":"fixture-directional"}\n');o['generatedSlot4FinalOutputSymbolic']=rec(f);o['generatedFinalOutputDirectionalLightmapAnchor']=rec(d)
 return {'format':pipeline.v28.FORMAT,'outputs':o,'stats':{'s':28},'validation':{'v28VisualGlbByteIdenticalToV27':True},'policies':{'s':'keep'},'manifest':rec(m)},gb,gt
def iodoc():return {'format':pipeline.io_sig.FORMAT,'summary':{'shaderCount':34,'inputSymbolCheckCount':333,'outputRegisterCheckCount':34},'shaders':[]}
def ndoc():return {'format':pipeline.normal_anchor.FORMAT,'summary':{'shaderCount':34,'layeredNormalTargetShaderCount':21,'anchoredLayeredNormalShaderCount':21,'matchedDirectionalEquationCount':21,'missingTargetShaderCount':0,'ambiguousTargetShaderCount':0,'incidentalNonTargetMatchShaderCount':0},'shaders':[]}
def main():
 with tempfile.TemporaryDirectory() as td:
  out=Path(td);oat=out/'oat';oat.mkdir();b,gb,gt=base(out);oldr=pipeline.v28.run_oat_textured_pipeline;oldi=pipeline.io_sig.build;oldn=pipeline.normal_anchor.build;ic=[];nc=[]
  try:
   pipeline.v28.run_oat_textured_pipeline=lambda **kw:b
   pipeline.io_sig.build=lambda fd,**kw:(ic.append(kw) or iodoc())
   pipeline.normal_anchor.build=lambda fd,io,dd,strict=True:(nc.append(strict) or ndoc())
   r=pipeline.run_oat_textured_pipeline(map_name='fixture',output_dir=out,oat_shader_root=oat)
  finally:pipeline.v28.run_oat_textured_pipeline=oldr;pipeline.io_sig.build=oldi;pipeline.normal_anchor.build=oldn
  assert len(ic)==2 and len(nc)==2 and nc==[True,True];assert r['format']==pipeline.FORMAT;assert r['stats']['s']==28;assert r['policies']['s']=='keep'
  assert r['validation']['v29InputSymbolCheckCount']==333;assert r['validation']['v29LayeredNormalTargetShaderCount']==21;assert r['validation']['v29AnchoredLayeredNormalShaderCount']==21;assert r['validation']['v29MissingLayeredNormalTargetShaderCount']==0;assert r['validation']['v29AmbiguousLayeredNormalTargetShaderCount']==0
  assert Path(r['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb;assert Path(r['outputs']['oatPortableTexturedGltf']['path']).read_bytes()==gt
  assert json.loads(Path(r['outputs']['generatedFinalOutputIoSignature']['path']).read_text())['format']==pipeline.io_sig.FORMAT;assert json.loads(Path(r['outputs']['generatedFinalOutputLayeredNormalAnchor']['path']).read_text())['format']==pipeline.normal_anchor.FORMAT
 with tempfile.TemporaryDirectory() as td:
  out=Path(td);b,gb,_=base(out,False);old=pipeline.v28.run_oat_textured_export_pipeline if hasattr(pipeline.v28,'run_oat_textured_export_pipeline') else None;old2=pipeline.v28.run_oat_textured_pipeline
  try:pipeline.v28.run_oat_textured_pipeline=lambda **kw:b;r=pipeline.run_oat_textured_pipeline(map_name='fixture',output_dir=out)
  finally:pipeline.v28.run_oat_textured_pipeline=old2
  assert r['validation']['v29IoSignatureGenerated'] is False and r['validation']['v29LayeredNormalAnchorGenerated'] is False;assert Path(r['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
 with tempfile.TemporaryDirectory() as td:
  out=Path(td);b,_,_=base(out,True);old=pipeline.v28.run_oat_textured_pipeline
  try:
   pipeline.v28.run_oat_textured_pipeline=lambda **kw:b
   try:pipeline.run_oat_textured_pipeline(map_name='fixture',output_dir=out)
   except pipeline.OatTexturedPipelineV29Error as e:assert 'oat_shader_root is unavailable' in str(e)
   else:raise AssertionError('missing exact OAT root accepted')
  finally:pipeline.v28.run_oat_textured_pipeline=old
 print('PASS: production v29 exact I/O semantics and layered-normal final-output joins');return 0
if __name__=='__main__':raise SystemExit(main())
