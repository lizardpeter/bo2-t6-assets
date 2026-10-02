#!/usr/bin/env python3
"""Retail RMGE01 LightData structural census."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import smg_rmge01_j3d_material_census_v1 as common

PREFIXES=["Player","Strong","Weak","Planet"]

def byte(row,name,default=0):
    v=row.get(common.bcsv_hash(name),default)
    try: return int(v) & 0xff
    except Exception: return default & 0xff

def number(row,name,default=0.0):
    v=row.get(common.bcsv_hash(name),default)
    try: return float(v)
    except Exception: return float(default)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base",default=common.BASE_DEFAULT)
    ap.add_argument("--galaxy",default="EggStarGalaxy")
    ap.add_argument("--out",required=True)
    a=ap.parse_args(); base=a.base.rstrip("/")

    arc=common.rarc_files(common.fetch(f"{base}/ObjectData/LightData.arc"))
    files={name.lower():payload for name,payload in arc}
    global_payload=files.get("lightdata.bcsv")
    if global_payload is None: raise RuntimeError("LightData.bcsv missing")
    rows=common.bcsv_rows(global_payload)

    presets=[]
    follow_camera=0
    for i,row in enumerate(rows):
        name=row.get(common.bcsv_hash("AreaLightName"))
        if not isinstance(name,str) or not name:
            raise RuntimeError(f"LightData row {i} missing AreaLightName")
        p={"name":name,"interpolate":int(number(row,"Interpolate",-1)),"types":{}}
        for prefix in PREFIXES:
            actor={"ambient":[byte(row,f"{prefix}Ambient{ch}") for ch in "RGBA"],
                   "alpha2":byte(row,f"{prefix}Alpha2"),
                   "lights":[]}
            for li in range(2):
                q=f"{prefix}Light{li}"
                pos=[number(row,f"{q}Pos{axis}") for axis in "XYZ"]
                if not all(x == x and abs(x) != float("inf") for x in pos):
                    raise RuntimeError(f"{name} {q} non-finite position")
                follow=number(row,f"{q}FollowCamera") != 0
                follow_camera += int(follow)
                actor["lights"].append({
                    "position":pos,
                    "color":[byte(row,f"{q}Color{ch}") for ch in "RGBA"],
                    "follow_camera":follow,
                })
            p["types"][prefix]=actor
        presets.append(p)

    scenario=common.rarc_files(common.fetch(f"{base}/StageData/{a.galaxy}/{a.galaxy}Scenario.arc"))
    zone_payload=next((p for n,p in scenario if n.lower()=="zonelist.bcsv"),None)
    zones=[r.get(common.H_ZONE) for r in common.bcsv_rows(zone_payload) if isinstance(r.get(common.H_ZONE),str)]

    zone_maps={}
    missing=[]
    invalid_names=[]
    preset_names={p["name"] for p in presets}
    mapping_count=0
    for zone in zones:
        key=f"light{zone}.bcsv".lower()
        payload=files.get(key)
        if payload is None:
            missing.append(zone)
            continue
        table=common.bcsv_rows(payload)
        out={}
        for row in table:
            lid=int(number(row,"LightID",-1))
            name=row.get(common.bcsv_hash("AreaLightName"))
            if not isinstance(name,str) or not name:
                raise RuntimeError(f"{key} LightID {lid} has no AreaLightName")
            if name not in preset_names:
                invalid_names.append({"zone":zone,"light_id":lid,"area_light":name})
            if str(lid) in out:
                raise RuntimeError(f"{key} duplicate LightID {lid}")
            out[str(lid)]=name
            mapping_count+=1
        zone_maps[zone]=out

    # LightCtrlCube / LightCtrlCylinder are ordinary placement records whose
    # Obj_arg0 is LightID and Obj_arg1 is priority.
    light_areas=[]
    unresolved_areas=[]
    for zone in zones:
        try:
            zone_files=common.rarc_files(common.fetch(f"{base}/StageData/{zone}.arc"))
        except Exception:
            continue
        zone_map=zone_maps.get(zone,{})
        for fname,payload in zone_files:
            try: placements=common.bcsv_rows(payload)
            except Exception: continue
            for row in placements:
                obj=row.get(common.H_NAME)
                if obj not in ("LightCtrlCube","LightCtrlCylinder"):
                    continue
                lid=int(row.get(common.bcsv_hash("Obj_arg0"),-1) or -1)
                priority=int(row.get(common.bcsv_hash("Obj_arg1"),-1) or -1)
                item={"zone":zone,"shape":obj,"light_id":lid,"priority":priority}
                light_areas.append(item)
                if str(lid) not in zone_map:
                    unresolved_areas.append(item)

    result={
      "source":{"base":base,"galaxy":a.galaxy},
      "counts":{
        "area_light_presets":len(presets),
        "zone_names":len(zones),
        "zone_mapping_tables":len(zone_maps),
        "missing_zone_mapping_tables":len(missing),
        "light_id_mappings":mapping_count,
        "follow_camera_light_records":follow_camera,
        "invalid_area_light_references":len(invalid_names),
        "light_area_volumes":len(light_areas),
        "unresolved_light_area_volumes":len(unresolved_areas),
      },
      "missing_zone_mapping_tables":missing,
      "invalid_area_light_references":invalid_names,
      "zone_maps":zone_maps,
      "light_areas":light_areas,
      "unresolved_light_areas":unresolved_areas,
      "presets":presets,
      "provenance":{"policy":"retail files fetched transiently; only structural LightData census retained"}
    }
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result["counts"],indent=2,sort_keys=True))
    print("missing zone maps",missing)
    print("invalid refs",invalid_names)
    print("light areas",len(light_areas),"unresolved",unresolved_areas)

if __name__=="__main__": main()
