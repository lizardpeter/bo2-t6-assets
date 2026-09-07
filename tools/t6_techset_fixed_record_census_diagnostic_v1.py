#!/usr/bin/env python3
"""Diagnose all plausible T6 MaterialTechniqueSet fixed records in one expanded zone.

This is deliberately non-promoting. It accepts packed/reused TechniqueSet name
pointers instead of assuming the internal name is FOLLOWING. Candidates require:
- non-null valid name pointer;
- worldVertFormat <= 8 and zero header padding;
- all 36 technique pointers null/FOLLOWING/INSERT/valid packed;
- at least one non-null technique pointer.

The diagnostic compares the candidate count/source order with the exact inline
type-7 XAsset count. It does not assign identities when multiple candidates
remain.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from t6_asset_types_v1 import ASSET_TYPES, TECHNIQUE_SET
from t6_material_techset_top_level_walk_v1 import FOLLOW, INSERT, dec, parse_front


def ptr_valid(raw: int, blocks: tuple[int, ...]) -> tuple[bool, dict | None]:
    if raw == 0:
        return True, {"kind": "null", "rawHex": "0x00000000"}
    try:
        p = dec(raw, blocks)
    except Exception:
        return False, None
    return p.get("kind") in ("packed", "following", "insert"), p


def inline_name(data: bytes, start: int, raw: int) -> str | None:
    if raw not in (FOLLOW, INSERT):
        return None
    p = start + 152
    e = data.find(b"\0", p, min(len(data), p + 512))
    if e < 0:
        return None
    b = data[p:e]
    if not b or any(x < 32 or x > 126 for x in b):
        return None
    return b.decode("latin1")


def build(expanded: Path) -> dict:
    data = expanded.read_bytes()
    blocks, assets, body = parse_front(data)
    inline_q = [
        i
        for i, a in enumerate(assets)
        if int(a["type"]) == TECHNIQUE_SET and int(a["headerRaw"]) in (FOLLOW, INSERT)
    ]

    candidates = []
    # Byte-granular on purpose: source allocations are not assumed to be aligned.
    limit = len(data) - 152
    for off in range(body, limit):
        name_raw = struct.unpack_from("<I", data, off)[0]
        if name_raw == 0:
            continue
        world = data[off + 4]
        if world > 8 or data[off + 5 : off + 8] != b"\0\0\0":
            continue
        ok, name_ptr = ptr_valid(name_raw, blocks)
        if not ok:
            continue
        refs = struct.unpack_from("<36I", data, off + 8)
        if not any(refs):
            continue
        ref_kinds = {"null": 0, "following": 0, "insert": 0, "packed": 0}
        valid = True
        for raw in refs:
            ok, p = ptr_valid(raw, blocks)
            if not ok or p is None:
                valid = False
                break
            ref_kinds[p["kind"]] = ref_kinds.get(p["kind"], 0) + 1
        if not valid:
            continue
        candidates.append(
            {
                "start": off,
                "namePointer": name_ptr,
                "inlineName": inline_name(data, off, name_raw),
                "worldVertFormat": world,
                "techniquePointerKinds": ref_kinds,
                "nonNullTechniquePointers": 36 - ref_kinds.get("null", 0),
            }
        )

    asset_rows = [
        {
            "xassetIndex": int(a["xassetIndex"]),
            "typeId": int(a["type"]),
            "type": ASSET_TYPES[int(a["type"])],
            "headerRaw": f"0x{int(a['headerRaw']):08X}",
        }
        for a in assets
    ]
    return {
        "format": "t6-techset-fixed-record-census-diagnostic-v1",
        "assetBodySourceStart": body,
        "inlineTechniqueSetXAssetIndices": inline_q,
        "inlineTechniqueSetXAssetCount": len(inline_q),
        "candidateCount": len(candidates),
        "candidates": candidates,
        "assets": asset_rows,
        "noCandidatePromoted": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = build(a.expanded)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
