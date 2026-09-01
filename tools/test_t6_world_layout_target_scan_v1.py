#!/usr/bin/env python3
"""Regression for conservative cross-map T6 layout target scanning."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from t6_world_layout_target_scan_v1 import scan_document, scan_files


def main() -> int:
    reference_only = {
        "format": "synthetic-layout",
        "map": "mp_reference_only",
        "formatTable": {
            str(fmt): {
                "worldVertFormat": fmt,
                "vertexCount": 999,
                "description": f"reference format {fmt}",
            }
            for fmt in range(9)
        },
        "metadata": {"worldVertFormat": 8},
    }
    ref = scan_document(
        reference_only,
        source="reference.layout.json",
        target_formats={4, 5, 7, 8},
    )
    assert ref["observedFormats"] == []
    assert ref["targetHits"] == []
    assert ref["weakOnlyFormats"] == list(range(9))
    assert ref["strongEvidenceCount"] == 0
    assert ref["weakCandidateCount"] == 10

    observed = {
        "format": "synthetic-layout",
        "map": "mp_observed",
        "observedFormats": [0, 4, 6],
        "observedFormatGroupCounts": {"4": 3, "7": 2, "8": 0},
        "surfaces": [
            {
                "surfaceIndex": 10,
                "worldVertFormat": 5,
                "vertexDataOffset0": 100,
                "vertexDataOffset1": 200,
                "vertexCount": 12,
            },
            {
                "index": 11,
                "worldVertFormat": 3,
                "vertexDataOffset0": 300,
                "vertexDataOffset1": 400,
                "vertexCount": 8,
            },
        ],
        "formatTable": {
            "8": {
                "worldVertFormat": 8,
                "vertexCount": 123,
            }
        },
    }
    obs = scan_document(
        observed,
        source="observed.layout.json",
        target_formats={4, 5, 7, 8},
    )
    assert obs["observedFormats"] == [0, 3, 4, 5, 6, 7]
    assert obs["targetHits"] == [4, 5, 7]
    assert obs["weakOnlyFormats"] == [8]
    assert any(
        row["kind"] == "explicit-observed-count"
        and row["worldVertFormat"] == 7
        for row in obs["strongEvidence"]
    )
    assert any(
        row["kind"] == "surface-or-group-record"
        and row["worldVertFormat"] == 5
        for row in obs["strongEvidence"]
    )
    assert not any(
        row["worldVertFormat"] == 8 for row in obs["strongEvidence"]
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        raid_dir = root / "derived" / "maps" / "mp_raid"
        raid_dir.mkdir(parents=True)
        raid = raid_dir / "mp_raid.layout.json"
        raid.write_text(json.dumps(reference_only | {"map": "mp_raid"}), encoding="utf-8")

        slums = root / "derived" / "maps" / "mp_slums.layout.json"
        slums.parent.mkdir(parents=True, exist_ok=True)
        slums.write_text(
            json.dumps(
                {
                    "map": "mp_slums",
                    "groups": [
                        {
                            "groupIndex": 2,
                            "worldVertFormat": 8,
                            "vd0Offset": 1024,
                            "vd1Offset": 2048,
                            "vertexCount": 16,
                        }
                    ],
                    "formatTable": {
                        "4": {"worldVertFormat": 4, "vertexCount": 1}
                    },
                }
            ),
            encoding="utf-8",
        )

        raid_report = scan_files([root], map_name="mp_raid")
        assert raid_report["matchedLayoutFileCount"] == 1
        assert raid_report["observedFormats"] == []
        assert raid_report["targetHits"] == []
        assert raid_report["targetHit"] is False

        slums_report = scan_files([root], map_name="mp_slums")
        assert slums_report["matchedLayoutFileCount"] == 1
        assert slums_report["observedFormats"] == [8]
        assert slums_report["targetHits"] == [8]
        assert slums_report["targetHit"] is True
        assert slums_report["reports"][0]["weakOnlyFormats"] == [4]

        all_report = scan_files([root])
        assert all_report["matchedLayoutFileCount"] == 2
        assert all_report["observedFormats"] == [8]
        assert all_report["targetHits"] == [8]

    print("PASS t6_world_layout_target_scan_v1 conservative observation regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
