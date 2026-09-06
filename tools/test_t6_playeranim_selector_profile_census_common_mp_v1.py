#!/usr/bin/env python3
"""Retail canary for the common_mp playeranim selector profile universe."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools"/"t6_playeranim_selector_profile_census_v1.py"
SOURCE=ROOT/"manifests"/"nonmap"/"retail"/"common_mp_weapon_playeranim_selector_summary_v1.json"

def load_tool():
    s=importlib.util.spec_from_file_location("selector_census",TOOL)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

m=load_tool(); out=m.build(m.load(SOURCE),SOURCE)
assert out["summary"]=={"weaponRows":54,"uniqueSelectorProfiles":24},out["summary"]
by={p["id"]:p for p in out["profiles"]}
assert len(by)==24
assert by["standard_onfoot_smg_handleclip_v1"]["memberWeapons"]==["insas_mp","mp7_mp"]
assert by["standard_onfoot_smg_default_v1"]["memberWeapons"]==["evoskorpion_mp","vector_mp"]
assert by["standard_onfoot_rifle_rearclip_v1"]["memberWeapons"]==["saritch_mp","tar21_mp","type95_mp"]
assert by["standard_onfoot_grenade_hold_v1"]["memberWeaponCount"]==6
assert by["standard_onfoot_grenade_default_v1"]["memberWeaponCount"]==7
assert by["standard_onfoot_melee_singleknife_v1"]["memberWeapons"]==["knife_held_mp"]
assert by["standard_onfoot_item_riotshield_v1"]["memberWeapons"]==["riotshield_mp"]
assert all(p["concreteWeapon"] is None for p in out["profiles"])
assert all(p["selectors"]["weaponclass"]==p["selectors"]["nextWeaponclass"] for p in out["profiles"])
assert all(p["selectors"]["playerAnimType"]==p["selectors"]["nextPlayerAnimType"] for p in out["profiles"])
print("t6_playeranim_selector_profile_census_common_mp_v1: PASS (54 weapons, 24 profiles)")
