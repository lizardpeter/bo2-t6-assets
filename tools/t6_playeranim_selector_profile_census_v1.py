#!/usr/bin/env python3
"""Derive unique standard on-foot playeranim selector profiles from a T6 weapon selector layer.

This deliberately describes selector classes, not final named-weapon ownership.
A later weapon layer can still override a named weapon without changing the
reusable compatibility profile for the selector tuple itself.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

FORMAT="t6-playeranim-selector-profile-census-v1"
FAMILIES=["idle/stance","walk/run/sprint","crouch/prone","jump/fall/land","weapon-ready/fire/reload","melee","turn/aim","death/reaction"]
FORBIDDEN=["mounted","vehicle_name","vehicle_seat_to"]

def load(p:Path):
    d=json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(d,dict): raise ValueError("selector layer must be a JSON object")
    return d

def sha256(p:Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def slug(s:str)->str:
    x=re.sub(r"[^a-z0-9]+","_",s.lower()).strip("_")
    if not x: raise ValueError(f"selector value has no slug: {s!r}")
    return x

def rows(d:dict):
    fmt=d.get("format"); out=[]
    if fmt=="t6-weapon-playeranim-selector-layer-summary-v1":
        for weapon,pair in (d.get("selectors") or {}).items():
            if not isinstance(weapon,str) or not isinstance(pair,list) or len(pair)!=2: raise ValueError(f"invalid summary selector row for {weapon!r}")
            out.append((weapon,pair[0],pair[1]))
    elif fmt=="t6-weapon-playeranim-selector-layer-v1":
        for r in d.get("weapons") or []:
            if not isinstance(r,dict) or not isinstance(r.get("weapon"),str): raise ValueError("invalid selector layer weapon row")
            sel=r.get("selector")
            if not isinstance(sel,dict): continue
            out.append((r["weapon"],sel.get("weaponclass"),sel.get("playerAnimType")))
    else: raise ValueError(f"unsupported selector layer format: {fmt!r}")
    for w,wc,pat in out:
        if not isinstance(wc,str) or not wc or not isinstance(pat,str) or not pat: raise ValueError(f"{w}: selector pair missing strings")
    return out

def build(d:dict,path:Path):
    grouped={}
    for weapon,wc,pat in rows(d): grouped.setdefault((wc,pat),[]).append(weapon)
    profiles=[]; ids=set()
    for (wc,pat),weapons in sorted(grouped.items(),key=lambda x:(x[0][0].casefold(),x[0][1].casefold())):
        pid=f"standard_onfoot_{slug(wc)}_{slug(pat)}_v1"
        if pid in ids: raise ValueError(f"profile id collision: {pid}")
        ids.add(pid); members=sorted(set(weapons),key=str.casefold)
        profiles.append({"id":pid,"format":"t6-playeranim-selector-profile-v1","selectors":{"weaponclass":wc,"nextWeaponclass":wc,"playerAnimType":pat,"nextPlayerAnimType":pat},"forbiddenConditionKeys":FORBIDDEN,"requiredBehaviorFamilies":FAMILIES,"concreteWeapon":None,"memberWeapons":members,"memberWeaponCount":len(members),"rule":"Named weapons are membership evidence for this source layer only; final retail assignment still requires ordered weapon-layer precedence closure."})
    return {"format":FORMAT,"authority":"deterministic selector-tuple census from supplied retail weapon selector evidence","source":{"path":str(path),"sha256":sha256(path),"format":d.get("format"),"authority":d.get("authority")},"summary":{"weaponRows":sum(p["memberWeaponCount"] for p in profiles),"uniqueSelectorProfiles":len(profiles)},"profiles":profiles,"proofBoundary":"This census proves only which selector tuples occur in the supplied selector layer and which source-layer weapon rows share them. It does not prove that any named weapon retains that selector after later retail weapon layers."}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--selector-layer",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    out=build(load(a.selector_layer),a.selector_layer); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps(out["summary"],indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
