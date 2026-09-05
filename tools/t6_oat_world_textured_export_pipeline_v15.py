#!/usr/bin/env python3
"""Production T6 world export pipeline v15: dual-proof normal transforms.

v15 preserves the complete v14/v13/v12 portable artifact. Automatic Nuketown
recipe recovery is upgraded from v6 to v7 so each secondary normal transform is
accepted only when the retained Nuketown component/world-layout proof agrees
with exact OAT .tech routing + paired VS ancestry + PS transform dependencies.
Normal-map sampled XY decoding remains separate and is not guessed here.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import t6_nuketown_generated_shader_recipe_recover_v7 as recipe_recovery_v7
import t6_oat_world_textured_export_pipeline_v14 as v14
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
FORMAT="t6-oat-world-textured-export-pipeline-manifest-v15"
class OatTexturedPipelineV15Error(RuntimeError): pass
def _sha(b): return hashlib.sha256(b).hexdigest()
def _record(p,b=None):
 p=Path(p);x=p.read_bytes() if b is None else b;return {"file":p.name,"path":str(p),"bytes":len(x),"sha256":_sha(x)}
def _path(r,label):
 if not isinstance(r,dict): raise OatTexturedPipelineV15Error(f"missing {label} record")
 p=Path(str(r.get("path") or ""))
 if not p.is_file(): raise OatTexturedPipelineV15Error(f"{label} does not exist: {p}")
 return p
def run_oat_textured_pipeline(**kwargs):
 old=v14.recipe_recovery_v6;v14.recipe_recovery_v6=recipe_recovery_v7
 try: result=v14.run_oat_textured_pipeline(**kwargs)
 finally: v14.recipe_recovery_v6=old
 if result.get("format")!="t6-oat-world-textured-export-pipeline-manifest-v14": raise OatTexturedPipelineV15Error(f"unexpected v14 base {result.get('format')!r}")
 recovery=result.get("stats",{}).get("generatedShaderRecipeRecovery");automatic=isinstance(recovery,dict)
 if automatic:
  if recovery.get("format")!=recipe_recovery_v7.FORMAT: raise OatTexturedPipelineV15Error(f"automatic recipe recovery did not reach v7: {recovery.get('format')!r}")
  if not recovery.get("normalTransformCrossProofAgreementComplete"): raise OatTexturedPipelineV15Error("normal transform cross-proof agreement incomplete")
  if int(recovery.get("normalTransformCrossCheckedLayerCount",-1))!=int(recovery.get("secondaryNormalLayerCount",-2)): raise OatTexturedPipelineV15Error("cross-checked normal-layer count differs from recipe population")
 out=Path(kwargs["output_dir"]);name=str(kwargs["map_name"]);outputs=result.get("outputs",{})
 old_glb=_path(outputs.get("oatPortableTexturedGlb"),"v14 GLB");new_glb=out/f"{name}.world_oat_portable_textured_v15.glb";old_glb.replace(new_glb);outputs["oatPortableTexturedGlb"]=_record(new_glb)
 if isinstance(outputs.get("oatPortableTexturedGltf"),dict):
  p=_path(outputs["oatPortableTexturedGltf"],"v14 glTF");q=out/f"{name}.world_oat_portable_textured_v15.gltf";p.replace(q);outputs["oatPortableTexturedGltf"]=_record(q)
 result.setdefault("validation",{}).update({"v15AutomaticRecipeRecoveryUsesV7":automatic,"v15NormalTransformCrossProofAgreementComplete":None if not automatic else True,"v15NormalTransformCrossCheckedMaterialCount":None if not automatic else int(recovery["normalTransformCrossCheckedMaterialCount"]),"v15NormalTransformCrossCheckedLayerCount":None if not automatic else int(recovery["normalTransformCrossCheckedLayerCount"])})
 result.setdefault("policies",{})["v15GeneratedNormalTransforms"]="renderer transform ownership requires agreement between Nuketown retained layout/component proof and exact slot-4 shader routing/VS/PS ancestry; no transform-index convention is assumed"
 oldm=result.pop("manifest",None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get("path") or ""));p.unlink() if p.is_file() else None
 result["format"]=FORMAT;payload=(json.dumps(result,indent=2,sort_keys=True)+"\n").encode();mp=out/f"{name}.world_oat_textured_export_manifest_v15.json";mp.write_bytes(payload);result["manifest"]=_record(mp,payload);return result
def main():
 p=argparse.ArgumentParser();p.add_argument("--map",dest="map_name",required=True);p.add_argument("--surfaces",type=Path,required=True);p.add_argument("--vd0",type=Path,required=True);p.add_argument("--vd1",type=Path,required=True);p.add_argument("--indices",type=Path,required=True);p.add_argument("--materials",type=Path,required=True);p.add_argument("--catalog",type=Path,required=True);p.add_argument("--prefix",type=Path,required=True);p.add_argument("--asset-pointer-base",type=lambda v:int(v,0),required=True);p.add_argument("--oat-material-root",type=Path,required=True);p.add_argument("--oat-shader-root",type=Path);p.add_argument("--dds-root",type=Path,required=True);p.add_argument("--format-registry",type=Path,required=True);p.add_argument("--lightmap-catalog",type=Path);p.add_argument("--reflection-probe-catalog",type=Path);p.add_argument("--generated-shader-recipes",type=Path);p.add_argument("--generated-shader-expanded-world",type=Path);p.add_argument("--out-dir",type=Path,required=True);p.add_argument("--write-gltf",action="store_true");p.add_argument("--sm-polygon-offset-bias",type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument("--sm-polygon-offset-scale",type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for flag in ("unresolved-world-materials","missing-oat-materials","missing-dds","missing-preview-textures","missing-dependency-textures","missing-lightmap-dds","missing-reflection-probe-dds"):p.add_argument("--allow-"+flag,action="store_true")
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({"format":r["format"],"glb":r["outputs"]["oatPortableTexturedGlb"],"manifest":r["manifest"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
