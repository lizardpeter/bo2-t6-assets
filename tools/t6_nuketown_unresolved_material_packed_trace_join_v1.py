#!/usr/bin/env python3
"""Prove that every v1 unresolved production Material GfxImage has one stable five-root packed tuple."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def h(path: Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--coverage",type=Path,required=True)
    ap.add_argument("--trace",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    cov=json.loads(a.coverage.read_text())
    tr=json.loads(a.trace.read_text())
    if cov.get("format")!="t6-nuketown-production-texture-payload-coverage-v1":
        raise SystemExit("coverage format drift")
    if tr.get("format")!="t6-nuketown-gfximage-packed-identity-trace-v2":
        raise SystemExit("trace format drift")
    unresolved=set(cov["unresolvedProductionImages"])
    stable={x["name"]:x for x in tr["rows"]}
    conflicts={x["name"]:x for x in tr.get("conflicts",[])}
    if set(stable)&set(conflicts):
        raise SystemExit("trace stable/conflict overlap")
    joined=sorted(unresolved & set(stable))
    conflict_names=sorted(unresolved & set(conflicts))
    absent=sorted(unresolved-set(stable)-set(conflicts))
    rows=[]
    for name in joined:
        x=stable[name]
        rows.append({
            "name":name,
            "nameHash":x["nameHash"],
            "dataHash":x["dataHash"],
            "streamedPartCount":x["streamedPartCount"],
            "width":x["width"],"height":x["height"],"depth":x["depth"],
            "roots":x["roots"],
        })
    doc={
      "format":"t6-nuketown-unresolved-material-packed-trace-join-v1",
      "sources":{
        "coverage":{"path":str(a.coverage),"sha256":h(a.coverage)},
        "trace":{"path":str(a.trace),"sha256":h(a.trace)},
      },
      "summary":{
        "unresolvedProductionMaterialImageCount":len(unresolved),
        "stablePackedTupleJoinCount":len(joined),
        "crossRootTupleConflictCount":len(conflict_names),
        "absentFromPackedTraceCount":len(absent),
      },
      "rows":rows,
      "crossRootTupleConflicts":[conflicts[x] for x in conflict_names],
      "absentFromPackedTrace":absent,
      "proofBoundary":"This proves only exact-name membership in the stable five-root native packed tuple set. It does not prove that any supplied retail IPAK contains the tuple or that payload bytes decode correctly. No conflicted or absent tuple is promoted.",
    }
    if len(unresolved)!=347: raise SystemExit(f"expected 347 unresolved, got {len(unresolved)}")
    if len(joined)!=347 or conflict_names or absent:
        raise SystemExit(f"join not closed: stable={len(joined)} conflicts={len(conflict_names)} absent={len(absent)}")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":
    main()
