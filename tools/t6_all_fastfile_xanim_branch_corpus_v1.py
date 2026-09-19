#!/usr/bin/env python3
"""Aggregate compact per-FastFile strict XAnim branch census rows.

Only rows whose structural XAnim count exactly equals the raw XAsset-list XANIMPARTS
count contribute to exhaustive branch totals/absence statements. Partial rows remain
first-class evidence and are never coerced closed.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

KEYS=("transKeyed","transConstant","quat2Keyed","quat2Constant","quatKeyed","quatConstant")
FMT="t6-all-fastfile-xanim-branch-corpus-v1"
SHARD_FMT="t6-all-fastfile-xanim-branch-corpus-shard-v1"

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shard-dir",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    files=sorted(a.shard_dir.glob("T6_ALL_FASTFILE_XANIM_BRANCH_CORPUS_SHARD_*_V1.json"))
    if len(files)!=8:raise SystemExit(f"expected 8 shard proofs, got {len(files)}")
    docs=[json.loads(p.read_text()) for p in files]
    rows=[]
    for d in docs:
        if d.get("format")!=SHARD_FMT:raise SystemExit("shard format drift")
        rows.extend(d.get("rows",[]))
    rows.sort(key=lambda r:int(r["globalIndex"]))
    if len(rows)!=215 or [int(r["globalIndex"]) for r in rows]!=list(range(215)):
        raise SystemExit("incomplete 215-FastFile row universe")
    bad=[r for r in rows if r.get("status")!="green"]
    if bad:raise SystemExit(f"non-green expansion/census rows: {[x.get('zipPath') for x in bad[:12]]}")
    closed=[r for r in rows if r["countClosesExactly"]]
    partial=[r for r in rows if not r["countClosesExactly"]]
    exact_totals={k:sum(int(r["branches"][k]) for r in closed) for k in KEYS}
    observed_totals={k:sum(int(r["branches"][k]) for r in rows) for k in KEYS}
    const_hits=[r for r in rows if int(r["branches"]["quatConstant"])>0]
    dyn_hits=[r for r in rows if int(r["branches"]["quatKeyed"])>0]
    doc={
      "format":FMT,
      "authority":"complete 215-FastFile public archive universe; CRC-verified remote ZIP extraction; SHA-pinned raw/expanded rows; strict XAnim branch census v3",
      "remoteZip":docs[0].get("remoteZip"),
      "summary":{
        "archiveFastFileCount":len(rows),"greenFastFileCount":len(rows),
        "countClosedFastFileCount":len(closed),"partialFastFileCount":len(partial),
        "expectedXAnimRecordsCountClosed":sum(int(r["expectedXAnimCount"]) for r in closed),
        "structuralXAnimRecordsCountClosed":sum(int(r["structuralRecordCount"]) for r in closed),
        "emptyPlaceholderRecordsCountClosed":sum(int(r["emptyPlaceholderCount"]) for r in closed),
        "exactCountBranchTotals":exact_totals,
        "allIdentifiedBranchTotals":observed_totals,
        "constantFullQuatObservedCountClosed":exact_totals["quatConstant"],
        "constantFullQuatObservedAllIdentified":observed_totals["quatConstant"],
        "dynamicFullQuatObservedCountClosed":exact_totals["quatKeyed"],
        "constantFullQuatHitFastFileCount":len(const_hits),
        "dynamicFullQuatHitFastFileCount":len(dyn_hits),
      },
      "partialFastFiles":[{
        "globalIndex":r["globalIndex"],"zipPath":r["zipPath"],"zoneName":r["zoneName"],
        "expectedXAnimCount":r["expectedXAnimCount"],"structuralRecordCount":r["structuralRecordCount"],
        "branches":r["branches"]
      } for r in partial],
      "constantFullQuatHitFastFiles":[{
        "globalIndex":r["globalIndex"],"zipPath":r["zipPath"],"zoneName":r["zoneName"],
        "countClosesExactly":r["countClosesExactly"],"constantFullQuat":r.get("constantFullQuat",[])
      } for r in const_hits],
      "dynamicFullQuatHitFastFiles":[{
        "globalIndex":r["globalIndex"],"zipPath":r["zipPath"],"zoneName":r["zoneName"],
        "countClosesExactly":r["countClosesExactly"],"dynamicFullQuatCount":r["dynamicFullQuatCount"],
        "dynamicFullQuatExamples":r.get("dynamicFullQuatExamples",[])
      } for r in dyn_hits],
      "rows":rows,
      "proofBoundary":"Complete only for the referenced 215-FastFile public archive universe. Every successfully expanded row is retained, but exhaustive branch totals and negative branch claims use only exact-count rows. Partial rows contribute only positive observations. This does not prove absence from retail XFiles not present in this archive, language/platform variants, or historical executables."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
