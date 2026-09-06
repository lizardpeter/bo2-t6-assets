#!/usr/bin/env python3
import importlib.util,json,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location("mx",HERE/"t6_player_character_animation_matrix_v2.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
profiles={"format":"t6-playeranim-selector-profile-census-v1","profiles":[
 {"id":"p1","selectors":{"weaponclass":"smg","nextWeaponclass":"smg","playerAnimType":"default","nextPlayerAnimType":"default"},"memberWeapons":["a"]},
 {"id":"p2","selectors":{"weaponclass":"rifle","nextWeaponclass":"rifle","playerAnimType":"default","nextPlayerAnimType":"default"},"memberWeapons":["b"]}]}
registry={"format":"t6-player-body-identity-registry-v1","bodies":[
 {"name":"body_a","retailIdentityStatus":"retail-proven-full-body"},
 {"name":"body_b","retailIdentityStatus":"candidate-unresolved"}]}
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/"c.json"
 c={"format":"t6-third-person-animation-compatibility-v2","bodyModel":"body_a","selectorProfile":{"id":"p1","selectors":profiles["profiles"][0]["selectors"]},"allRequiredTracksCompatible":True,"ownershipResolvedFromRetail":True}
 p.write_text(json.dumps(c))
 o=m.build(profiles,registry,[(p,c)])
 assert o["summary"]=={"bodyModels":2,"retailProvenBodies":1,"unresolvedBodyCandidates":1,"selectorProfiles":2,"crossProductCells":4,"closedCells":1,"pendingCompatibilityCells":1,"blockedBodyIdentityCells":2,"failedProofCells":0}
 by={(x["bodyModel"],x["profileId"]):x for x in o["cells"]}
 assert by[("body_a","p1")]["status"]=="closed"
 assert by[("body_a","p2")]["status"]=="pending-no-retained-proof"
 assert by[("body_b","p1")]["status"]=="blocked-body-identity-unresolved"
 bad=json.loads(json.dumps(c));bad["selectorProfile"]["selectors"]["playerAnimType"]="handleclip"
 try:m.build(profiles,registry,[(p,bad)])
 except ValueError:pass
 else:raise AssertionError("selector mismatch did not fail")
print("t6_player_character_animation_matrix_v2: PASS")
