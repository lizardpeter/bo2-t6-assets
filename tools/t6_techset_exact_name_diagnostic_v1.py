#!/usr/bin/env python3
"""Non-promoting exact-name diagnostic for T6 MaterialTechniqueSet dependencies.

This tool is deliberately not an ownership proof. Given one or more canonical
TechniqueSet names, it enumerates every exact NUL-terminated occurrence of the
canonical and comma-prefixed spelling in an expanded retail XFile. If an
occurrence is exactly 152 bytes after a structurally valid TechniqueSet fixed
record, the existing source-closed nested serializer is replayed there and the
serialized extent is hashed.

The result is useful for locating the retail definition reached by an already
source-proven comma-prefixed reference stub. It must not be used to assign a
top-level XAsset index or to replace source-order replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_material_techset_top_level_walk_v1 import Cursor, parse_front


def occurrences(data: bytes, needle: bytes) -> list[int]:
    out = []
    p = 0
    while True:
        p = data.find(needle, p)
        if p < 0:
            return out
        out.append(p)
        p += 1


def inspect_name(data: bytes, blocks: tuple[int, ...], spelling: str) -> list[dict[str, Any]]:
    needle = spelling.encode("latin1") + b"\0"
    rows = []
    for name_start in occurrences(data, needle):
        fixed_start = name_start - 152
        rec: dict[str, Any] = {
            "spelling": spelling,
            "nameStart": name_start,
            "candidateFixedStart": fixed_start,
            "candidateTechniqueSet": False,
        }
        if fixed_start < 0:
            rows.append(rec)
            continue
        try:
            c = Cursor(data, fixed_start, blocks)
            node = c.techset()
            got = ((node.get("name") or {}).get("value"))
            if got != spelling:
                raise ValueError(f"parsed name {got!r} != requested spelling")
            active = [x for x in node.get("techniqueRefs") or [] if (x.get("pointer") or {}).get("kind") != "null"]
            inline_tech = [x for x in active if x.get("inlineTechnique") is not None]
            raw = data[fixed_start:c.p]
            rec.update({
                "candidateTechniqueSet": True,
                "serializedEnd": c.p,
                "serializedBytes": c.p - fixed_start,
                "serializedSha256": hashlib.sha256(raw).hexdigest(),
                "worldVertFormat": node.get("worldVertFormat"),
                "nonNullTechniqueRefs": len(active),
                "inlineTechniqueRefs": len(inline_tech),
                "activeSlots": [x.get("slot") for x in active],
                "node": node,
            })
        except Exception as exc:
            rec["parseError"] = str(exc)
        rows.append(rec)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--name", action="append", required=True)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    data = a.expanded.read_bytes()
    blocks, assets, source = parse_front(data)
    targets = []
    for canonical in a.name:
        canonical = canonical[1:] if canonical.startswith(",") else canonical
        spellings = [canonical, "," + canonical]
        rows = []
        for spelling in spellings:
            rows.extend(inspect_name(data, blocks, spelling))
        targets.append({
            "canonicalName": canonical,
            "occurrenceCount": len(rows),
            "techniqueSetCandidateCount": sum(1 for x in rows if x.get("candidateTechniqueSet")),
            "occurrences": rows,
        })

    out = {
        "format": "t6-techset-exact-name-diagnostic-v1",
        "zone": a.zone,
        "source": {
            "expandedBytes": len(data),
            "expandedSha256": hashlib.sha256(data).hexdigest(),
            "assetCount": len(assets),
            "assetBodySourceStart": source,
            "blockSizes": list(blocks),
        },
        "targets": targets,
        "diagnosticOnly": True,
        "noOwnershipPromoted": True,
        "proofBoundary": (
            "Exact literal name occurrences and successful nested TechniqueSet parses are diagnostic evidence only. "
            "No occurrence is assigned to a top-level XAsset index from scan position, name, rank, adjacency, or similarity; "
            "top-level ownership still requires retail loader/source-order proof."
        ),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "zone": a.zone,
        "targets": [
            {
                "name": x["canonicalName"],
                "occurrences": x["occurrenceCount"],
                "techniqueSetCandidates": x["techniqueSetCandidateCount"],
            }
            for x in targets
        ],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
