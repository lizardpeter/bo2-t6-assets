#!/usr/bin/env python3
from __future__ import annotations

import t6_oat_conflict_pc_server_projection_v2 as proj


def server() -> dict:
    return {
        "format": "t6-pc-server-xasset-override-proof-v2",
        "authority": {
            "pcDedicatedServerBuild": True,
            "retailT6mpClient": False,
        },
        "pcDedicatedServer": {"exeSha256": "fixture"},
        "mpFlags": {
            "common_mp": {"allocFlagsHex": "0x00000080", "priority": 54},
            "ordinaryBuiltInMpMap": {"allocFlagsHex": "0x00008000", "priority": 57},
            "code_post_gfx_mp": {"allocFlagsHex": "0x00000008", "priority": 52},
            "patch_mp": {"allocFlagsHex": "0x00000002", "priority": 65},
        },
    }


def conflicts() -> dict:
    return {
        "format": "t6-oat-parent-dependency-conflict-census-v1",
        "authoritativeWinnerSelection": False,
        "summary": {"unresolvedConflictCount": 4},
        "conflicts": [
            {
                "conflictKey": "map-patch",
                "kind": "divergent-parent-owned-child",
                "techniqueSet": "set_a",
                "technique": "tech_a",
                "materials": ["m/a"],
                "parentOwners": ["/tmp/map_out", "/tmp/patch_out"],
            },
            {
                "conflictKey": "common-patch",
                "kind": "divergent-parent-owned-child",
                "techniqueSet": "set_b",
                "technique": "tech_b",
                "materials": ["m/b"],
                "parentOwners": ["/tmp/common_out", "/tmp/patch_out"],
            },
            {
                "conflictKey": "code-post-patch",
                "kind": "divergent-parent-owned-child",
                "techniqueSet": "set_c",
                "technique": "tech_c",
                "materials": ["m/c"],
                "parentOwners": ["/tmp/code_post_out", "/tmp/patch_out"],
            },
            {
                "conflictKey": "missing",
                "kind": "missing-parent-techniqueset-owner",
                "techniqueSet": "missing_set",
                "materials": ["m/d"],
                "parentOwners": [],
            },
        ],
    }


def main() -> int:
    result = proj.build(conflicts(), server())
    s = result["summary"]
    assert result["authoritativeForPcDedicatedServerBuild"] is True
    assert result["authoritativeForRetailClient"] is False
    assert s["sourceConflictCount"] == 4
    assert s["serverUniquePredictionCount"] == 3
    assert s["ownerUniverseGapCount"] == 1
    assert s["unmappedServerZoneClassCount"] == 0
    assert s["serverPriorityTieCount"] == 0
    assert s["authoritativeRetailClientWinnerCount"] == 0
    assert s["serverPredictedPrimaryRootCounts"] == {"/tmp/patch_out": 3}
    assert [r["serverPredictedPrimaryRoot"] for r in result["projections"][:3]] == [
        "/tmp/patch_out", "/tmp/patch_out", "/tmp/patch_out"
    ]
    assert result["projections"][3]["serverPredictedPrimaryRoot"] is None

    bad = server()
    bad["authority"]["retailT6mpClient"] = True
    try:
        proj.build(conflicts(), bad)
    except proj.ProjectionError:
        pass
    else:
        raise AssertionError("retail-client authority must be rejected")

    print("PASS: code_post_gfx_mp projection is exact-server-only and cannot promote retail winners")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
