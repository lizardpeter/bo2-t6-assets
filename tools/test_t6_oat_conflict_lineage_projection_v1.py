#!/usr/bin/env python3
from __future__ import annotations

import t6_oat_conflict_lineage_projection_v1 as projection


def doc(owners: list[str]) -> dict:
    return {
        "format": "t6-oat-parent-dependency-conflict-census-v1",
        "authoritativeWinnerSelection": False,
        "conflicts": [{
            "conflictKey": "abc",
            "kind": "divergent-parent-owned-child",
            "techniqueSet": "set",
            "technique": "tech",
            "declaredTechniqueTypes": ["lit"],
            "materials": ["m"],
            "parentOwners": owners,
        }],
    }


def main() -> int:
    # Current lineage hypothesis: patch 0x8 => priority 13, ordinary map
    # 0x8000 => priority 5.  Projection must remain non-authoritative.
    result = projection.build(
        doc(["/tmp/map_out", "/tmp/patch_out"]),
        {"/tmp/map_out": 0x8000, "/tmp/patch_out": 0x8},
    )
    assert result["authoritative"] is False
    assert result["authorityState"] == "lineage_projection_only"
    assert result["summary"]["uniqueLineagePredictionCount"] == 1
    assert result["summary"]["authoritativeWinnerCount"] == 0
    row = result["projections"][0]
    assert row["lineagePredictedPrimaryRoot"] == "/tmp/patch_out"
    assert row["projectionState"] == "unique-lineage-priority-maximum"
    assert row["authoritative"] is False

    # Equal priorities cannot be ordered without load-order proof.
    tie = projection.build(
        doc(["/tmp/a", "/tmp/b"]),
        {"/tmp/a": 0x8, "/tmp/b": 0x8},
    )
    assert tie["summary"]["lineagePriorityTieCount"] == 1
    assert tie["projections"][0]["lineagePredictedPrimaryRoot"] is None
    assert tie["projections"][0]["projectionState"] == "lineage-priority-tie-load-order-required"

    # Missing root metadata remains visible and non-predicted.
    missing = projection.build(
        doc(["/tmp/map_out", "/tmp/unknown"]),
        {"/tmp/map_out": 0x8000},
    )
    assert missing["summary"]["unmappedConflictCount"] == 1
    assert missing["projections"][0]["lineagePredictedPrimaryRoot"] is None
    assert missing["projections"][0]["unmappedParentOwners"] == ["/tmp/unknown"]

    print("PASS: OAT conflict lineage projection never promotes lineage to authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
