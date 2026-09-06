#!/usr/bin/env python3
"""Retail canary: current multiplayer body registry must contain exactly one source-closed full body."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def lm(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
c=lm(ROOT/"tools"/"t6_player_body_target_census_v1.py","bodytargets")
r=lm(ROOT/"tools"/"t6_player_body_identity_registry_v1.py","bodyregistry")
seed_path=ROOT/"manifests"/"nonmap"/"targets"/"mp_player_body_prefix_seeds_v1.json"
proof_path=ROOT/"manifests"/"nonmap"/"retail"/"faction_seals_mp_seal6_smg_full_player_v1.json"
seed=r.load(seed_path); proof=r.load(proof_path)
o=r.build(seed,[(proof_path,proof)],c)
assert o["summary"]=={
 "candidateBodies":30,
 "retailProvenFullBodies":1,
 "unresolvedCandidateBodies":29,
 "retailSkeletonsClosed":1
}
by={x["name"]:x for x in o["bodies"]}
seal=by["c_usa_mp_seal6_smg_fb"]
assert seal["retailIdentityStatus"]=="retail-proven-full-body"
assert seal["retailProof"]["sourceZone"]=="faction_seals_mp"
assert seal["retailProof"]["bones"]==102
assert seal["retailProof"]["rootBones"]==1
assert seal["retailProof"]["surfaces"]==42
assert seal["retailProof"]["sourceFastfileSha256"]=="1a075434760751551158b7d62cc2761649e2d2c7606b27b3bbe066b998b77c88"
assert seal["retailProof"]["expandedSha256"]=="21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30"
assert seal["retailProof"]["skeletonNormalizedJsonSha256"]=="151fdfa7cfbcfa4a27fe0792965a76ba279058c455c937928ef97442227fa426"
assert all(x["retailIdentityStatus"]=="candidate-unresolved" for n,x in by.items() if n!="c_usa_mp_seal6_smg_fb")
print("t6_player_body_identity_registry_retail_v1: PASS (30 candidates, 1 retail-proven, 29 unresolved)")
