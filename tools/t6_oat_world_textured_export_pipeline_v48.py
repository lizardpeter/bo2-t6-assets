#!/usr/bin/env python3
"""Production T6 world export pipeline v48: exact T6 code-sampler identities.

v48 preserves v47 visual bytes. When v47 final-output texture-resource bindings
exist, the pinned OAT T6 MaterialTextureSource/commonCodeSamplerSources table is
parsed from the exact verified source blobs and every code.* sampler RHS is
joined to its exact enum/index/update-frequency/custom-sampler/tech-flag identity.

Runtime resource instances/content and D3D11 sampler behavior remain unresolved.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_code_sampler_source_table_v1 as sampler_table
import t6_generated_final_output_code_sampler_identity_v1 as sampler_identity
import t6_oat_world_textured_export_pipeline_v47 as v47
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v48'
class OatTexturedPipelineV48Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV48Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV48Error(f'{label} does not exist: {p}')
 return p

def run_oat_textured_pipeline(**kw):
 r=v47.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v47.FORMAT:raise OatTexturedPipelineV48Error(f"unexpected v47 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v47 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v48.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v47 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v48.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 bind_rec=o.get('generatedFinalOutputTextureResourceBinding');doc=None;table_doc=None
 if isinstance(bind_rec,dict):
  source_root=kw.get('oat_source_root')
  if source_root is None:raise OatTexturedPipelineV48Error('v47 texture-resource binding exists but oat_source_root is absent for pinned T6 code-sampler identity')
  binding=json.loads(_path(bind_rec,'v47 texture-resource binding').read_text())
  try:
   t1=sampler_table.build_from_root(Path(source_root),verify_pinned_blobs=True);t2=sampler_table.build_from_root(Path(source_root),verify_pinned_blobs=True)
   d1=sampler_identity.build(binding,t1);d2=sampler_identity.build(binding,t2)
  except Exception as e:raise OatTexturedPipelineV48Error(f'final-output T6 code-sampler identity generation failed: {e}') from e
  tb1=_jb(t1);tb2=_jb(t2);b1=_jb(d1);b2=_jb(d2)
  if t1!=t2 or tb1!=tb2:raise OatTexturedPipelineV48Error('pinned T6 code-sampler table regeneration was not byte-identical')
  if d1!=d2 or b1!=b2:raise OatTexturedPipelineV48Error('T6 code-sampler identity regeneration was not byte-identical')
  table_doc=t1;doc=d1;tp=out/f'{name}.t6_code_sampler_source_table_v1.json';tp.write_bytes(tb1);o['t6CodeSamplerSourceTable']=_rec(tp,tb1);p=out/f'{name}.generated_final_output_code_sampler_identity_v1.json';p.write_bytes(b1);o['generatedFinalOutputCodeSamplerIdentity']=_rec(p,b1)
 s=None if doc is None else doc['summary'];ts=None if table_doc is None else table_doc['summary'];r.setdefault('stats',{})['t6CodeSamplerSourceTable']=ts;r['stats']['generatedFinalOutputCodeSamplerIdentity']=s
 r.setdefault('validation',{}).update({'v48CodeSamplerIdentityGenerated':doc is not None,'v48CodeSamplerIdentityDeterministic':None if doc is None else True,'v48PinnedSamplerTableVerified':None if table_doc is None else True,'v48CodeSamplerAssignmentCount':None if s is None else int(s['codeSamplerAssignmentCount']),'v48UniqueCodeSamplerAccessorCount':None if s is None else int(s['uniqueCodeSamplerAccessorCount']),'v48RuntimeSamplerResourceResolvedCount':None if s is None else int(s['runtimeResourceResolvedCount']),'v48VisualGlbByteIdenticalToV47':True,'v48VisualGltfByteIdenticalToV47':True if had_gltf else None})
 r.setdefault('policies',{})['v48FinalOutputCodeSamplerIdentity']='join every v47 .tech code.* texture RHS to exact pinned OAT T6 MaterialTextureSource/commonCodeSamplerSources enum/index/update-frequency/customSampler/techFlags metadata; require exact pinned header blob verification; runtime resource instance/content and D3D11 sampling remain unresolved; visual bytes unchanged'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v48.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--oat-source-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,oat_source_root=a.oat_source_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'codeSamplerIdentity':r['outputs'].get('generatedFinalOutputCodeSamplerIdentity'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
