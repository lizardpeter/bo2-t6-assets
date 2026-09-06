#!/usr/bin/env python3
"""Cross-check the durable 42-row SEAL6 surface/material table against retail proof."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RETAIL = ROOT / "manifests" / "nonmap" / "retail"
OLD = RETAIL / "faction_seals_mp_seal6_smg_full_player_v1.json"
NEW = RETAIL / "seal6_smg_surface_material_assignments_v1.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def norm(name: str) -> str:
    return name[1:] if name.startswith(",") else name


def main() -> int:
    old = load(OLD)
    new = load(NEW)
    assert new["format"] == "t6-xmodel-surface-material-assignments-v1"
    assert new["source"]["expandedSha256"] == old["expandedStream"]["sha256"]
    assert new["source"]["xmodel"] == old["fullBody"]["name"] == "c_usa_mp_seal6_smg_fb"

    rows = new["assignments"]
    assert len(rows) == old["fullBody"]["surfaces"] == 42
    assert [r["surfaceIndex"] for r in rows] == list(range(42))

    raw = old["bodyMaterials"]["rawHandleSequence"]
    assert [r["handleRaw"].upper() for r in rows] == [x.upper() for x in raw]

    packed = {
        k.upper(): norm(v)
        for k, v in old["bodyMaterials"]["packedReuseCorrelations"].items()
    }
    inline = {
        int(m["firstSurfaceIndex"]): norm(m["name"])
        for m in old["bodyMaterials"]["directInline"]
    }
    assert sorted(inline) == [2, 6, 8, 12]

    for row in rows:
        i = int(row["surfaceIndex"])
        handle = row["handleRaw"].upper()
        if handle == "0XFFFFFFFF":
            assert row["handleKind"] == "inline-following"
            expected = inline[i]
        else:
            assert row["handleKind"] == "packed-reference"
            expected = packed[handle]
        assert norm(row["material"]) == expected, (i, row["material"], expected)

    lods = old["fullBody"]["lods"]
    assert [int(x["numSurfs"]) for x in lods] == [14, 10, 9, 9]
    for lod in lods:
        li = int(lod["index"])
        start = int(lod["surfIndex"])
        count = int(lod["numSurfs"])
        rr = [r for r in rows if int(r["lodIndex"]) == li]
        assert len(rr) == count
        assert [int(r["surfaceIndex"]) for r in rr] == list(range(start, start + count))
        assert [int(r["lodLocalSurfaceIndex"]) for r in rr] == list(range(count))

    assert new["summary"] == {
        "surfaces": 42,
        "lods": 4,
        "lodSurfaceCounts": [14, 10, 9, 9],
        "uniqueMaterials": 13,
        "inlineFollowingHandles": 4,
        "packedHandles": 38,
        "allAssignmentsResolved": True,
    }
    print("SEAL6 42-row surface/material retail cross-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
