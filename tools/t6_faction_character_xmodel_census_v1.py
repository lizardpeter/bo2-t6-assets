#!/usr/bin/env python3
"""Exact T6 faction full-body/viewhands XModel census.

The scan only promotes a name when all of the following hold:
1. the literal inline name ends in _fb or _viewhands;
2. the immediately preceding 248 bytes form an XModel fixed record whose name
   pointer is FOLLOWING/INSERT;
3. the general serialized XModel walker decodes the identical name;
4. the walker closes without blockers.

This intentionally does not infer Character/MpType/MpBody/MpHead ownership.
It is a proof-backed authored-XModel library census only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import defaultdict
from pathlib import Path

from t6_xmodel_serialized_walker import XMODEL_SIZE, XModelWalker
from t6_clipmap_serialized_walker import PTR_FOLLOWING, PTR_INSERT

NAME_RE = re.compile(rb"[A-Za-z0-9_./-]{4,160}(?:_fb|_viewhands)\x00")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--raw-sha256")
    ap.add_argument("--expected-expanded-sha256")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    expanded_sha = hashlib.sha256(data).hexdigest()
    if args.expected_expanded_sha256 and expanded_sha != args.expected_expanded_sha256.lower():
        raise SystemExit(
            f"expanded sha mismatch: got {expanded_sha}, expected {args.expected_expanded_sha256}"
        )

    records = []
    rejected = []
    seen = set()
    for match in NAME_RE.finditer(data):
        name = match.group(0)[:-1].decode("latin1")
        fixed = match.start() - XMODEL_SIZE
        if fixed < 0 or fixed in seen:
            continue
        if fixed + XMODEL_SIZE > len(data):
            continue
        name_ptr = struct.unpack_from("<I", data, fixed)[0]
        if name_ptr not in (PTR_FOLLOWING, PTR_INSERT):
            continue
        try:
            walk = XModelWalker(data, fixed).walk_xmodel()
        except Exception as exc:
            rejected.append({
                "name": name,
                "fixedSourceStart": fixed,
                "reason": f"walker_exception:{type(exc).__name__}:{exc}",
            })
            continue
        decoded = walk["xmodel"]["name"]
        if decoded != name:
            rejected.append({
                "name": name,
                "fixedSourceStart": fixed,
                "reason": f"walker_name_mismatch:{decoded!r}",
            })
            continue
        if walk["blockers"]:
            rejected.append({
                "name": name,
                "fixedSourceStart": fixed,
                "reason": "walker_blockers",
                "blockers": walk["blockers"],
            })
            continue
        seen.add(fixed)
        xm = walk["xmodel"]
        records.append({
            "fixedSourceStart": fixed,
            "serializedEnd": walk["assetSerializedEnd"],
            "serializedBytes": walk["assetSerializedBytes"],
            "serializedSha256": walk["assetSerializedSha256"],
            "name": name,
            "role": "full_body" if name.endswith("_fb") else "viewhands",
            "numBones": xm["numBones"],
            "numRootBones": xm["numRootBones"],
            "numSurfs": xm["numSurfs"],
            "numLods": xm["numLods"],
        })

    records.sort(key=lambda row: (row["name"], row["fixedSourceStart"]))
    grouped = defaultdict(lambda: {"fullBody": [], "viewhands": []})
    for row in records:
        suffix = "_fb" if row["role"] == "full_body" else "_viewhands"
        stem = row["name"][:-len(suffix)]
        grouped[stem]["fullBody" if row["role"] == "full_body" else "viewhands"].append(row["name"])

    pairs = []
    for identity in sorted(grouped):
        g = grouped[identity]
        pairs.append({
            "identity": identity,
            "fullBodyModels": sorted(g["fullBody"]),
            "viewhandsModels": sorted(g["viewhands"]),
            "paired": bool(g["fullBody"] and g["viewhands"]),
        })

    result = {
        "format": "t6-faction-character-xmodel-census-v1",
        "source": {
            "zone": args.zone,
            "rawSha256": args.raw_sha256,
            "expandedSha256": expanded_sha,
            "expandedBytes": len(data),
        },
        "xmodels": records,
        "pairs": pairs,
        "summary": {
            "validatedXModels": len(records),
            "fullBodyModels": sum(r["role"] == "full_body" for r in records),
            "viewhandsModels": sum(r["role"] == "viewhands" for r in records),
            "pairedIdentities": sum(p["paired"] for p in pairs),
            "unpairedIdentities": [p["identity"] for p in pairs if not p["paired"]],
            "rejectedCandidates": len(rejected),
        },
        "rejectedCandidates": rejected,
        "proofBoundary": (
            "Exact SHA-pinned expanded FastFile + inline-name adjacency + exact 248-byte "
            "XModel fixed-record interpretation + blocker-free general serialized XModel walker. "
            "This proves authored faction full-body/viewhands XModels and same-stem pairing only; "
            "it does not yet prove Character/MpType/MpBody/MpHead selection ownership."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"zone": args.zone, **result["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
