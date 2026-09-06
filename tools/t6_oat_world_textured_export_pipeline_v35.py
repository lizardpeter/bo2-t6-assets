#!/usr/bin/env python3
"""Production T6 world export pipeline v35: squared-RGB/directional product diagnostic.

v35 preserves v34 visual bytes.  When the exact final-output semantic sidecars
exist it probes for literal two-input MUL nodes between v26 squared generated RGB
and each v28 directional-lightmap RGB equation, with v29 identifying the exact
layered-normal equation.

Absence of a direct MUL is diagnostic and does not fail production; ambiguity in
a purported direct product does fail closed inside the probe.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_generated_final_output_diffuse_directional_product_probe_v1 as probe
import t6_oat_world_textured_export_pipeline_v34 as v34
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v35'
class OatTexturedPipelineV35Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV35Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV35Error(f'{label} does not exist: {p}')
 return p
def run_oat_textured_pipeline(**kw):
 r=v34.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v34.FORMAT:raise OatTexturedPipelineV35Error(f"unexpected v34 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v34 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v35.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v34 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v35.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 final_rec=o.get('generatedSlot4FinalOutputSymbolic');square_rec=o.get('generatedFinalOutputRgbSquareAnchor');dir_rec=o.get('generatedFinalOutputDirectionalLightmapAnchor');normal_rec=o.get('generatedFinalOutputLayeredNormalAnchor');doc=None
 if isinstance(final_rec,dict):
  for rec,label in ((square_rec,'v26 RGB-square'),(dir_rec,'v28 directional'),(normal_rec,'v29 layered-normal')):
   if not isinstance(rec,dict):raise OatTexturedPipelineV35Error(f'final-output DAG exists but {label} sidecar is absent')
  fd=json.loads(_path(final_rec,'final-output symbolic sidecar').read_text());sq=json.loads(_path(square_rec,'RGB-square sidecar').read_text());dd=json.loads(_path(dir_rec,'directional sidecar').read_text());nn=json.loads(_path(normal_rec,'layered-normal sidecar').read_text())
  try:d1=probe.build(fd,sq,dd,nn);d2=probe.build(fd,sq,dd,nn)
  except Exception as e:raise OatTexturedPipelineV35Error(f'diffuse/directional direct-product probing failed: {e}') from e
  b1=_jb(d1);b2=_jb(d2)
  if d1!=d2 or b1!=b2:raise OatTexturedPipelineV35Error('diffuse/directional product probe regeneration was not byte-identical')
  doc=d1;p=out/f'{name}.generated_final_output_diffuse_directional_product_probe_v1.json';p.write_bytes(b1);o['generatedFinalOutputDiffuseDirectionalProductProbe']=_rec(p,b1)
 s=None if doc is None else doc['summary'];r.setdefault('stats',{})['generatedFinalOutputDiffuseDirectionalProductProbe']=s
 r.setdefault('validation',{}).update({'v35DiffuseDirectionalProductProbeGenerated':doc is not None,'v35DiffuseDirectionalProductProbeDeterministic':None if doc is None else True,'v35DirectionalEquationCount':None if s is None else int(s['directionalEquationCount']),'v35DirectProductCount':None if s is None else int(s['directProductCount']),'v35ShaderWithAnyDirectProductCount':None if s is None else int(s['shaderWithAnyDirectProductCount']),'v35LayeredNormalEquationDirectRgbLaneCount':None if s is None else int(s['layeredNormalEquationDirectRgbLaneCount']),'v35LayeredNormalEquationAllRgbDirectProductCount':None if s is None else int(s['layeredNormalEquationAllRgbDirectProductCount']),'v35VisualGlbByteIdenticalToV34':True,'v35VisualGltfByteIdenticalToV34':True if had_gltf else None})
 r.setdefault('policies',{})['v35DiffuseDirectionalProductProbe']='diagnostically search exact final-output DAGs for literal two-input MUL(squareRGB,directionalRGB) nodes and tag which directional equation is the v29 layered-normal equation; no multiplication reassociation and no assumed fallback formula; visual bytes unchanged'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v35.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'diffuseDirectionalProbe':r['outputs'].get('generatedFinalOutputDiffuseDirectionalProductProbe'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
