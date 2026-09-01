#!/usr/bin/env python3
"""Regression for layout-driven raw T6 vd1 stride proof."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from t6_world_vd1_layout_census_v1 import census, derive_allocations, extract_group_records


def main() -> int:
    layout = {
        "map": "mp_synthetic",
        "groups": [
            {
                "groupIndex": 0,
                "worldVertFormat": 4,
                "vd0Offset": 0,
                "vd1Offset": 0,
                "vertexCount": 3,
                "surfaceIndices": [1, 2],
            },
            {
                "groupIndex": 1,
                "worldVertFormat": 8,
                "vd0Offset": 128,
                "vd1Offset": 36,
                "vertexCount": 2,
                "surfaceIndices": [3],
            },
        ],
        # This deliberately looks numerically plausible but is reference-only
        # and must never become raw allocation evidence.
        "formatTable": {
            "7": {
                "worldVertFormat": 7,
                "vd0Offset": 999,
                "vd1Offset": 0,
                "vertexCount": 3,
            }
        },
    }
    records, rejected = extract_group_records(layout)
    assert len(records) == 2
    assert sorted(row["worldVertFormat"] for row in records) == [4, 8]
    assert any(row["reason"] == "reference-table-path" for row in rejected)

    raw = bytes(range(76))
    derived = derive_allocations(records, raw)
    assert derived["blockers"] == []
    assert derived["observedRawStrideByFormat"] == {"4": [12], "8": [20]}

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        layout_path = root / "mp_synthetic.layout.json"
        vd1_path = root / "mp_synthetic.gfxworld.vd1.bin"
        layout_path.write_text(json.dumps(layout), encoding="utf-8")
        vd1_path.write_bytes(raw)
        doc = census(
            map_name="mp_synthetic",
            layout_path=layout_path,
            vd1_path=vd1_path,
        )
        assert doc["format"] == "t6-world-vd1-layout-census-v1"
        assert doc["observedRawStrideByFormat"] == {"4": [12], "8": [20]}
        assert doc["formatSummary"]["4"]["formulaSupportedByThisFixture"] is True
        assert doc["formatSummary"]["8"]["formulaSupportedByThisFixture"] is True
        assert doc["stats"]["unambiguousAllocationCount"] == 2
        assert doc["stats"]["blockedAllocationCount"] == 0

    # Same offset claimed by two formats is not promotable even when the raw
    # span happens to divide their shared count.
    ambiguous = [
        {"vd0Offset": 0, "vd1Offset": 0, "vertexCount": 2, "worldVertFormat": 4},
        {"vd0Offset": 128, "vd1Offset": 0, "vertexCount": 2, "worldVertFormat": 7},
        {"vd0Offset": 256, "vd1Offset": 24, "vertexCount": 1, "worldVertFormat": 6},
    ]
    blocked = derive_allocations(ambiguous, bytes(36))
    assert "4" not in blocked["observedRawStrideByFormat"]
    assert "7" not in blocked["observedRawStrideByFormat"]
    assert any(
        row["reason"] == "shared-offset-has-multiple-world-formats"
        for row in blocked["blockers"]
    )

    print("PASS t6_world_vd1_layout_census_v1 strict raw allocation regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
