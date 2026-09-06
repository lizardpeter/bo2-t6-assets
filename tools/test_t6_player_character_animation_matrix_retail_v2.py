#!/usr/bin/env python3
"""Retail canary for the current multiplayer third-person character x selector matrix."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def lm(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
pt=lm(ROOT/"tools"/"t6_playeranim_selector_profile_census_v1.py","profiles")
ct=lm(ROOT/"tools"/"t6_player_body_target_census_v1.py","candidates")
br=lm(ROOT/"tools"/"t6_player_body_identity_registry_v1.py","registry")
mx=lm(ROOT/"tools"/"t6_player_character_animation_matrix_v2.py","matrix")
selector_path=ROOT/"manifests"/"nonmap"/"retail"/"common_mp_weapon_playeranim_selector_summary_v1.json"
seed_path=ROOT/"manifests"/"nonmap"/"targets"/"mp_player_body_prefix_seeds_v1.json"
body_proof_path=ROOT/"manifests"/"nonmap"/"retail"/"faction_seals_mp_seal6_smg_full_player_v1.json"
compat_paths=[
 ROOT/"manifests"/"nonmap"/"retail"/"seal6_standard_onfoot_smg_default_playeranim_compatibility_v1.json",
 ROOT/"manifests"/"nonmap"/"retail"/"seal6_standard_onfoot_smg_handleclip_playeranim_compatibility_v1.json",
]
profiles=pt.build(pt.load(selector_path),selector_path)
registry=br.build(br.load(seed_path),[(body_proof_path,br.load(body_proof_path))],ct)
out=mx.build(profiles,registry,[(p,mx.load(p)) for p in compat_paths])
assert out["summary"]=={
 "bodyModels":30,
 "retailProvenBodies":1,
 "unresolvedBodyCandidates":29,
 "selectorProfiles":24,
 "crossProductCells":720,
 "closedCells":2,
 "pendingCompatibilityCells":22,
 "blockedBodyIdentityCells":696,
 "failedProofCells":0
}
cells={(x["bodyModel"],x["profileId"]):x for x in out["cells"]}
assert cells[("c_usa_mp_seal6_smg_fb","standard_onfoot_smg_default_v1")]["status"]=="closed"
assert cells[("c_usa_mp_seal6_smg_fb","standard_onfoot_smg_handleclip_v1")]["status"]=="closed"
assert cells[("c_usa_mp_seal6_smg_fb","standard_onfoot_rifle_default_v1")]["status"]=="pending-no-retained-proof"
assert cells[("c_chn_mp_pla_smg_fb","standard_onfoot_smg_default_v1")]["status"]=="blocked-body-identity-unresolved"
assert sum(x["status"]=="closed" for x in out["cells"] if x["bodyModel"]=="c_usa_mp_seal6_smg_fb")==2
print("t6_player_character_animation_matrix_retail_v2: PASS (30 bodies x 24 profiles = 720; 2 closed, 22 pending, 696 body-blocked)")
