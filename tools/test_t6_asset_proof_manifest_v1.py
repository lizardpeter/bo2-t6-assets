#!/usr/bin/env python3
"""Deterministic regressions for t6_asset_proof_manifest_v1."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from t6_asset_proof_manifest_v1 import AssetProofError, LIFECYCLE, validate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GOLDEN = ROOT / "manifests" / "nonmap" / "retail" / "seal6_smg_golden_asset_proof_v1.json"


def must_fail(doc: dict, needle: str) -> None:
    try:
        validate(doc)
    except AssetProofError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected fail-closed error containing {needle!r}")


def main() -> int:
    doc = json.loads(GOLDEN.read_text(encoding="utf-8"))
    summary = validate(doc)
    assert summary["assetId"] == "golden:seal6-smg-lod0-sixclip-v1"
    assert summary["assetType"] == "GOLDEN_FIXTURE"
    assert summary["lifecycleStage"] == "semantically_validated"
    assert summary["lifecycleOrdinal"] == LIFECYCLE.index("semantically_validated")
    assert summary["exactClaim"] is True
    assert summary["dependencyCounts"]["resolved"] == 5
    assert summary["dependencyCounts"]["ambiguous"] == 0
    assert summary["validationCounts"] == {"pass": 5, "fail": 0, "pending": 0}

    inv = doc["invariants"]
    assert (inv["surfaces"], inv["vertices"], inv["triangles"]) == (14, 13490, 14968)
    assert (inv["joints"], inv["materials"], inv["fps"]) == (102, 12, 30)
    expected = {
        "pb_stand_alert": 383,
        "pb_stand_ads": 90,
        "pb_smg_sprint": 46,
        "pb_combatrun_forward_loop": 50,
        "pb_standjump_takeoff": 27,
        "pt_stand_shoot_auto": 18,
    }
    assert {row["name"]: row["frames"] for row in inv["animations"]} == expected

    bad = copy.deepcopy(doc)
    bad["dependencies"][0]["status"] = "ambiguous"
    must_fail(bad, "unresolved/ambiguous dependencies")

    bad = copy.deepcopy(doc)
    bad["validations"][0]["status"] = "pending"
    must_fail(bad, "semantically_validated claim")

    bad = copy.deepcopy(doc)
    bad["lifecycleStage"] = "exported"
    must_fail(bad, "semantically_validated cannot pass")

    bad = copy.deepcopy(doc)
    bad["sources"][0]["sha256"] = "deadbeef"
    must_fail(bad, "64-hex SHA-256")

    bad = copy.deepcopy(doc)
    bad["exactClaim"] = True
    bad["lifecycleStage"] = "dependency_closed"
    bad["stages"]["exported"]["status"] = "pending"
    bad["stages"]["semantically_validated"]["status"] = "pending"
    must_fail(bad, "exactClaim requires semantically_validated")

    print("PASS: T6 asset proof manifest v1 + SEAL6 golden fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
