#!/usr/bin/env python3
"""Lock the normalized six-faction, 30-body multiplayer discovery target universe."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools"/"t6_player_body_target_census_v1.py"
SEEDS=ROOT/"manifests"/"nonmap"/"targets"/"mp_player_body_prefix_seeds_v1.json"
s=importlib.util.spec_from_file_location("bodytargets",TOOL)
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
expected=m.build(m.load(SEEDS))
assert expected["summary"]=={
 "factionPrefixes":6,
 "viewhandsEvidenceIdentities":18,
 "candidateBodies":30,
 "independentlyEnumeratedDiscoveryTargets":10,
 "derivedOnlyCandidates":20,
 "requiredTargets":0,
 "retailResolvedBodies":0
}
by={x["name"]:x for x in expected["models"]}
assert by["c_usa_mp_seal6_smg_fb"]["nameEvidence"]=="independently-enumerated-discovery-target"
assert by["c_chn_mp_pla_sniper_fb"]["nameEvidence"]=="independently-enumerated-discovery-target"
assert by["c_usa_mp_fbi_assault_fb"]["nameEvidence"]=="derived-from-retail-viewhands-prefix-and-class-convention"
assert by["c_mul_mp_cordis_smg_fb"]["nameEvidence"]=="derived-from-retail-viewhands-prefix-and-class-convention"
assert all(not x["required"] for x in expected["models"])
assert all(x["retailIdentityStatus"]=="unresolved-until-exact-xmodel-corpus-hit" for x in expected["models"])
assert len(by)==30
print("t6_player_body_target_census_mp_v1: PASS (6 factions, 18 viewhands identities, 30 body candidates, 10 independently enumerated)")
