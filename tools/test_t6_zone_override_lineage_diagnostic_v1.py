#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_zone_override_lineage_diagnostic_v1 as M


def expect_error(fn, text: str) -> None:
    try:
        fn()
    except Exception as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError(f"expected error containing {text!r}")


def main() -> int:
    # Current concrete lineage prediction: ordinary level/map 0x8000 (priority 5)
    # versus patch 0x8 (priority 13) predicts patch, but authority MUST remain false.
    rows = [
        M.Candidate("mp_nuketown_2020", 0x8000, "OpenBO2 Com_LoadLevelFastFiles lineage", 1),
        M.Candidate("patch_mp", 0x8, "T6 reconstruction DB_ZONE_PATCH lineage", 0),
    ]
    result = M.diagnose(rows)
    assert result["authoritative"] is False
    assert result["authorityState"] == "lineage_prediction_only"
    assert result["lineagePredictedPrimary"] == "patch_mp"
    assert result["lineagePriorityOrder"] == ["patch_mp", "mp_nuketown_2020"]
    assert {c["label"]: c["priority"] for c in result["candidates"]} == {
        "patch_mp": 13,
        "mp_nuketown_2020": 5,
    }

    # Equality exercises the inspected >= rule: later load wins only as a lineage prediction.
    equal = M.diagnose([
        M.Candidate("old", 0x8, "synthetic", 0),
        M.Candidate("new", 0x8, "synthetic", 1),
    ])
    assert equal["authoritative"] is False
    assert equal["lineagePredictedPrimary"] == "new"
    assert equal["events"][-1]["lineageWouldOverride"] is True

    # Unknown zone flags fail instead of receiving an invented priority.
    expect_error(
        lambda: M.diagnose([
            M.Candidate("known", 0x8, "synthetic", 0),
            M.Candidate("unknown", 0x123456, "synthetic", 1),
        ]),
        "unknown lineage zone flag",
    )

    # Input parser rejects ambiguous load order and malformed candidate sets.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bad = root / "bad.json"
        bad.write_text(json.dumps({"candidates": [
            {"label": "a", "zoneFlag": "0x8", "loadOrdinal": 0},
            {"label": "b", "zoneFlag": "0x8000", "loadOrdinal": 0},
        ]}), encoding="utf-8")
        expect_error(lambda: M.load_candidates(bad), "loadOrdinal values must be unique")

    print("t6_zone_override_lineage_diagnostic_v1: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
