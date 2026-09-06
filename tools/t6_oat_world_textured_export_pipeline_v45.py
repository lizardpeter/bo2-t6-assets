#!/usr/bin/env python3
"""Production T6 world export pipeline v45: cbuffer replay-completeness census.

v45 preserves v44 visual bytes. Whenever the v40 cbuffer-enriched unknown-term
census exists, it combines whichever exact source proofs are available:
- v41 per-material MaterialConstantDef values;
- v43 T6 code-constant enum/update-frequency identities.

It emits, per unknown term/dependency/TechniqueSet, whether source identity and
runtime value are resolved. Missing optional proof inputs are represented as
explicit unavailable resolution kinds, never guessed.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_generated_final_output_unclassified_term_cbuffer_resolution_v1 as resolution
import t6_oat_world_textured_export_pipeline_v44 as v44
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v45'
class OatTexturedPipelineV45Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV45Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV45Error(f'{label} does not exist: {p}')
 return p

def run_oat_textured_pipeline(**kw):
 r=v44.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v44.FORMAT:raise OatTexturedPipelineV45Error(f"unexpected v44 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v44 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v45.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v44 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v45.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 census_rec=o.get('generatedFinalOutputUnclassifiedTermCensusCbufferEnriched');doc=None
 if isinstance(census_rec,dict):
  census=json.loads(_path(census_rec,'v40 cbuffer-enriched unknown-term census').read_text())
  values_rec=o.get('generatedFinalOutputMaterialCbufferValues');code_rec=o.get('generatedFinalOutputCodeConstantIdentity')
  values=None if not isinstance(values_rec,dict) else json.loads(_path(values_rec,'v41 material cbuffer values').read_text())
  code=None if not isinstance(code_rec,dict) else json.loads(_path(code_rec,'v43 code-constant identity').read_text())
  try:d1=resolution.build(census,values,code);d2=resolution.build(census,values,code)
  except Exception as e:raise OatTexturedPipelineV45Error(f'unknown-term cbuffer resolution census failed: {e}') from e
  b1=_jb(d1);b2=_jb(d2)
  if d1!=d2 or b1!=b2:raise OatTexturedPipelineV45Error('cbuffer resolution census regeneration was not byte-identical')
  doc=d1;p=out/f'{name}.generated_final_output_unclassified_term_cbuffer_resolution_v1.json';p.write_bytes(b1);o['generatedFinalOutputUnclassifiedTermCbufferResolution']=_rec(p,b1)
 s=None if doc is None else doc['summary'];r.setdefault('stats',{})['generatedFinalOutputUnclassifiedTermCbufferResolution']=s
 r.setdefault('validation',{}).update({'v45UnknownTermCbufferResolutionGenerated':doc is not None,'v45UnknownTermCbufferResolutionDeterministic':None if doc is None else True,'v45TermCount':None if s is None else int(s['termCount']),'v45CbufferDependencyCount':None if s is None else int(s['cbufferDependencyCount']),'v45TermWithAllCbufferSourceIdentitiesResolvedCount':None if s is None else int(s['termWithAllCbufferSourceIdentitiesResolvedCount']),'v45TermWithAllCbufferRuntimeValuesResolvedCount':None if s is None else int(s['termWithAllCbufferRuntimeValuesResolvedCount']),'v45DependencyWithAllSourceIdentitiesResolvedCount':None if s is None else int(s['dependencyWithAllSourceIdentitiesResolvedCount']),'v45DependencyWithAllRuntimeValuesResolvedCount':None if s is None else int(s['dependencyWithAllRuntimeValuesResolvedCount']),'v45MaterialValuesInputAvailable':None if s is None else bool(s['materialValuesInputAvailable']),'v45CodeIdentityInputAvailable':None if s is None else bool(s['codeIdentityInputAvailable']),'v45VisualGlbByteIdenticalToV44':True,'v45VisualGltfByteIdenticalToV44':True if had_gltf else None})
 r.setdefault('policies',{})['v45UnknownTermCbufferReplayBoundary']='for each unknown-term cbuffer dependency and exact TechniqueSet assignment, classify material.* as retail-value resolved when v41 exists, code.* as exact T6 identity but runtime-dynamic when v43 exists, and unavailable/other sources explicitly; no missing source/value is guessed; visual bytes unchanged'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v45.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--oat-source-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,oat_source_root=a.oat_source_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'cbufferResolution':r['outputs'].get('generatedFinalOutputUnclassifiedTermCbufferResolution'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
