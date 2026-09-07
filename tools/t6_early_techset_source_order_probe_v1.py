#!/usr/bin/env python3
"""Diagnostic prefix probe for the exact early T6 XAsset source-order walker.

This does not establish ownership and does not alter the proof walker. It runs
fresh exact q0..qN replays for progressively longer prefixes and records the
first exception so retail CI can expose the precise loader boundary that still
needs implementation. A failed prefix remains failed; there is no cursor skip,
scan, resynchronization, or inferred start.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from t6_early_techset_source_order_walk_v1 import walk


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--end-asset", type=int, default=20)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    probes = []
    first_failure = None
    for end in range(a.end_asset + 1):
        try:
            report = walk(a.expanded, 0, end, set())
            row = report["rows"][-1]
            probes.append({
                "endAssetIndex": end,
                "status": "ok",
                "sourceEnd": report["sourceEnd"],
                "lastAsset": {
                    "xassetIndex": row["xassetIndex"],
                    "xassetType": row["xassetType"],
                    "xassetTypeName": row["xassetTypeName"],
                    "sourceStart": row["sourceStart"],
                    "sourceEnd": row["sourceEnd"],
                    "serializedBytes": row["serializedBytes"],
                },
            })
        except Exception as exc:
            failure = {
                "endAssetIndex": end,
                "status": "failed",
                "errorType": type(exc).__name__,
                "error": str(exc),
            }
            probes.append(failure)
            first_failure = failure
            break

    out = {
        "format": "t6-early-techset-source-order-prefix-probe-v1",
        "requestedEndAssetIndex": a.end_asset,
        "firstFailure": first_failure,
        "probes": probes,
        "diagnosticOnly": True,
        "proofBoundary": (
            "Each successful entry is a fresh exact source-order replay beginning at q0. "
            "The first failed prefix is reported without skipping, scanning, resynchronizing, or promoting any later byte offset."
        ),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 1 if first_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
