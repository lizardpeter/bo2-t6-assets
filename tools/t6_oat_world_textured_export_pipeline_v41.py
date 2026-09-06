#!/usr/bin/env python3
"""Production T6 world export pipeline v41: exact material cbuffer literals.

v41 preserves v40 visual bytes. When the retained expanded world path is
provided alongside final-output/cbuffer proof, it re-reads every generated
MaterialConstantDef directly from the retail world and resolves exact `.tech`
``material.*`` cbuffer sources to per-material float4/scalar values.

Two sidecars are emitted:
- direct generated MaterialConstantDef archive;
- final-output per-material cbuffer values v2.

`code.*`, unassigned and other sources remain unresolved here. No physical
meaning is inferred from constant names or values.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_retail_world_material_constants_v1 as retail_constants
import t6_generated_final_output_material_cbuffer_values_v2 as material_values
import t6_oat_world_textured_export_pipeline_v40 as v40
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v41'
class OatTexturedPipelineV41Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV41Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV41Error(f'{label} does not exist: {p}')
 return p

def run_oat_textured_pipeline(**kw):
 r=v40.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v40.FORMAT:raise OatTexturedPipelineV41Error(f"unexpected v40 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v40 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v41.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v40 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v41.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 expanded=kw.get('generated_shader_expanded_world_path');requested=expanded is not None;values_doc=constants_doc=None
 if requested:
  final_rec=o.get('generatedSlot4FinalOutputSymbolic');cb_rec=o.get('generatedFinalOutputCbufferSignature')
  if not isinstance(final_rec,dict) or not isinstance(cb_rec,dict):raise OatTexturedPipelineV41Error('expanded world was supplied for material cbuffer values but final-output/cbuffer sidecar is missing')
  try:
   c1=retail_constants.build(name,Path(expanded),generated_only=True);c2=retail_constants.build(name,Path(expanded),generated_only=True)
  except Exception as e:raise OatTexturedPipelineV41Error(f'retail generated MaterialConstantDef archive failed: {e}') from e
  cb1=_jb(c1);cb2=_jb(c2)
  if c1!=c2 or cb1!=cb2:raise OatTexturedPipelineV41Error('retail MaterialConstantDef archive regeneration was not byte-identical')
  constants_doc=c1;cp=out/f'{name}.generated_material_constants_v1.json';cp.write_bytes(cb1);o['generatedRetailMaterialConstants']=_rec(cp,cb1)
  fd=json.loads(_path(final_rec,'final-output symbolic sidecar').read_text());cbd=json.loads(_path(cb_rec,'v39 cbuffer signature sidecar').read_text())
  try:v1=material_values.build(fd,cbd,c1);v2doc=material_values.build(fd,cbd,c1)
  except Exception as e:raise OatTexturedPipelineV41Error(f'per-material final-output cbuffer value join failed: {e}') from e
  vb1=_jb(v1);vb2=_jb(v2doc)
  if v1!=v2doc or vb1!=vb2:raise OatTexturedPipelineV41Error('per-material cbuffer value regeneration was not byte-identical')
  values_doc=v1;vp=out/f'{name}.generated_final_output_material_cbuffer_values_v2.json';vp.write_bytes(vb1);o['generatedFinalOutputMaterialCbufferValues']=_rec(vp,vb1)
 cs=None if constants_doc is None else constants_doc['stats'];vs=None if values_doc is None else values_doc['summary']
 r.setdefault('stats',{})['generatedRetailMaterialConstants']=cs;r['stats']['generatedFinalOutputMaterialCbufferValues']=vs
 r.setdefault('validation',{}).update({'v41MaterialCbufferValuesRequested':requested,'v41MaterialCbufferValuesGenerated':values_doc is not None,'v41MaterialCbufferValuesDeterministic':None if values_doc is None else True,'v41GeneratedMaterialConstantArchiveDeterministic':None if constants_doc is None else True,'v41GeneratedMaterialCount':None if cs is None else int(cs['materialCount']),'v41GeneratedMaterialConstantCount':None if cs is None else int(cs['constantCount']),'v41MaterialSourceBindingOccurrenceCount':None if vs is None else int(vs['materialSourceBindingOccurrenceCount']),'v41ResolvedMaterialSourceBindingOccurrenceCount':None if vs is None else int(vs['resolvedMaterialSourceBindingOccurrenceCount']),'v41UnresolvedNonMaterialSourceBindingOccurrenceCount':None if vs is None else int(vs['unresolvedNonMaterialSourceBindingOccurrenceCount']),'v41UniqueMaterialConstantNameCount':None if vs is None else int(vs['uniqueMaterialConstantNameCount']),'v41ShaderCountWithMaterialValueVariation':None if vs is None else int(vs['shaderCountWithMaterialValueVariation']),'v41VisualGlbByteIdenticalToV40':True,'v41VisualGltfByteIdenticalToV40':True if had_gltf else None})
 r.setdefault('policies',{})['v41ExactMaterialCbufferValues']='when retained expanded world is supplied, resolve exact .tech material.* final-output cbuffer sources per generated Material through zero-seed T6 hash plus serialized MaterialConstantDef fragment/hash/literal; shared CSOs do not imply shared values; code.* and other sources remain unresolved; visual bytes unchanged'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v41.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'materialConstants':r['outputs'].get('generatedRetailMaterialConstants'),'materialCbufferValues':r['outputs'].get('generatedFinalOutputMaterialCbufferValues'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
