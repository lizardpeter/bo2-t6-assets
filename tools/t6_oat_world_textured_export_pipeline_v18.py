#!/usr/bin/env python3
"""Production T6 world export pipeline v18: complete generated normal state.

v18 preserves v17's exact optional paired-VS basis attachment and upgrades its
automatic Nuketown recovery implementation from v8 to v9. Canonical recipes now
carry an exact base normal decode/zero baseline plus exact secondary normal
decode/transform state.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_nuketown_generated_shader_recipe_recover_v9 as recipe_recovery_v9
import t6_oat_world_textured_export_pipeline_v17 as v17
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT="t6-oat-world-textured-export-pipeline-manifest-v18"
class OatTexturedPipelineV18Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _rec(p,b=None):p=Path(p);x=p.read_bytes() if b is None else b;return {"file":p.name,"path":str(p),"bytes":len(x),"sha256":_sha(x)}
def _path(r,l):
 if not isinstance(r,dict):raise OatTexturedPipelineV18Error(f"missing {l} record")
 p=Path(str(r.get("path") or ""))
 if not p.is_file():raise OatTexturedPipelineV18Error(f"{l} missing: {p}")
 return p
def run_oat_textured_pipeline(**kwargs):
 old=v17.recipe_recovery_v8;v17.recipe_recovery_v8=recipe_recovery_v9
 try:r=v17.run_oat_textured_pipeline(**kwargs)
 finally:v17.recipe_recovery_v8=old
 if r.get("format")!="t6-oat-world-textured-export-pipeline-manifest-v17":raise OatTexturedPipelineV18Error(f"unexpected v17 base {r.get('format')!r}")
 rec=r.get("stats",{}).get("generatedShaderRecipeRecovery");auto=isinstance(rec,dict)
 if auto:
  if rec.get("format")!=recipe_recovery_v9.FORMAT:raise OatTexturedPipelineV18Error(f"automatic recovery did not reach v9: {rec.get('format')!r}")
  if not rec.get("fullNormalDecodeStateCoverageComplete"):raise OatTexturedPipelineV18Error("full normal decode state coverage incomplete")
  generated=int(rec.get("generatedMaterialCount",-1));explicit=int(rec.get("baseExplicitNormalMaterialCount",-2));zero=int(rec.get("baseZeroNormalMaterialCount",-3))
  if generated<0 or explicit+zero!=generated:raise OatTexturedPipelineV18Error(f"base normal baseline population {explicit}+{zero} != generated {generated}")
 out=Path(kwargs["output_dir"]);name=str(kwargs["map_name"]);outputs=r.get("outputs",{})
 p=_path(outputs.get("oatPortableTexturedGlb"),"v17 GLB");q=out/f"{name}.world_oat_portable_textured_v18.glb";p.replace(q);outputs["oatPortableTexturedGlb"]=_rec(q)
 if isinstance(outputs.get("oatPortableTexturedGltf"),dict):p=_path(outputs["oatPortableTexturedGltf"],"v17 glTF");q=out/f"{name}.world_oat_portable_textured_v18.gltf";p.replace(q);outputs["oatPortableTexturedGltf"]=_rec(q)
 r.setdefault("validation",{}).update({"v18AutomaticRecipeRecoveryUsesV9":auto,"v18FullNormalDecodeStateCoverageComplete":None if not auto else True,"v18BaseExplicitNormalMaterialCount":None if not auto else explicit,"v18BaseZeroNormalMaterialCount":None if not auto else zero,"v18BaseNormalPopulationComplete":None if not auto else explicit+zero==generated})
 r.setdefault("policies",{})["v18GeneratedNormalState"]="exact base normalMapSampler.x/y decode or zero baseline plus exact secondary decode and dual-proof transform ownership; optional v17/v16 basis attachment remains exact"
 oldm=r.pop("manifest",None)
 if isinstance(oldm,dict):p=Path(str(oldm.get("path") or ""));p.unlink() if p.is_file() else None
 r["format"]=FORMAT;payload=(json.dumps(r,indent=2,sort_keys=True)+"\n").encode();mp=out/f"{name}.world_oat_textured_export_manifest_v18.json";mp.write_bytes(payload);r["manifest"]=_rec(mp,payload);return r
def main():
 p=argparse.ArgumentParser();p.add_argument("--map",dest="map_name",required=True);p.add_argument("--surfaces",type=Path,required=True);p.add_argument("--vd0",type=Path,required=True);p.add_argument("--vd1",type=Path,required=True);p.add_argument("--indices",type=Path,required=True);p.add_argument("--materials",type=Path,required=True);p.add_argument("--catalog",type=Path,required=True);p.add_argument("--prefix",type=Path,required=True);p.add_argument("--asset-pointer-base",type=lambda v:int(v,0),required=True);p.add_argument("--oat-material-root",type=Path,required=True);p.add_argument("--oat-shader-root",type=Path);p.add_argument("--dds-root",type=Path,required=True);p.add_argument("--format-registry",type=Path,required=True);p.add_argument("--lightmap-catalog",type=Path);p.add_argument("--reflection-probe-catalog",type=Path);p.add_argument("--generated-shader-recipes",type=Path);p.add_argument("--generated-shader-expanded-world",type=Path);p.add_argument("--generated-normal-basis-proof",type=Path);p.add_argument("--out-dir",type=Path,required=True);p.add_argument("--write-gltf",action="store_true");p.add_argument("--sm-polygon-offset-bias",type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument("--sm-polygon-offset-scale",type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ("unresolved-world-materials","missing-oat-materials","missing-dds","missing-preview-textures","missing-dependency-textures","missing-lightmap-dds","missing-reflection-probe-dds"):p.add_argument("--allow-"+f,action="store_true")
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({"format":r["format"],"glb":r["outputs"]["oatPortableTexturedGlb"],"manifest":r["manifest"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
