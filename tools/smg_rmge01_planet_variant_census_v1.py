#!/usr/bin/env python3
"""Retail RMGE01 PlanetMap child-resource census for one galaxy."""
from __future__ import annotations
import argparse, collections, json
from pathlib import Path
import smg_rmge01_j3d_material_census_v1 as common

FIELDS = ["BloomFlag", "IndirectFlag", "WaterFlag"]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base",default=common.BASE_DEFAULT)
    ap.add_argument("--galaxy",default="EggStarGalaxy")
    ap.add_argument("--out",required=True)
    a=ap.parse_args(); base=a.base.rstrip("/")

    table_arc=common.rarc_files(common.fetch(f"{base}/ObjectData/PlanetMapDataTable.arc"))
    table_payload=next((p for n,p in table_arc if n.lower()=="planetmapdatatable.bcsv"),None)
    if table_payload is None:
        raise RuntimeError("PlanetMapDataTable.bcsv missing")
    table=common.bcsv_rows(table_payload)
    by_name={}
    for row in table:
        name=row.get(common.bcsv_hash("PlanetName"))
        if not isinstance(name,str) or not name: continue
        by_name[name.lower()] = {
            field: float(row.get(common.bcsv_hash(field),0) or 0) != 0
            for field in FIELDS
        }

    scenario=common.rarc_files(common.fetch(f"{base}/StageData/{a.galaxy}/{a.galaxy}Scenario.arc"))
    zone_payload=next((p for n,p in scenario if n.lower()=="zonelist.bcsv"),None)
    zones=[r.get(common.H_ZONE) for r in common.bcsv_rows(zone_payload) if isinstance(r.get(common.H_ZONE),str)]
    objects=set()
    for zone in zones:
        for name,payload in common.rarc_files(common.fetch(f"{base}/StageData/{zone}.arc")):
            if name.lower()=="stageobjinfo": continue
            try: rows=common.bcsv_rows(payload)
            except Exception: continue
            for row in rows:
                v=row.get(common.H_NAME)
                if isinstance(v,str) and v: objects.add(v)

    requested=collections.Counter(); present=collections.Counter(); missing=[]
    planet_objects=[]
    for obj in sorted(objects):
        flags=by_name.get(obj.lower())
        if flags is None: continue
        planet_objects.append(obj)
        for field,suffix in [("BloomFlag","Bloom"),("IndirectFlag","Indirect"),("WaterFlag","Water")]:
            if not flags[field]: continue
            requested[suffix]+=1
            name=f"{obj}{suffix}"
            try:
                common.fetch(common.object_url(base,name),retries=2)
                present[suffix]+=1
            except Exception as e:
                missing.append({"object":obj,"variant":name,"error":str(e)})

    result={
        "source":{"base":base,"galaxy":a.galaxy},
        "counts":{
            "planet_table_rows":len(table),
            "placed_unique_objects":len(objects),
            "registered_planet_objects":len(planet_objects),
            "requested_variants":sum(requested.values()),
            "present_variants":sum(present.values()),
            "missing_variants":len(missing),
        },
        "requested_by_kind":dict(requested),
        "present_by_kind":dict(present),
        "planet_objects":planet_objects,
        "missing":missing,
        "provenance":{"policy":"retail payloads fetched transiently; only structural counts retained"},
    }
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__": main()
