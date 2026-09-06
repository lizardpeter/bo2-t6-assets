#!/usr/bin/env python3
import importlib.util,json,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def mod():
    s=importlib.util.spec_from_file_location("c",HERE/"t6_playeranim_selector_profile_census_v1.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
m=mod()
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"layer.json"
    p.write_text(json.dumps({"format":"t6-weapon-playeranim-selector-layer-summary-v1","authority":"fixture","selectors":{"b_mp":["smg","handleclip"],"a_mp":["smg","handleclip"],"c_mp":["rifle","default"],"d_mp":["pistol spread","default"]}})+"\n")
    o=m.build(m.load(p),p)
    assert o["summary"]=={"weaponRows":4,"uniqueSelectorProfiles":3}
    by={x["id"]:x for x in o["profiles"]}
    assert by["standard_onfoot_smg_handleclip_v1"]["memberWeapons"]==["a_mp","b_mp"]
    assert by["standard_onfoot_pistol_spread_default_v1"]["selectors"]["weaponclass"]=="pistol spread"
    assert all(x["concreteWeapon"] is None for x in o["profiles"])
    p.write_text(json.dumps({"format":"t6-weapon-playeranim-selector-layer-v1","weapons":[{"weapon":"x","selector":{"weaponclass":"mg","playerAnimType":"beltfed"}},{"weapon":"x","selector":{"weaponclass":"mg","playerAnimType":"beltfed"}},{"weapon":"ignored","selector":None}]})+"\n")
    o=m.build(m.load(p),p)
    assert o["summary"]=={"weaponRows":1,"uniqueSelectorProfiles":1}
    assert o["profiles"][0]["memberWeapons"]==["x"]
print("t6_playeranim_selector_profile_census_v1: PASS")
