#!/usr/bin/env python3
import importlib.util,json,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def loadmod(name):
    s=importlib.util.spec_from_file_location(name,HERE/f"{name}.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
m=loadmod("t6_player_character_animation_census_v1")
with tempfile.TemporaryDirectory() as td:
    td=Path(td); profiles=td/"profiles.json"
    profiles.write_text(json.dumps({"format":"t6-playeranim-selector-profile-census-v1","profiles":[{"id":"p1","selectors":{"weaponclass":"smg","nextWeaponclass":"smg","playerAnimType":"default","nextPlayerAnimType":"default"},"memberWeapons":["a"]},{"id":"p2","selectors":{"weaponclass":"rifle","nextWeaponclass":"rifle","playerAnimType":"default","nextPlayerAnimType":"default"},"memberWeapons":["b"]}]})+"\n")
    c=td/"c.json"; c.write_text(json.dumps({"format":"t6-third-person-animation-compatibility-v1","bodyModel":"body_a","selectorProfile":{"id":"p1","selectors":{"weaponclass":"smg","nextWeaponclass":"smg","playerAnimType":"default","nextPlayerAnimType":"default"}},"allRequiredTracksCompatible":True,"ownershipResolvedFromRetail":True,"summary":{"x":1}})+"\n")
    o=m.build(m.load(profiles),profiles,[c])
    assert o["summary"]=={"bodyModels":1,"selectorProfiles":2,"crossProductCells":2,"closedCells":1,"failedProofCells":0,"pendingCells":1}
    assert [x["status"] for x in o["cells"]]==["closed","pending-no-retained-proof"]
    assert o["cells"][0]["compatibilityProof"]["compatibilityFormat"]=="t6-third-person-animation-compatibility-v1"
    bad=td/"bad.json"; bad.write_text(json.dumps({"format":"t6-third-person-animation-compatibility-v2","bodyModel":"body_a","selectorProfile":{"id":"p2","selectors":{"weaponclass":"rifle","nextWeaponclass":"rifle","playerAnimType":"default","nextPlayerAnimType":"default"}},"allRequiredTracksCompatible":False,"ownershipResolvedFromRetail":True})+"\n")
    o=m.build(m.load(profiles),profiles,[c,bad]); assert o["summary"]["failedProofCells"]==1 and o["summary"]["pendingCells"]==0
    wrong=td/"wrong.json"; wrong.write_text(json.dumps({"format":"t6-third-person-animation-compatibility-v2","bodyModel":"body_b","selectorProfile":{"id":"p1","selectors":{"weaponclass":"smg","nextWeaponclass":"smg","playerAnimType":"handleclip","nextPlayerAnimType":"handleclip"}},"allRequiredTracksCompatible":True,"ownershipResolvedFromRetail":True})+"\n")
    try: m.build(m.load(profiles),profiles,[wrong])
    except ValueError: pass
    else: raise AssertionError("selector mismatch did not fail")
print("t6_player_character_animation_census_v1: PASS")
