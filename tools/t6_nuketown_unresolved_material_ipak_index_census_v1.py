#!/usr/bin/env python3
"""Index-only exact-pair census for unresolved Nuketown Material GfxImages."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from t6_ipak_http_range_v2 import open_ipak

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--join",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("urls",nargs="+")
    a=ap.parse_args()
    d=json.loads(a.join.read_text())
    if d.get("format")!="t6-nuketown-unresolved-material-packed-trace-join-v1":
        raise SystemExit("join format drift")
    if d["summary"]!={"unresolvedProductionMaterialImageCount":347,"stablePackedTupleJoinCount":347,"crossRootTupleConflictCount":0,"absentFromPackedTraceCount":0}:
        raise SystemExit("join summary drift")
    ipaks=[open_ipak(u) for u in a.urls]
    rows=[]
    for x in d["rows"]:
        nh=x["nameHash"]&0xffffffff; dh=x["dataHash"]&0x1fffffff
        hits=[]
        for p in ipaks:
            e=p.entry_exact(nh,dh)
            if e is not None:
                hits.append({"container":p.url,"entry":{"dataHash":e[0],"nameHash":e[1],"offset":e[2],"rawSize":e[3]}})
        rows.append({"name":x["name"],"nameHash":nh,"dataHash":dh,"exactPairMatches":hits,"status":"present" if hits else "absent"})
    present=[x for x in rows if x["exactPairMatches"]]
    missing=[x for x in rows if not x["exactPairMatches"]]
    multi=[x for x in rows if len(x["exactPairMatches"])>1]
    per={}
    for x in present:
        for h in x["exactPairMatches"]:
            per[h["container"]]=per.get(h["container"],0)+1
    out={
      "format":"t6-nuketown-unresolved-material-ipak-index-census-v1",
      "summary":{
        "targetCount":len(rows),
        "exactPairPresentCount":len(present),
        "exactPairAbsentCount":len(missing),
        "multiContainerExactPairCount":len(multi),
        "exactPairMatchCount":sum(len(x["exactPairMatches"]) for x in rows),
        "presentByContainer":dict(sorted(per.items())),
      },
      "rows":rows,
      "containers":[p.describe() for p in ipaks],
      "proofBoundary":"This is exact retail IPAK index membership for the native traced (nameHash,dataHash) pair only. Presence does not yet prove payload extraction, CRC29 validity, byte agreement across duplicate containers, or IWI dimensions; those remain the resolver gate. No dataHash-only fallback is used.",
    }
    if len(rows)!=347: raise SystemExit(f"expected 347 targets, got {len(rows)}")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":
    main()
