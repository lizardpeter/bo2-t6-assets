#!/usr/bin/env python3
"""Compact exact T6 MP XAnim delta-branch census for one expanded retail XFile.

This wraps the strict v3 parser. Count closure is never inferred: the compact
proof records both the XAsset-table expected count and structurally identified
count, and only a true equality may support exhaustive branch absence.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_xanim_retail_delta_branch_census_v3 as v3

KEYS=("transKeyed","transConstant","quat2Keyed","quat2Constant","quatKeyed","quatConstant")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--expanded",type=Path,required=True)
    ap.add_argument("--zone",required=True)
    ap.add_argument("--fastfile-sha256",required=True)
    ap.add_argument("--fastfile-bytes",type=int,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    if len(a.fastfile_sha256)!=64: raise SystemExit("bad FastFile SHA-256")
    c=v3.census(a.expanded)
    out={
      "format":"t6-mp-xanim-delta-branch-zone-census-v1",
      "authority":"SHA-pinned retail MP FastFile expanded by source-closed T6 expander; strict XAnim delta branch census v3",
      "zone":a.zone,
      "retailFastFile":{"bytes":a.fastfile_bytes,"sha256":a.fastfile_sha256},
      "expanded":{"file":a.expanded.name,"bytes":c["expandedBytes"],"sha256":c["expandedSha256"]},
      "xassetCount":c["xassetCount"],
      "expectedXAnimCount":c["expectedXAnimCount"],
      "structuralRecordCount":c["structuralRecordCount"],
      "emptyPlaceholderCount":c["emptyPlaceholderCount"],
      "countClosesExactly":c["countClosesExactly"],
      "inlineNames":c["inlineNames"],
      "packedNames":c["packedNames"],
      "overlaps":c["overlaps"],
      "branches":{k:c["branches"][k] for k in KEYS},
      "constantFullQuat":c["constantFullQuat"],
      "dynamicFullQuatCount":c["dynamicFullQuatCount"],
      "dynamicFullQuatExamples":c["dynamicFullQuatExamples"],
      "proofBoundary":"Exhaustive absence/presence statements for serialized XAnim delta branches are authorized only when countClosesExactly is true. Empty placeholders are admitted only by the v3 exact 104-byte zero-record plus comma-prefixed inline-name contract. A partial count remains useful evidence but is not promoted to whole-zone absence.",
    }
    if out["overlaps"]!=0: raise SystemExit(f"{a.zone}: overlapping structural XAnim records")
    if sum((out["inlineNames"],out["packedNames"])) > out["structuralRecordCount"]:
        raise SystemExit(f"{a.zone}: name accounting overflow")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:out[k] for k in ("zone","expectedXAnimCount","structuralRecordCount","emptyPlaceholderCount","countClosesExactly","branches","dynamicFullQuatCount")},indent=2,sort_keys=True))

if __name__=="__main__": main()
