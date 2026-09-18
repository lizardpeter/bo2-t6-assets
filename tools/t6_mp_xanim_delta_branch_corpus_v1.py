#!/usr/bin/env python3
"""Aggregate transactional per-map MP XAnim branch proofs against target manifest."""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
KEYS=("transKeyed","transConstant","quat2Keyed","quat2Constant","quatKeyed","quatConstant")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--targets",type=Path,required=True)
    ap.add_argument("--proof-dir",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    target=json.loads(a.targets.read_text())
    if target.get("format")!="t6-retail-mp-world-format-targets-v1": raise SystemExit("target manifest drift")
    expected={m["zone"]:m for m in target["maps"]}
    rows=[]; missing=[]
    for zone,m in sorted(expected.items()):
        p=a.proof_dir/f"{zone}.json"
        if not p.exists():
            missing.append(zone); continue
        d=json.loads(p.read_text())
        if d.get("format")!="t6-mp-xanim-delta-branch-zone-census-v1" or d.get("zone")!=zone:
            raise SystemExit(f"{zone}: zone proof identity drift")
        ff=d["retailFastFile"]
        if ff["sha256"]!=m["sha256"] or ff["bytes"]!=m["bytes"]:
            raise SystemExit(f"{zone}: FastFile source identity drift")
        rows.append(d)
    closed=[x for x in rows if x["countClosesExactly"]]
    partial=[x for x in rows if not x["countClosesExactly"]]
    branch={k:sum(x["branches"][k] for x in closed) for k in KEYS}
    out={
      "format":"t6-mp-xanim-delta-branch-corpus-v1",
      "authority":"per-map strict v3 XAnim structural census joined to SHA-pinned 31-map retail MP target manifest",
      "sourceTargetManifest":{"path":str(a.targets),"sha256":hashlib.sha256(a.targets.read_bytes()).hexdigest()},
      "summary":{
        "targetMapCount":len(expected),
        "mapsScanned":len(rows),
        "mapsCountClosed":len(closed),
        "mapsPartial":len(partial),
        "mapsUnscanned":len(missing),
        "expectedXAnimRecordsScanned":sum(x["expectedXAnimCount"] for x in rows),
        "structuralXAnimRecordsScanned":sum(x["structuralRecordCount"] for x in rows),
        "exactCountXAnimRecords":sum(x["expectedXAnimCount"] for x in closed),
        "emptyPlaceholderRecordsExactCountMaps":sum(x["emptyPlaceholderCount"] for x in closed),
        "exactCountBranchTotals":branch,
        "constantFullQuatObservedInExactCountMaps":branch["quatConstant"],
        "dynamicFullQuatObservedInExactCountMaps":branch["quatKeyed"],
      },
      "unscannedMaps":missing,
      "partialMaps":[{"zone":x["zone"],"expected":x["expectedXAnimCount"],"identified":x["structuralRecordCount"]} for x in partial],
      "zones":[{
        "zone":x["zone"],"expected":x["expectedXAnimCount"],"identified":x["structuralRecordCount"],
        "emptyPlaceholderCount":x["emptyPlaceholderCount"],"countClosesExactly":x["countClosesExactly"],
        "branches":x["branches"],"expandedSha256":x["expanded"]["sha256"],
      } for x in rows],
      "proofBoundary":"Only count-closed zone proofs contribute to exhaustive branch totals or absence claims. Missing maps are explicit, and partial maps remain observations only. Full 31-map MP closure requires mapsScanned == mapsCountClosed == targetMapCount; this manifest does not cover Zombies or other non-MP XFiles.",
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))

if __name__=="__main__": main()
