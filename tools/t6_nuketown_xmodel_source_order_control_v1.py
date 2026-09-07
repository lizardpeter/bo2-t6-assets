#!/usr/bin/env python3
"""Exact expanded-stream source-order control for the first Nuketown XModels.

This control deliberately stays in the repository expanded-FastFile coordinate
system. It never translates OpenAssetTools source-consumption positions.

Independent retained canaries from the exact retail Nuketown q4 cursor audit:
  * expanded SHA-256 7e791f...d505
  * q3 TechniqueSet: 125632 -> 499456
  * q4 XModel nt_2020_air_vent: 499456 -> 515650

After those canaries validate the starting cursor and XModel serializer, the
same fail-closed top-level walker advances through q3..q13 in XAsset order.
Only XMODEL/TECHNIQUE_SET records are accepted by that walker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_clipmap_normalize_v5 import parse_top_level_xasset_table
from t6_clipmap_normalize_v6 import walk_map_prefix_stringtable
from t6_xmodel_techset_top_level_walk_v1 import walk

EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
Q3_START = 125632
Q3_END = 499456
Q4_END = 515650
Q4_NAME = "nt_2020_air_vent"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    d = a.expanded.read_bytes()
    sha = hashlib.sha256(d).hexdigest()
    if sha != EXPANDED_SHA256:
        raise SystemExit(f"expanded SHA mismatch: {sha}")

    table = parse_top_level_xasset_table(d)
    prefix = walk_map_prefix_stringtable(d, table)
    source_start = int(prefix["sourceEnd"])
    if source_start != Q3_START:
        raise SystemExit(f"map prefix ended at {source_start}, expected {Q3_START}")

    q3 = walk(d, 3, 3, source_start)
    if int(q3["sourceEnd"]) != Q3_END:
        raise SystemExit(f"q3 ended at {q3['sourceEnd']}, expected {Q3_END}")
    if q3["rows"][0]["kind"] != "TECHNIQUE_SET":
        raise SystemExit(f"q3 kind drifted: {q3['rows'][0]['kind']}")

    full = walk(d, 3, 13, source_start)
    rows = full["rows"]
    by_q = {int(r["xassetIndex"]): r for r in rows}
    if sorted(by_q) != list(range(3, 14)):
        raise SystemExit(f"unexpected q coverage: {sorted(by_q)}")
    if int(by_q[4]["sourceStart"]) != Q3_END:
        raise SystemExit(f"q4 start drifted: {by_q[4]['sourceStart']}")
    if int(by_q[4]["sourceEnd"]) != Q4_END:
        raise SystemExit(f"q4 end drifted: {by_q[4]['sourceEnd']}")
    if by_q[4].get("xmodelName") != Q4_NAME:
        raise SystemExit(f"q4 name drifted: {by_q[4].get('xmodelName')!r}")

    xmodel_rows = []
    for q in range(4, 14):
        r = by_q[q]
        if r["kind"] != "XMODEL" or int(r["xassetType"]) != 5:
            raise SystemExit(f"q{q} is not the expected XMODEL: {r['kind']} type={r['xassetType']}")
        if int(r["sourceEnd"]) <= int(r["sourceStart"]):
            raise SystemExit(f"q{q} did not advance")
        xmodel_rows.append({
            "xassetIndex": q,
            "name": r.get("xmodelName"),
            "numBones": r.get("numBones"),
            "numSurfs": r.get("numSurfs"),
            "sourceStart": int(r["sourceStart"]),
            "sourceEnd": int(r["sourceEnd"]),
            "serializedBytes": int(r["sourceEnd"]) - int(r["sourceStart"]),
        })

    for left, right in zip(rows, rows[1:]):
        if int(left["sourceEnd"]) != int(right["sourceStart"]):
            raise SystemExit(
                f"source-order discontinuity q{left['xassetIndex']} -> q{right['xassetIndex']}: "
                f"{left['sourceEnd']} != {right['sourceStart']}"
            )

    out = {
        "format": "t6-nuketown-xmodel-source-order-control-v1",
        "expandedSha256": sha,
        "coordinateSystem": "repository expanded FastFile byte offsets",
        "retiredOatCoordinateTranslationUsed": False,
        "mapPrefixSourceEnd": source_start,
        "canaries": {
            "q3": {"sourceStart": Q3_START, "sourceEnd": Q3_END, "kind": "TECHNIQUE_SET"},
            "q4": {"sourceStart": Q3_END, "sourceEnd": Q4_END, "name": Q4_NAME},
        },
        "walk": {
            "startAssetIndex": 3,
            "endAssetIndex": 13,
            "sourceStart": int(full["sourceStart"]),
            "sourceEnd": int(full["sourceEnd"]),
            "sourceContinuous": True,
            "xmodelsSourceClosed": len(xmodel_rows),
            "xmodelRows": xmodel_rows,
        },
        "gates": {
            "expandedRetailIdentityMatches": True,
            "exactMapPrefixCursorEstablished": True,
            "q3IndependentEndpointCanaryMatches": True,
            "q4IndependentXModelCanaryMatches": True,
            "q4ThroughQ13XModelSourceOrderClosed": len(xmodel_rows) == 10,
            "wholeZoneXModelPopulationClosed": False,
        },
        "proofBoundary": [
            "q3/q4 canaries are expanded-stream endpoints from the independently retained exact Nuketown q4 cursor audit.",
            "q4 through q13 are promoted only because one exact source cursor is advanced sequentially through the top-level XAsset order and every XModel fully passes XModelWalker.",
            "This does not assert that q4 through q13 are all Nuketown XModels, nor that the whole zone XModel population is closed.",
            "No OAT source-consumption offset is translated into an expanded-stream offset.",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "sourceStart": out["walk"]["sourceStart"],
        "sourceEnd": out["walk"]["sourceEnd"],
        "xmodelsSourceClosed": len(xmodel_rows),
        "names": [r["name"] for r in xmodel_rows],
        "gates": out["gates"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
