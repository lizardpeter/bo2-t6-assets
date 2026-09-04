#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
EXPECTED={
  "crossMapStructuralConflictCount":0,
  "crossMapStructurallyAnchoredPointerCount":60,
  "directVertexShaderOccurrenceCount":64,
  "introRowsSha256":"4f83d066bcf57d05aee3ef7637a44dde183c6e0557782b7a3d4348565497900c",
  "introductionOnlyPointerCount":4,
  "introductionRuleValidationCount":60,
  "introductionRuleValidationFailureCount":0,
  "mapRowsSha256":"5af45d63bad223afc7db2ae18d44852dac2fca458e1a8ec7897ffa47c940fee4",
  "packedVertexShaderOccurrenceCount":5612,
  "pointerRowsSha256":"ad4c02621983d041ee5ed2234263e5d0a16be058312eb3440107bfd39ed003f0",
  "producerProofFailureCount":0,
  "resolvedPackedOccurrenceCount":5612,
  "resolvedPackedPointerCount":64,
  "resolvedTargetProducerOccurrenceCount":5676,
  "resolvedTargetVertexShaderCount":16,
  "retainedMapCount":5,
  "shaRowsSha256":"5366a2f72d6fc0d51e50ce8ea4f9ab0184b1bbda6eb1d7eb18c5b19d5b016e12",
  "surfaceNormalTargetShaderCount":4086,
  "targetPassOccurrenceCount":5676,
  "uniqueTargetPackedPointerCount":64
}
INTRO={
 ("zm_prison",59924156):"05ea231b8599e5947a20e6f557c8805c07ad3aa485872936af4747751d8ff82b",
 ("zm_prison",59953528):"f060751961b1c7f2f188f22ef309d09895d101ff25de8d09933e9b8a5b2ba2be",
 ("zm_tomb",73890528):"05ea231b8599e5947a20e6f557c8805c07ad3aa485872936af4747751d8ff82b",
 ("zm_tomb",73924716):"f060751961b1c7f2f188f22ef309d09895d101ff25de8d09933e9b8a5b2ba2be"
}
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d["format"]=="t6-retail-reflection-probe-packed-vs-alias-v1"
 assert d["summary"]==EXPECTED
 enc=d["encoding"]; assert len(enc["mapTable"])==5 and len(enc["vertexShaderTable"])==16
 assert enc["introductionPatternTable"]==[[4,5,1],[6,8,2]]
 assert len(d["pointerAliases"])==64
 assert sum(x[3] for x in d["pointerAliases"])==5612
 assert sum(x[5] for x in d["pointerAliases"])==60
 assert len(d["resolvedVertexShaderCounts"])==16
 assert sum(x[1] for x in d["resolvedVertexShaderCounts"])==5676
 got={(enc["mapTable"][x[0]],x[2]):enc["vertexShaderTable"][x[4]] for x in d["introductionOnlyAliases"]}
 assert got==INTRO
 assert all(enc["introductionPatternTable"][x[6]] in ([4,5,1],[6,8,2]) for x in d["pointerAliases"])
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--manifest",type=Path,default=Path("manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json"));ap.add_argument("--verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_packed_vs_alias_v1.py"));ap.add_argument("--root",type=Path)
 ap.add_argument("--producer-verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_texcoord5_producer_v1.py"));ap.add_argument("--coordinate-verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_coordinate_v1.py"));ap.add_argument("--mip-verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_mip_v1.py"));ap.add_argument("--weight-verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_weight_v1.py"));ap.add_argument("--angular-verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_angular_v1.py"));ap.add_argument("--semantic-verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_material_semantics_v1.py"));ap.add_argument("--surface-verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_surface_normal_v1.py"));ap.add_argument("--shared-verifier",type=Path,default=Path("tools/t6_retail_reflection_probe_shared_parameter_v1.py"));ap.add_argument("--guard",type=Path,default=Path("tools/t6_retail_lightmap_secondary_rdef_guard_v1.py"));a=ap.parse_args()
 d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,"prod").build(a.root,a.producer_verifier,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.semantic_verifier,a.surface_verifier,a.shared_verifier,a.guard);validate(got);assert got==d,"retail rerun differs from committed packed-VS alias manifest"
 print("PASS: T6 retained reflection packed-VS alias regression")
if __name__=="__main__":main()
