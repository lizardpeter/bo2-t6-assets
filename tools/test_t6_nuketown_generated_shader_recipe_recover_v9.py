#!/usr/bin/env python3
from __future__ import annotations
import hashlib,tempfile
from pathlib import Path
import t6_nuketown_generated_shader_recipe_recover_v9 as r

def manifest(sha,base_n=True):
 m="*65n_82n(wpc/base:wpc/layer)" if base_n else "*65_82n(wpc/base:wpc/layer)"
 return {"format":"t6-generated-world-shader-recipe-manifest-v1","materials":[{"material":m,"techniqueSet":"lit_sm_r0c0n0_b1c1n1","pixelShaderArchetype":"sha256:"+sha,"vertexShaderArchetype":"sha256:"+"b"*64,"worldVertFormats":[2 if base_n else 1],"proof":{"x":1},"layerProgram":[{"layerIndex":1,"operation":"blend","weightClass":"alpha_vertex","hasNormal":True,"hasSpecular":False,"xVariant":False,"heightVariant":False}],r.v8.v7.v6.NORMAL_BINDING_KEY:{"components":[{"layerIndex":0,"hasNormal":base_n},{"layerIndex":1,"hasNormal":True}]},r.v8.NORMAL_DECODE_KEY:{"layers":[{"layerIndex":1,"normalResource":"normalMapSampler1","transformMode":"transform2x2" if base_n else "direct","decodePairSha256":"d"*64,"components":[{"component":"x","forensicDagSha256":"e"*64},{"component":"y","forensicDagSha256":"f"*64}]}]}}],"recovery":{"format":r.v8.FORMAT,"recipeRowsSha256":"c"*64}}
def decoded(sha,explicit=True):
 base={"mode":"explicit_normal","normalResource":"normalMapSampler","sampleChannels":["x","y"],"decodePairSha256":"a"*64,"components":[{"component":"x","forensicDagSha256":"1"*64},{"component":"y","forensicDagSha256":"2"*64}]} if explicit else {"mode":"zero","normalResource":None,"sampleChannels":[],"decodePairSha256":None,"components":[]}
 return {"format":r.decode_v2.FORMAT,"techniqueSet":"lit_sm_r0c0n0_b1c1n1","pixelShaderSha256":sha,"baseline":base,"allDecodeLeavesSampleOnly":True,"layers":[{"layerIndex":1,"normalResource":"normalMapSampler1","transformMode":"transform2x2" if explicit else "direct","decodePairSha256":"d"*64,"components":[{"component":"x","forensicDagSha256":"e"*64},{"component":"y","forensicDagSha256":"f"*64}]}]}
def main():
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);(root/"shader_bin").mkdir();(root/"techniques").mkdir();blob=b"DXBC-full-normal";sha=hashlib.sha256(blob).hexdigest();(root/"shader_bin/ps.cso").write_bytes(blob);(root/"techniques/t.tech").write_text("normalMapSampler = material.normalMap;\n")
  oldr,olde=r.resolve_slot_shader,r.decode_v2.extract_normal_decode_dags
  try:
   r.resolve_slot_shader=lambda oat_root,technique,slot_index:{"techniqueFile":"techniques/t.tech","pixelShaders":[{"relativeFile":"shader_bin/ps.cso","sha256":sha}]}
   r.decode_v2.extract_normal_decode_dags=lambda b,t:decoded(sha,True)
   out=r._augment_full_normal_state(manifest(sha,True),oat_root=root)
  finally:r.resolve_slot_shader, r.decode_v2.extract_normal_decode_dags=oldr,olde
  p=out["materials"][0][r.NORMAL_STATE_KEY];assert p["baseline"]["mode"]=="explicit_normal";assert p["baseline"]["materialArgument"]=="normalMap";assert p["baseline"]["portableDependency"]=={"layerIndex":0,"role":"normalMap"};assert p["secondaryNormalLayerCount"]==1
  rec=out["recovery"];assert rec["baseExplicitNormalMaterialCount"]==1 and rec["baseZeroNormalMaterialCount"]==0 and rec["fullNormalDecodeStateCoverageComplete"]
  (root/"techniques/t.tech").write_text("// no base sampler\n")
  try:
   r.resolve_slot_shader=lambda oat_root,technique,slot_index:{"techniqueFile":"techniques/t.tech","pixelShaders":[{"relativeFile":"shader_bin/ps.cso","sha256":sha}]};r.decode_v2.extract_normal_decode_dags=lambda b,t:decoded(sha,False)
   zero=r._augment_full_normal_state(manifest(sha,False),oat_root=root);assert zero["materials"][0][r.NORMAL_STATE_KEY]["baseline"]["mode"]=="zero"
  finally:r.resolve_slot_shader, r.decode_v2.extract_normal_decode_dags=oldr,olde
  try:
   r.resolve_slot_shader=lambda oat_root,technique,slot_index:{"techniqueFile":"techniques/t.tech","pixelShaders":[{"relativeFile":"shader_bin/ps.cso","sha256":sha}]};r.decode_v2.extract_normal_decode_dags=lambda b,t:decoded(sha,False)
   try:r._augment_full_normal_state(manifest(sha,True),oat_root=root)
   except r.NuketownShaderRecipeRecoveryV9Error as exc:assert "base n marker requires explicit normal baseline" in str(exc)
   else:raise AssertionError("base n/shader zero disagreement accepted")
  finally:r.resolve_slot_shader, r.decode_v2.extract_normal_decode_dags=oldr,olde
 print("PASS: Nuketown generated shader recovery v9 complete normal state")
if __name__=="__main__":main()
