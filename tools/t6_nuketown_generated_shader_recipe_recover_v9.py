#!/usr/bin/env python3
"""Nuketown generated shader recipe recovery v9: complete normal decode state.

v8 closes exact pre-transform decode for secondary normal layers. v9 reruns the
same exact slot-4 shader through normal decode v2 for every generated recipe and
adds the recurrence baseline too:

* explicit base normalMapSampler.x/y forensic decode DAG, or
* exact zero baseline.

The baseline is independently cross-checked against the retained compound base
component ``n`` marker from v6's normalTransformBindingsV1. Existing v8
secondary-layer decode rows are required to agree byte-for-byte in identity
(hash/resource/mode) with v2 before the v2 payload is attached.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import t6_nuketown_generated_shader_recipe_recover_v8 as v8
import t6_generated_normal_sample_decode_dag_v2 as decode_v2
from t6_dxbc_material_constant_binding_v1 import parse_material_assignments
from t6_generated_shader_recipe_contract_v1 import validate_manifest
from t6_oat_slot_shader_resolver_v1 import resolve_slot_shader

FORMAT="t6-nuketown-generated-shader-recipe-recovery-v9"
NORMAL_STATE_KEY="normalSampleDecodeV2"
class NuketownShaderRecipeRecoveryV9Error(RuntimeError):pass
def _jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _augment_full_normal_state(manifest:dict,*,oat_root:Path)->dict:
 rows=manifest.get("materials")
 if not isinstance(rows,list):raise NuketownShaderRecipeRecoveryV9Error("v8 manifest has no material rows")
 cache={};explicit=zero=base_sample_materials=secondary_layers=0;baseline_hashes=set();all_component_hashes=set()
 for recipe in rows:
  material=str(recipe.get("material") or "");technique=str(recipe.get("techniqueSet") or "")
  cached=cache.get(technique)
  if cached is None:
   resolved=resolve_slot_shader(oat_root,technique,slot_index=4);shaders=resolved.get("pixelShaders",[])
   if len(shaders)!=1:raise NuketownShaderRecipeRecoveryV9Error(f"{technique!r}: non-unique slot-4 pixel shader")
   shader=shaders[0];blob=(Path(oat_root)/shader["relativeFile"]).read_bytes()
   if hashlib.sha256(blob).hexdigest()!=shader["sha256"]:raise NuketownShaderRecipeRecoveryV9Error(f"{technique!r}: pixel shader bytes changed")
   decoded=decode_v2.extract_normal_decode_dags(blob,technique)
   tech_text=(Path(oat_root)/resolved["techniqueFile"]).read_text(encoding="utf-8",errors="strict")
   cached=(decoded,resolved,parse_material_assignments(tech_text));cache[technique]=cached
  decoded,resolved,assignments=cached
  if str(recipe.get("pixelShaderArchetype") or "")!="sha256:"+str(decoded.get("pixelShaderSha256") or ""):raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: v2 normal state shader identity mismatch")
  layout=recipe.get(v8.v7.v6.NORMAL_BINDING_KEY)
  if not isinstance(layout,dict):raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: retained component normal binding missing")
  components=layout.get("components")
  if not isinstance(components,list) or not components:raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: retained component list missing")
  base_has_normal=bool(components[0].get("hasNormal"))
  baseline=decoded.get("baseline")
  if not isinstance(baseline,dict):raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: v2 baseline missing")
  mode=str(baseline.get("mode") or "")
  if base_has_normal and mode!="explicit_normal":raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: base n marker requires explicit normal baseline, got {mode!r}")
  if not base_has_normal and mode!="zero":raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: unmarked base requires zero normal baseline, got {mode!r}")
  if mode=="explicit_normal":
   explicit+=1;base_sample_materials+=1;resource=str(baseline.get("normalResource") or "")
   argument=assignments.get(resource)
   if not resource or argument is None:raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: base normal resource lacks exact .tech material assignment")
   baseline_attached={**baseline,"materialArgument":argument,"portableDependency":{"layerIndex":0,"role":"normalMap"}}
   baseline_hashes.add(str(baseline["decodePairSha256"]))
   for c in baseline["components"]:all_component_hashes.add(str(c["forensicDagSha256"]))
  elif mode=="zero":
   zero+=1;baseline_attached=dict(baseline)
  else:raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: unsupported base normal mode {mode!r}")
  v1_payload=recipe.get(v8.NORMAL_DECODE_KEY);v1_layers=[] if not isinstance(v1_payload,dict) else v1_payload.get("layers",[])
  v2_layers=decoded.get("layers",[])
  if not isinstance(v1_layers,list) or not isinstance(v2_layers,list):raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: malformed secondary normal decode rows")
  a={int(x["layerIndex"]):x for x in v1_layers};b={int(x["layerIndex"]):x for x in v2_layers}
  if set(a)!=set(b):raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: v8/v9 secondary normal layer sets disagree")
  attached_layers=[]
  for layer in sorted(b):
   old,new=a[layer],b[layer]
   for key in ("normalResource","transformMode","decodePairSha256"):
    if old.get(key)!=new.get(key):raise NuketownShaderRecipeRecoveryV9Error(f"{material!r} layer {layer}: v8/v2 {key} disagreement")
   if [x.get("forensicDagSha256") for x in old.get("components",[])]!=[x.get("forensicDagSha256") for x in new.get("components",[])]:raise NuketownShaderRecipeRecoveryV9Error(f"{material!r} layer {layer}: v8/v2 component DAG disagreement")
   attached_layers.append(old);secondary_layers+=1
   for c in new["components"]:all_component_hashes.add(str(c["forensicDagSha256"]))
  payload={"format":"t6-generated-normal-sample-decode-recipe-v2","material":material,"techniqueSet":technique,"pixelShaderArchetype":recipe["pixelShaderArchetype"],"techniqueFile":resolved["techniqueFile"],"baseline":baseline_attached,"layers":attached_layers,"secondaryNormalLayerCount":len(attached_layers),"allDecodeLeavesExact":bool(decoded.get("allDecodeLeavesSampleOnly")),"proof":"exact base_pair baseline + v8 exact secondary decode DAGs; base n marker and .tech normal sampler assignment cross-checked"}
  payload["bindingSha256"]=_jhash(payload);recipe[NORMAL_STATE_KEY]=payload
 rec=manifest.setdefault("recovery",{});rec["baseRecoveryFormat"]=rec.get("format");rec["baseRecipeRowsSha256"]=rec.get("recipeRowsSha256");rec["format"]=FORMAT;rec["producer"]="tools/t6_nuketown_generated_shader_recipe_recover_v9.py";rec["baseExplicitNormalMaterialCount"]=explicit;rec["baseZeroNormalMaterialCount"]=zero;rec["baseNormalSampleMaterialCount"]=base_sample_materials;rec["secondaryNormalDecodeLayerOccurrenceCountV2"]=secondary_layers;rec["uniqueBaseNormalDecodePairDagCount"]=len(baseline_hashes);rec["uniqueAllNormalDecodeComponentDagCount"]=len(all_component_hashes);rec["fullNormalDecodeStateCoverageComplete"]=True;rec["recipeRowsSha256"]=_jhash(rows);rec["proofBoundary"]="v8 exact secondary normal decode + exact base normalMapSampler.x/y baseline or zero, cross-checked against retained base n marker; physical basis attachment remains a separate postpass"
 checked=validate_manifest(manifest)
 for material,row in checked.items():
  if not isinstance(row.get(NORMAL_STATE_KEY),dict):raise NuketownShaderRecipeRecoveryV9Error(f"{material!r}: v2 normal state lost during canonical validation")
 return manifest
def build_from_bindings(bindings:list[dict],*,oat_root:Path,expanded_sha256:str,strict_nuketown:bool=True,**proof_paths)->dict:
 base=v8.build_from_bindings(bindings,oat_root=oat_root,expanded_sha256=expanded_sha256,strict_nuketown=strict_nuketown,**proof_paths);return _augment_full_normal_state(base,oat_root=Path(oat_root))
def recover(*,expanded_world:Path,oat_root:Path,strict_nuketown:bool=True,**proof_paths)->dict:
 base=v8.recover(expanded_world=expanded_world,oat_root=oat_root,strict_nuketown=strict_nuketown,**proof_paths);return _augment_full_normal_state(base,oat_root=Path(oat_root))
def main():
 p=argparse.ArgumentParser();p.add_argument("--expanded-world",type=Path,required=True);p.add_argument("--oat-root",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--relaxed",action="store_true");a=p.parse_args();d=recover(expanded_world=a.expanded_world,oat_root=a.oat_root,strict_nuketown=not a.relaxed);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n");print(json.dumps(d["recovery"],indent=2,sort_keys=True))
if __name__=="__main__":main()
