#!/usr/bin/env python3
"""Fail-closed per-zone T6 retail XAnim/XModel population audit v1.

This is the resumable unit used by broader corpus population censuses. It never
defines corpus scope itself. For one already-expanded retail FastFile it:

1. derives exact top-level XAsset type counts from the raw XAsset list,
2. requires the retained structural XAnimParts census to close exactly against
   the raw type-4 count,
3. optionally consumes a pinned-native top-level XAsset trace and checks every
   source-consuming type-5 XMODEL with XModelWalker v2,
4. preserves zero-source XMODEL references as explicit identity blockers.

A zone can therefore have exact XAnim population closure while XModel identity
closure remains false. No name scan or character classification is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_native_xmodel_trace_audit_v1 import audit as audit_xmodels
from t6_raw_xasset_inventory import parse_front
from t6_xanim_retail_delta_branch_census_v3 import census as census_xanim

FORMAT = "t6-retail-zone-population-audit-v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--native-xasset-trace", type=Path)
    ap.add_argument("--expect-expanded-sha256")
    ap.add_argument("--expect-expanded-bytes", type=int)
    ap.add_argument("--expect-assets", type=int)
    ap.add_argument("--expect-xanims", type=int)
    ap.add_argument("--expect-xmodels", type=int)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--require-xanim-closed",
        action="store_true",
        help="return nonzero unless raw XAnim count and structural census close exactly",
    )
    ap.add_argument(
        "--require-source-consuming-xmodels-closed",
        action="store_true",
        help="return nonzero unless all native source-consuming XMODEL endpoints close",
    )
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    digest = sha256_bytes(data)
    if args.expect_expanded_sha256 and digest.lower() != args.expect_expanded_sha256.lower():
        raise ValueError(
            f"{args.zone}: expanded SHA-256 {digest} != {args.expect_expanded_sha256}"
        )
    if args.expect_expanded_bytes is not None and len(data) != args.expect_expanded_bytes:
        raise ValueError(
            f"{args.zone}: expanded bytes {len(data)} != {args.expect_expanded_bytes}"
        )

    front = parse_front(data)
    front.pop("_blocks", None)
    counts = front["asset_type_counts"]
    xanim_expected = int(counts.get("XANIMPARTS", 0))
    xmodel_expected = int(counts.get("XMODEL", 0))
    asset_expected = int(front["asset_count"])

    for label, actual, expected in (
        ("XAsset", asset_expected, args.expect_assets),
        ("XAnimParts", xanim_expected, args.expect_xanims),
        ("XModel", xmodel_expected, args.expect_xmodels),
    ):
        if expected is not None and actual != expected:
            raise ValueError(f"{args.zone}: {label} count {actual} != expected {expected}")

    xa = census_xanim(args.expanded)
    xanim_structural = {
        "expectedFromRawXAssetList": xanim_expected,
        "structuralRecordCount": int(xa["structuralRecordCount"]),
        "emptyPlaceholderCount": int(xa.get("emptyPlaceholderCount", 0)),
        "inlineNames": int(xa["inlineNames"]),
        "packedNames": int(xa["packedNames"]),
        "overlaps": xa["overlaps"],
        "producerCountClosesExactly": bool(xa["countClosesExactly"]),
    }
    xanim_structural["countClosesRawXAssetListExactly"] = (
        xanim_structural["producerCountClosesExactly"]
        and xanim_structural["structuralRecordCount"] == xanim_expected
    )

    xmodel = {
        "expectedFromRawXAssetList": xmodel_expected,
        "nativeTraceConfigured": args.native_xasset_trace is not None,
        "audit": None,
    }
    if args.native_xasset_trace is not None:
        xmodel["audit"] = audit_xmodels(
            args.expanded,
            args.native_xasset_trace,
            args.zone,
            asset_expected,
            xmodel_expected,
            digest,
            len(data),
        )

    xmodel_source_closed = (
        xmodel["audit"] is not None
        and xmodel["audit"]["gates"]["allSourceConsumingXModelsWalkerClosed"] is True
    )
    xmodel_identity_closed = (
        xmodel["audit"] is not None
        and xmodel["audit"]["gates"]["wholeZoneXModelPopulationClosed"] is True
    )

    out = {
        "format": FORMAT,
        "zone": args.zone,
        "expandedBytes": len(data),
        "expandedSha256": digest,
        "rawXAssetInventory": {
            "assetCount": asset_expected,
            "assetTypeCounts": counts,
            "xanimparts": xanim_expected,
            "xmodels": xmodel_expected,
        },
        "xanim": xanim_structural,
        "xmodel": xmodel,
        "gates": {
            "rawXAssetInventoryClosed": True,
            "xanimPopulationClosed": xanim_structural["countClosesRawXAssetListExactly"],
            "xmodelNativeTraceConfigured": args.native_xasset_trace is not None,
            "xmodelSourceConsumingRecordsClosed": xmodel_source_closed,
            "xmodelPopulationIdentityClosed": xmodel_identity_closed,
            "characterClassificationComplete": False,
            "semanticCoverageComplete": False,
        },
        "proofBoundary": [
            "This file closes one zone only and makes no corpus-completeness claim.",
            "XAnim population closure means every raw top-level XANIMPARTS entry is represented by the retained structural census; it is not full animation semantic coverage.",
            "XMODEL raw count is exact from the top-level XAsset list. Structural closure additionally requires a native top-level trace and XModelWalker v2 endpoint agreement.",
            "Zero-source top-level XMODEL references remain identity blockers until resolved by native pointer/backreference evidence.",
            "Character classification is a later relationship/identity layer and is never inferred from names by this audit.",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "zone": args.zone,
                "xassets": asset_expected,
                "xanims": xanim_expected,
                "xmodels": xmodel_expected,
                "gates": out["gates"],
            },
            indent=2,
            sort_keys=True,
        )
    )

    if args.require_xanim_closed and not out["gates"]["xanimPopulationClosed"]:
        return 2
    if (
        args.require_source_consuming_xmodels_closed
        and not out["gates"]["xmodelSourceConsumingRecordsClosed"]
    ):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
