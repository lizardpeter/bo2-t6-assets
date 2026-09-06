#!/usr/bin/env python3
import importlib.util, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location("bodytargets",HERE/"t6_player_body_target_census_v1.py")
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
classes=["assault","lmg","shotgun","smg","sniper"]
seed={
 "format":"t6-player-faction-prefix-seeds-v1",
 "classes":classes,
 "factions":[
  {"faction":"A","prefix":"c_a_mp_alpha","viewhandsEvidence":["c_a_mp_alpha_long_viewhands"]},
  {"faction":"B","prefix":"c_b_mp_beta","viewhandsEvidence":["c_b_mp_beta_smg_viewhands"]}
 ],
 "independentlyEnumeratedBodyNames":["c_a_mp_alpha_smg_fb"]
}
o=m.build(seed)
assert o["summary"]=={
 "factionPrefixes":2,"viewhandsEvidenceIdentities":2,"candidateBodies":10,
 "independentlyEnumeratedDiscoveryTargets":1,"derivedOnlyCandidates":9,
 "requiredTargets":0,"retailResolvedBodies":0
}
by={x["name"]:x for x in o["models"]}
assert by["c_a_mp_alpha_smg_fb"]["nameEvidence"]=="independently-enumerated-discovery-target"
assert by["c_b_mp_beta_sniper_fb"]["nameEvidence"]=="derived-from-retail-viewhands-prefix-and-class-convention"
assert all(x["required"] is False for x in o["models"])
assert all(x["retailIdentityStatus"]=="unresolved-until-exact-xmodel-corpus-hit" for x in o["models"])
bad=json.loads(json.dumps(seed)); bad["independentlyEnumeratedBodyNames"]=["c_a_mp_alpha_medic_fb"]
try:m.build(bad)
except ValueError:pass
else:raise AssertionError("out-of-universe enumeration did not fail")
bad=json.loads(json.dumps(seed)); bad["factions"][0]["viewhandsEvidence"]=["wrong_viewhands"]
try:m.build(bad)
except ValueError:pass
else:raise AssertionError("prefix mismatch did not fail")
print("t6_player_body_target_census_v1: PASS")
