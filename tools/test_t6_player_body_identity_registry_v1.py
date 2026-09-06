#!/usr/bin/env python3
import importlib.util, json, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
def lm(name):
 s=importlib.util.spec_from_file_location(name,HERE/f"{name}.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
r=lm("t6_player_body_identity_registry_v1"); c=lm("t6_player_body_target_census_v1")
seed={"format":"t6-player-faction-prefix-seeds-v1","classes":["smg","sniper"],"factions":[{"faction":"A","prefix":"c_a_mp_alpha","viewhandsEvidence":["c_a_mp_alpha_viewhands"]}],"independentlyEnumeratedBodyNames":[]}
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/"proof.json"
 proof={"format":"fixture","authority":"fixture","fullBody":{"name":"c_a_mp_alpha_smg_fb","bones":100,"rootBones":1,"surfaces":2,"fixedRecordSha256":"a"*64,"fixedPlusNameSha256":"b"*64,"skeleton":{"hierarchyValid":True,"allBoneNamesResolved":True,"normalizedJsonSha256":"c"*64},"mesh":{"vertices":1,"triangles":1}},"sourceFastfile":{"zoneName":"faction_a_mp","sha256":"d"*64},"expandedStream":{"sha256":"e"*64},"status":{"fullBodyGeometryRetailProven":True,"fullBodySkeletonRetailProven":True,"retailCompiledPlayerScriptLocated":True}}
 p.write_text(json.dumps(proof))
 o=r.build(seed,[(p,proof)],c)
 assert o["summary"]=={"candidateBodies":2,"retailProvenFullBodies":1,"unresolvedCandidateBodies":1,"retailSkeletonsClosed":1}
 by={x["name"]:x for x in o["bodies"]}
 assert by["c_a_mp_alpha_smg_fb"]["retailIdentityStatus"]=="retail-proven-full-body"
 assert by["c_a_mp_alpha_sniper_fb"]["retailIdentityStatus"]=="candidate-unresolved"
 bad=json.loads(json.dumps(proof));bad["status"]["fullBodySkeletonRetailProven"]=False
 try:r.build(seed,[(p,bad)],c)
 except ValueError:pass
 else:raise AssertionError("unproven skeleton promoted")
 bad=json.loads(json.dumps(proof));bad["fullBody"]["name"]="outside_fb"
 try:r.build(seed,[(p,bad)],c)
 except ValueError:pass
 else:raise AssertionError("outside candidate universe promoted")
print("t6_player_body_identity_registry_v1: PASS")
