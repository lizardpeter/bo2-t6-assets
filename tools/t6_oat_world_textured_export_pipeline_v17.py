#!/usr/bin/env python3
"""Production T6 world export pipeline v17: complete generated-normal recipe inputs.

v17 composes two independent advances without changing either historical stage:

* v16 optionally attaches the exact paired-VS world normal/tangent/binormal basis;
* automatic Nuketown recovery is upgraded from v7 to v8, embedding exact
  normalMapSamplerN.x/y pre-transform decode DAGs and exact sampler bindings.

Thus a v17 material can carry exact sample decode, dual-proof transform ownership
and exact physical reconstruction basis in the same canonical recipe.  The GLB
geometry/texture/lightmap/reflection/render-state payload remains v16-derived.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import t6_nuketown_generated_shader_recipe_recover_v8 as recipe_recovery_v8
import t6_oat_world_textured_export_pipeline_v16 as v16
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
FORMAT="t6-oat-world-textured-export-pipeline-manifest-v17"
class OatTexturedPipelineV17Error(RuntimeError): pass
def _sha(x): return hashlib.sha256(x).hexdigest()
def _record(p,data=None):
 p=Path(p);b=p.read_bytes() if data is None else data;return {"file":p.name,"path":str(p),"bytes":len(b),"sha256":_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV17Error(f"missing {label} record")
 p=Path(str(r.get("path") or ""))
 if not p.is_file():raise OatTexturedPipelineV17Error(f"{label} does not exist: {p}")
 return p
def run_oat_textured_pipeline(**kwargs):
 old=v16.v15.recipe_recovery_v7;v16.v15.recipe_recovery_v7=recipe_recovery_v8
 try:r=v16.run_oat_textured_pipeline(**kwargs)
 finally:v16.v15.recipe_recovery_v7=old
 if r.get("format")!="t6-oat-world-textured-export-pipeline-manifest-v16":raise OatTexturedPipelineV17Error(f"unexpected v16 base {r.get('format')!r}")
 rec=r.get("stats",{}).get("generatedShaderRecipeRecovery");auto=isinstance(rec,dict)
 if auto:
  if rec.get("format")!=recipe_recovery_v8.FORMAT:raise OatTexturedPipelineV17Error(f"automatic recipe recovery did not reach v8: {rec.get('format')!r}")
  if not rec.get("normalSampleDecodeCoverageComplete"):raise OatTexturedPipelineV17Error("normal sample decode coverage incomplete")
  if int(rec.get("normalDecodeLayerOccurrenceCount",-1))!=int(rec.get("secondaryNormalLayerCount",-2)):raise OatTexturedPipelineV17Error("normal decode layer count differs from secondary normal layer population")
  if int(rec.get("normalDecodeMaterialCount",-1))!=int(rec.get("secondaryNormalMaterialCount",-2)):raise OatTexturedPipelineV17Error("normal decode material count differs from secondary normal material population")
 basis=r.get("stats",{}).get("generatedNormalBasisAttachment")
 if basis is not None:
  if not basis.get("allSecondaryNormalMaterialsAttached"):raise OatTexturedPipelineV17Error("v16 normal basis attachment is incomplete")
  if auto and int(basis.get("secondaryNormalMaterialCount",-1))!=int(rec.get("secondaryNormalMaterialCount",-2)):raise OatTexturedPipelineV17Error("basis/decode secondary-normal material populations disagree")
 out=Path(kwargs["output_dir"]);name=str(kwargs["map_name"]);outputs=r.get("outputs",{})
 p=_path(outputs.get("oatPortableTexturedGlb"),"v16 GLB");q=out/f"{name}.world_oat_portable_textured_v17.glb";p.replace(q);outputs["oatPortableTexturedGlb"]=_record(q)
 if isinstance(outputs.get("oatPortableTexturedGltf"),dict):
  p=_path(outputs["oatPortableTexturedGltf"],"v16 glTF");q=out/f"{name}.world_oat_portable_textured_v17.gltf";p.replace(q);outputs["oatPortableTexturedGltf"]=_record(q)
 r.setdefault("validation",{}).update({"v17AutomaticRecipeRecoveryUsesV8":auto,"v17NormalSampleDecodeCoverageComplete":None if not auto else True,"v17NormalDecodeMaterialCount":None if not auto else int(rec["normalDecodeMaterialCount"]),"v17NormalDecodeLayerOccurrenceCount":None if not auto else int(rec["normalDecodeLayerOccurrenceCount"]),"v17NormalBasisAndDecodePopulationAgree":None if basis is None or not auto else int(basis["secondaryNormalMaterialCount"])==int(rec["secondaryNormalMaterialCount"])})
 r.setdefault("policies",{})["v17GeneratedNormalPlaybackInputs"]="canonical generated recipe carries exact normal sample decode and dual-proof transform ownership; optional v16 attachment adds exact paired-VS physical N/T/B basis; no generic Normal Map or RG remap assumption"
 oldm=r.pop("manifest",None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get("path") or ""));p.unlink() if p.is_file() else None
 r["format"]=FORMAT;payload=(json.dumps(r,indent=2,sort_keys=True)+"\n").encode();mp=out/f"{name}.world_oat_textured_export_manifest_v17.json";mp.write_bytes(payload);r["manifest"]=_record(mp,payload);return r
def main():
 p=argparse.ArgumentParser();p.add_argument("--map",dest="map_name",required=True);p.add_argument("--surfaces",type=Path,required=True);p.add_argument("--vd0",type=Path,required=True);p.add_argument("--vd1",type=Path,required=True);p.add_argument("--indices",type=Path,required=True);p.add_argument("--materials",type=Path,required=True);p.add_argument("--catalog",type=Path,required=True);p.add_argument("--prefix",type=Path,required=True);p.add_argument("--asset-pointer-base",type=lambda v:int(v,0),required=True);p.add_argument("--oat-material-root",type=Path,required=True);p.add_argument("--oat-shader-root",type=Path);p.add_argument("--dds-root",type=Path,required=True);p.add_argument("--format-registry",type=Path,required=True);p.add_argument("--lightmap-catalog",type=Path);p.add_argument("--reflection-probe-catalog",type=Path);p.add_argument("--generated-shader-recipes",type=Path);p.add_argument("--generated-shader-expanded-world",type=Path);p.add_argument("--generated-normal-basis-proof",type=Path);p.add_argument("--out-dir",type=Path,required=True);p.add_argument("--write-gltf",action="store_true");p.add_argument("--sm-polygon-offset-bias",type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument("--sm-polygon-offset-scale",type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ("unresolved-world-materials","missing-oat-materials","missing-dds","missing-preview-textures","missing-dependency-textures","missing-lightmap-dds","missing-reflection-probe-dds"):p.add_argument("--allow-"+f,action="store_true")
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({"format":r["format"],"glb":r["outputs"]["oatPortableTexturedGlb"],"normalDecode":r.get("stats",{}).get("generatedShaderRecipeRecovery"),"normalBasis":r.get("stats",{}).get("generatedNormalBasisAttachment"),"manifest":r["manifest"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
