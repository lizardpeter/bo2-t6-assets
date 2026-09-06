#!/usr/bin/env python3
"""Production T6 world export pipeline v31: RGB factor recovery + specular cross-proof.

v31 preserves v30 visual bytes.  When the exact final-output DAG exists it:
1. extracts canonical recipes from the production GLB;
2. recovers every generated RGB A/B/M/T layer factor/condition inside the full
   slot-4 DAG and requires the completed RGB state to equal the v26 pre-square
   anchor;
3. joins every v30 specular step to the RGB step for the same retail material
   and layer and requires exact factor/condition DAG hash equality.

No physical interpretation of the scalar or specular XYZW is introduced.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_generated_final_output_rgb_factor_anchor_v1 as rgb_anchor
import t6_generated_final_output_specular_rgb_factor_join_v1 as factor_join
import t6_oat_world_textured_export_pipeline_v30 as v30
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE

FORMAT='t6-oat-world-textured-export-pipeline-manifest-v31'
class OatTexturedPipelineV31Error(RuntimeError):pass

def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV31Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV31Error(f'{label} does not exist: {p}')
 return p

def run_oat_textured_pipeline(**kw):
 r=v30.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v30.FORMAT:raise OatTexturedPipelineV31Error(f"unexpected v30 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v30 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v31.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v30 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v31.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 final_rec=o.get('generatedSlot4FinalOutputSymbolic');square_rec=o.get('generatedFinalOutputRgbSquareAnchor');spec_rec=o.get('generatedFinalOutputSpecularStateAnchor')
 rgb_doc=join_doc=None
 if isinstance(final_rec,dict):
  if not isinstance(square_rec,dict):raise OatTexturedPipelineV31Error('final-output DAG exists but v26 RGB-square sidecar is absent')
  if not isinstance(spec_rec,dict):raise OatTexturedPipelineV31Error('final-output DAG exists but v30 specular sidecar is absent')
  fd=json.loads(_path(final_rec,'final-output symbolic sidecar').read_text());sq=json.loads(_path(square_rec,'RGB-square sidecar').read_text());sp=json.loads(_path(spec_rec,'specular sidecar').read_text());recipes=v30._embedded_recipe_manifest(gb)
  try:r1=rgb_anchor.build(recipes,fd,sq,strict=True);r2=rgb_anchor.build(recipes,fd,sq,strict=True)
  except Exception as e:raise OatTexturedPipelineV31Error(f'generated RGB factor anchoring failed: {e}') from e
  b1=_jb(r1);b2=_jb(r2)
  if r1!=r2 or b1!=b2:raise OatTexturedPipelineV31Error('RGB factor anchor regeneration was not byte-identical')
  rgb_doc=r1;p=out/f'{name}.generated_final_output_rgb_factor_anchor_v1.json';p.write_bytes(b1);o['generatedFinalOutputRgbFactorAnchor']=_rec(p,b1)
  try:j1=factor_join.build(r1,sp,strict=True);j2=factor_join.build(r1,sp,strict=True)
  except Exception as e:raise OatTexturedPipelineV31Error(f'specular/RGB factor cross-proof failed: {e}') from e
  jb1=_jb(j1);jb2=_jb(j2)
  if j1!=j2 or jb1!=jb2:raise OatTexturedPipelineV31Error('specular/RGB factor join regeneration was not byte-identical')
  join_doc=j1;p=out/f'{name}.generated_final_output_specular_rgb_factor_join_v1.json';p.write_bytes(jb1);o['generatedFinalOutputSpecularRgbFactorJoin']=_rec(p,jb1)
 rs=None if rgb_doc is None else rgb_doc['summary'];js=None if join_doc is None else join_doc['summary']
 r.setdefault('stats',{})['generatedFinalOutputRgbFactorAnchor']=rs;r['stats']['generatedFinalOutputSpecularRgbFactorJoin']=js
 r.setdefault('validation',{}).update({'v31RgbFactorAnchorGenerated':rgb_doc is not None,'v31RgbFactorAnchorDeterministic':None if rgb_doc is None else True,'v31RgbFactorMaterialCount':None if rs is None else int(rs['materialCount']),'v31RgbFactorLayerStepCount':None if rs is None else int(rs['layerStepCount']),'v31RgbFactorFullyMatchedMaterialCount':None if rs is None else int(rs['fullyMatchedMaterialCount']),'v31SpecularRgbFactorJoinGenerated':join_doc is not None,'v31SpecularRgbFactorJoinDeterministic':None if join_doc is None else True,'v31SpecularRgbFactorJoinCheckCount':None if js is None else int(js['factorJoinCheckCount']),'v31SpecularRgbFactorMismatchCount':None if js is None else int(js['mismatchCount']),'v31SpecularRgbFullyMatchedMaterialCount':None if js is None else int(js['fullyMatchedMaterialCount']),'v31VisualGlbByteIdenticalToV30':True,'v31VisualGltfByteIdenticalToV30':True if had_gltf else None})
 r.setdefault('policies',{})['v31ExactSharedGeneratedLayerFactor']='recover the canonical RGB A/B/M/T factor or threshold condition directly from the complete final-output DAG, require the completed RGB state to equal the v26 pre-square anchor, then require every v30 specular b/t step for the same material/layer to use the exact same factor/condition DAG hash; visual bytes unchanged and no PBR semantics assigned'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v31.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'rgbFactors':r['outputs'].get('generatedFinalOutputRgbFactorAnchor'),'specularRgbJoin':r['outputs'].get('generatedFinalOutputSpecularRgbFactorJoin'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
