#!/usr/bin/env python3
"""Production T6 world export pipeline v43: exact code.* constant identities.

v43 preserves v42 visual bytes. When `oat_source_root` is supplied it verifies
the exact pinned OpenAssetTools T6 source-header Git blobs, parses the authoritative
T6 code-constant accessor/enum table, and joins every final-output `.tech code.*`
cbuffer source to its exact MaterialConstantSource numeric identity, array index,
update frequency, optional tech flags and matrix-pair metadata.

No runtime code-constant values are recovered by this stage.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_code_constant_source_table_v1 as code_table
import t6_generated_final_output_code_constant_identity_v1 as code_identity
import t6_oat_world_textured_export_pipeline_v42 as v42
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v43'
class OatTexturedPipelineV43Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV43Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV43Error(f'{label} does not exist: {p}')
 return p

def run_oat_textured_pipeline(**kw):
 base_kw=dict(kw);source_root=base_kw.pop('oat_source_root',None)
 r=v42.run_oat_textured_pipeline(**base_kw)
 if r.get('format')!=v42.FORMAT:raise OatTexturedPipelineV43Error(f"unexpected v42 base manifest {r.get('format')!r}")
 out=Path(base_kw['output_dir']);name=str(base_kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v42 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v43.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v42 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v43.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 table_doc=identity_doc=None;requested=source_root is not None
 if requested:
  cb_rec=o.get('generatedFinalOutputCbufferSignature')
  if not isinstance(cb_rec,dict):raise OatTexturedPipelineV43Error('oat_source_root was supplied but final-output cbuffer signature sidecar is missing')
  try:t1=code_table.build_from_root(Path(source_root),verify_pinned_blobs=True);t2=code_table.build_from_root(Path(source_root),verify_pinned_blobs=True)
  except Exception as e:raise OatTexturedPipelineV43Error(f'pinned T6 code-constant source table generation failed: {e}') from e
  tb1=_jb(t1);tb2=_jb(t2)
  if t1!=t2 or tb1!=tb2:raise OatTexturedPipelineV43Error('T6 code-constant table regeneration was not byte-identical')
  table_doc=t1;tp=out/f'{name}.t6_code_constant_source_table_v1.json';tp.write_bytes(tb1);o['t6CodeConstantSourceTable']=_rec(tp,tb1)
  cbd=json.loads(_path(cb_rec,'v39 final-output cbuffer signature').read_text())
  try:i1=code_identity.build(cbd,t1);i2=code_identity.build(cbd,t1)
  except Exception as e:raise OatTexturedPipelineV43Error(f'final-output code-constant identity join failed: {e}') from e
  ib1=_jb(i1);ib2=_jb(i2)
  if i1!=i2 or ib1!=ib2:raise OatTexturedPipelineV43Error('code-constant identity sidecar regeneration was not byte-identical')
  identity_doc=i1;ip=out/f'{name}.generated_final_output_code_constant_identity_v1.json';ip.write_bytes(ib1);o['generatedFinalOutputCodeConstantIdentity']=_rec(ip,ib1)
 ts=None if table_doc is None else table_doc['summary'];isum=None if identity_doc is None else identity_doc['summary']
 r.setdefault('stats',{})['t6CodeConstantSourceTable']=ts;r['stats']['generatedFinalOutputCodeConstantIdentity']=isum
 r.setdefault('validation',{}).update({'v43CodeConstantIdentityRequested':requested,'v43CodeConstantIdentityGenerated':identity_doc is not None,'v43CodeConstantIdentityDeterministic':None if identity_doc is None else True,'v43PinnedCodeSourceTableDeterministic':None if table_doc is None else True,'v43PinnedTechsetConstantsBlobVerified':None if table_doc is None else table_doc['source']['techsetConstants']['gitBlobSha1']==code_table.CONSTANTS_BLOB,'v43PinnedT6AssetsBlobVerified':None if table_doc is None else table_doc['source']['t6Assets']['gitBlobSha1']==code_table.ASSETS_BLOB,'v43CodeConstantSourceCount':None if ts is None else int(ts['codeConstantSourceCount']),'v43CodeConstantAssignmentCount':None if isum is None else int(isum['codeConstantAssignmentCount']),'v43ArrayCodeConstantAssignmentCount':None if isum is None else int(isum['arrayCodeConstantAssignmentCount']),'v43UniqueCodeConstantAccessorCount':None if isum is None else int(isum['uniqueAccessorCount']),'v43UniqueResolvedCodeEnumValueCount':None if isum is None else int(isum['uniqueResolvedEnumValueCount']),'v43VisualGlbByteIdenticalToV42':True,'v43VisualGltfByteIdenticalToV42':True if had_gltf else None})
 r.setdefault('policies',{})['v43ExactCodeConstantIdentity']='optional oat_source_root must contain exact pinned OAT T6 header blobs; parse authoritative commonCodeConstSources + MaterialConstantSource enum and join every .tech code.* final-output cbuffer assignment to exact numeric enum/array/update-frequency identity; runtime values remain unresolved and visual bytes unchanged'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v43.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--oat-source-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,oat_source_root=a.oat_source_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'codeConstantTable':r['outputs'].get('t6CodeConstantSourceTable'),'codeConstantIdentity':r['outputs'].get('generatedFinalOutputCodeConstantIdentity'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
