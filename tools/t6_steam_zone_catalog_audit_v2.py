#!/usr/bin/env python3
"""Fail-closed audit for the complete English-install T6 Steam FastFile catalog v2."""
from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path

BASE_FMT="t6-steam-english-base-zone-catalog-v1"
CAT_FMT="t6-steam-english-full-zone-catalog-v2"
OUT_FMT="t6-steam-zone-catalog-audit-v2"

def load(p:Path): return json.loads(p.read_text(encoding="utf-8"))

def read_probe(p:Path|None):
    if not p: return None
    rows={}; malformed=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        q=line.split("\t")
        if len(q)<2: malformed.append(line); continue
        rows[q[0]]={"status":q[1],"fields":q[2:]}
    return {"rows":rows,"malformed":malformed}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-catalog",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--seed",type=Path)
    ap.add_argument("--r2-probe-tsv",type=Path)
    ap.add_argument("--zip-probe-tsv",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    b=load(a.base_catalog); c=load(a.catalog); errors=[]
    if b.get("format")!=BASE_FMT: errors.append("base catalog format mismatch")
    if c.get("format")!=CAT_FMT: errors.append("v2 catalog format mismatch")
    if c.get("extends")!=str(a.base_catalog): errors.append("extends path mismatch")
    depots=list(b.get("depots",[]))+list(c.get("additionalDepots",[]))
    owners=defaultdict(list); entry_count=0
    for d in depots:
        ff=d.get("ff") if isinstance(d.get("ff"),list) else []
        if int(d.get("expectedFfCount",-1))!=len(ff): errors.append(f"depot {d.get('depotId')} FF count mismatch")
        folder=d.get("zoneFolder")
        if folder not in ("all","english"): errors.append(f"depot {d.get('depotId')} folder invalid")
        for p in ff:
            entry_count+=1
            if not isinstance(p,str) or not p.endswith('.ff'): errors.append(f"invalid FF path {p!r}"); continue
            if not p.startswith(f"zone/{folder}/"): errors.append(f"folder mismatch {p}")
            owners[p].append(int(d['depotId']))
    paths=set(owners)
    actual_collisions={p:sorted(v) for p,v in owners.items() if len(v)>1}
    expected_collisions={p:sorted(map(int,v)) for p,v in c.get("expectedOverlappingDepotPaths",{}).items()}
    if actual_collisions!=expected_collisions: errors.append(f"overlap ownership mismatch actual={actual_collisions} expected={expected_collisions}")
    t=c.get("totals",{})
    checks={
      "depots":len(depots)==int(t.get("depots",-1)),
      "depotFfEntries":entry_count==int(t.get("depotFfEntries",-1)),
      "uniqueFfPaths":len(paths)==int(t.get("uniqueFfPaths",-1)),
      "overlappingUniquePaths":len(actual_collisions)==int(t.get("overlappingUniquePaths",-1)),
    }
    for k,v in checks.items():
        if not v: errors.append(f"total check failed: {k}")
    seed=None
    if a.seed:
        s=load(a.seed); sp=[]
        for z in s.get("zones",[]):
            name=z['zone']; sp.append(f"zone/{'english' if name.startswith('en_') else 'all'}/{name}.ff")
        outside=sorted(set(sp)-paths)
        seed={"zones":len(sp),"matched":len(set(sp)&paths),"outsideCatalogPaths":outside}
    r2=read_probe(a.r2_probe_tsv); zp=read_probe(a.zip_probe_tsv)
    def probe_summary(pr):
        if pr is None: return None
        rowset=set(pr['rows']); missing=sorted(paths-rowset); unknown=sorted(rowset-paths)
        present=sorted(p for p in paths if pr['rows'].get(p,{}).get('status')=='present')
        unavailable=sorted(paths-set(present))
        return {"rows":len(pr['rows']),"present":len(present),"unavailable":unavailable,"missingProbeRows":missing,"unknownProbeRows":unknown,"malformedRows":pr['malformed']}
    rs=probe_summary(r2); zs=probe_summary(zp)
    union_present=set()
    if r2: union_present|={p for p in paths if r2['rows'].get(p,{}).get('status')=='present'}
    if zp: union_present|={p for p in paths if zp['rows'].get(p,{}).get('status')=='present'}
    union_missing=sorted(paths-union_present)
    structurally_valid=not errors
    english_complete=structurally_valid and bool(c.get('scope',{}).get('completeForEnglishRetailFfScope'))
    r2_complete=bool(rs is not None and not rs['unavailable'] and not rs['missingProbeRows'] and not rs['unknownProbeRows'] and not rs['malformedRows'])
    zip_complete=bool(zs is not None and not zs['unavailable'] and not zs['missingProbeRows'] and not zs['unknownProbeRows'] and not zs['malformedRows'])
    union_complete=bool((r2 is not None or zp is not None) and not union_missing)
    all_languages=bool(c.get('scope',{}).get('wholeRetailAllLanguagesComplete')) and english_complete
    out={
      "format":OUT_FMT,"baseCatalog":str(a.base_catalog),"catalog":str(a.catalog),
      "totals":{"depots":len(depots),"depotFfEntries":entry_count,"uniqueFfPaths":len(paths),"overlappingUniquePaths":len(actual_collisions)},
      "overlappingDepotPaths":actual_collisions,"errors":errors,"seedCoverage":seed,
      "r2Probe":rs,"publicZipProbe":zs,"sourceContainerUnion":{"present":len(union_present),"missing":union_missing},
      "gates":{
        "catalogStructurallyValid":structurally_valid,
        "englishRetailFfCatalogComplete":english_complete,
        "overlappingDepotPathOwnershipAccounted":structurally_valid and actual_collisions==expected_collisions,
        "overlappingDepotByteIdentityComplete":False,
        "r2MirrorCompleteForCatalog":r2_complete,
        "publicZipCompleteForCatalog":zip_complete,
        "sourceContainerUnionCompleteForCatalog":union_complete,
        "wholeRetailAllLanguagesCatalogComplete":all_languages,
        "populationInputIdentityComplete":False
      },
      "proofBoundary":[
        "SteamDB path enumeration proves the retained source catalog shape, not exact retail bytes.",
        "Six FastFile paths have multiple Steam depot owners. Ownership is accounted exactly, but byte-equivalence across those depot manifests remains unproven without manifest file hashes or independently matching retail bytes.",
        "R2 and public ZIP probes establish source-container availability only. They do not promote XAsset/XAnim/XModel population identity by themselves.",
        "The English-install catalog excludes non-English localization depots, so wholeRetailAllLanguagesCatalogComplete remains false."
      ]
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({"depots":len(depots),"entries":entry_count,"uniquePaths":len(paths),"collisions":len(actual_collisions),"errors":len(errors),"r2Present":None if rs is None else rs['present'],"zipPresent":None if zs is None else zs['present'],"unionPresent":len(union_present),"unionMissing":len(union_missing)},indent=2))
    if errors: raise SystemExit("catalog validation failed")
    return 0
if __name__=='__main__': raise SystemExit(main())
