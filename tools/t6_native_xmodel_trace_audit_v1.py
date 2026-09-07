#!/usr/bin/env python3
"""Audit one T6 FastFile XMODEL population against a native OAT XAsset trace.

Inputs are deliberately separate:
- an independently expanded retail FastFile,
- an independently captured pinned-OAT top-level XAsset trace,
- externally retained expected top-level XAsset and XMODEL counts.

Every native source-consuming XMODEL is walked with
`t6_xmodel_serialized_walker_v2`. Zero-source top-level XMODEL references are
retained as explicit identity-resolution blockers rather than silently counted
as closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from t6_material_techset_top_level_walk_v1 import parse_front
from t6_xmodel_serialized_walker_v2 import XModelWalker

TRACE_RE = re.compile(
    r"^T6_EXPANDED_XASSET index=(\d+) type=(\d+) "
    r"beforeLocal=(\d+) afterLocal=(\d+) before=(\d+) after=(\d+)$"
)
XMODEL_TYPE = 5


def parse_trace(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = TRACE_RE.fullmatch(line.strip())
        if not m:
            raise ValueError(f"{path}:{line_no}: malformed native trace line: {line!r}")
        i, typ, before_local, after_local, before, after = map(int, m.groups())
        if after_local < before_local or after < before:
            raise ValueError(f"{path}:{line_no}: decreasing native source position")
        rows.append(
            {
                "xassetIndex": i,
                "type": typ,
                "beforeLocal": before_local,
                "afterLocal": after_local,
                "sourceStart": before,
                "sourceEnd": after,
            }
        )
    return rows


def audit(
    expanded_path: Path,
    trace_path: Path,
    zone: str,
    expected_assets: int,
    expected_xmodels: int,
    expected_expanded_sha256: str | None,
    expected_expanded_bytes: int | None,
) -> dict:
    data = expanded_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_expanded_sha256 and digest.lower() != expected_expanded_sha256.lower():
        raise ValueError(
            f"{zone}: expanded SHA-256 {digest} != expected {expected_expanded_sha256}"
        )
    if expected_expanded_bytes is not None and len(data) != expected_expanded_bytes:
        raise ValueError(
            f"{zone}: expanded bytes {len(data)} != expected {expected_expanded_bytes}"
        )

    _, assets, _ = parse_front(data)
    trace = parse_trace(trace_path)
    raw_xmodels = sum(row["type"] == XMODEL_TYPE for row in assets)
    if len(assets) != expected_assets:
        raise ValueError(
            f"{zone}: raw XAsset count {len(assets)} != expected {expected_assets}"
        )
    if raw_xmodels != expected_xmodels:
        raise ValueError(
            f"{zone}: raw XMODEL count {raw_xmodels} != expected {expected_xmodels}"
        )
    if len(trace) != len(assets):
        raise ValueError(
            f"{zone}: native trace rows {len(trace)} != raw XAssets {len(assets)}"
        )
    if [row["xassetIndex"] for row in trace] != list(range(len(assets))):
        raise ValueError(f"{zone}: native XAsset indices are not exact source order")
    for native, raw in zip(trace, assets):
        if native["type"] != raw["type"]:
            raise ValueError(
                f"{zone}: native/raw XAsset type mismatch at {native['xassetIndex']}: "
                f"{native['type']} != {raw['type']}"
            )

    xmodels: list[dict] = []
    source_consuming = zero_source = matches = failures = 0
    for native, raw in zip(trace, assets):
        if native["type"] != XMODEL_TYPE:
            continue
        row = {
            **native,
            "headerRaw": f"0x{raw['headerRaw']:08X}",
            "nativeSerializedBytes": native["sourceEnd"] - native["sourceStart"],
        }
        if native["sourceEnd"] == native["sourceStart"]:
            zero_source += 1
            row["sourceKind"] = "zero-source-reference"
            row["walkerAttempted"] = False
            row["identityResolved"] = False
        else:
            source_consuming += 1
            row["sourceKind"] = "native-source-consuming"
            row["walkerAttempted"] = True
            try:
                walked = XModelWalker(data, native["sourceStart"]).walk_xmodel()
                row["walkerBlockers"] = walked["blockers"]
                row["walkerSourceEnd"] = int(walked["assetSerializedEnd"])
                row["walkerEndpointMatchesNative"] = (
                    not walked["blockers"]
                    and int(walked["assetSerializedEnd"]) == native["sourceEnd"]
                )
                row["walkerName"] = walked["xmodel"].get("name")
                row["numBones"] = walked["xmodel"].get("numBones")
                row["numSurfs"] = walked["xmodel"].get("numSurfs")
            except Exception as exc:  # fail closed and retain exact diagnostic
                row["walkerException"] = repr(exc)
                row["walkerEndpointMatchesNative"] = False
            if row.get("walkerEndpointMatchesNative"):
                matches += 1
            else:
                failures += 1
        xmodels.append(row)

    gates = {
        "rawExpectedCountsMatch": len(assets) == expected_assets
        and len(xmodels) == expected_xmodels,
        "allTopLevelXAssetsNativeTraced": len(trace) == len(assets),
        "allSourceConsumingXModelsWalkerClosed": failures == 0,
        "zeroSourceXModelReferencesResolvedToIdentity": zero_source == 0,
        "wholeZoneXModelPopulationClosed": failures == 0 and zero_source == 0,
    }
    return {
        "format": "t6-native-xmodel-trace-audit-v1",
        "zone": zone,
        "expandedPath": str(expanded_path),
        "nativeTracePath": str(trace_path),
        "expandedBytes": len(data),
        "expandedSha256": digest,
        "expectedTopLevelXAssets": expected_assets,
        "expectedXModels": expected_xmodels,
        "observedTopLevelXAssets": len(assets),
        "observedXModels": len(xmodels),
        "nativeSourceConsumingXModels": source_consuming,
        "zeroSourceXModelReferences": zero_source,
        "walkerEndpointMatchesNative": matches,
        "walkerEndpointMismatchesOrFailures": failures,
        "xmodels": xmodels,
        "gates": gates,
        "proofBoundary": [
            "Expected XAsset/XMODEL counts are external assertions and must not be inferred from the native trace being audited.",
            "Native source-consuming XMODEL endpoints are checked against XModelWalker v2 without fitted offsets.",
            "Zero-source top-level XMODEL references remain identity-resolution blockers until native pointer/backreference semantics establish their target.",
            "Names emitted by the structural walker are descriptive only and do not establish top-level ownership.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("native_trace", type=Path)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--expect-assets", type=int, required=True)
    ap.add_argument("--expect-xmodels", type=int, required=True)
    ap.add_argument("--expect-expanded-sha256")
    ap.add_argument("--expect-expanded-bytes", type=int)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--require-source-consuming-closed",
        action="store_true",
        help="fail if any source-consuming XMODEL endpoint does not close",
    )
    ap.add_argument(
        "--require-population-closed",
        action="store_true",
        help="fail unless source-consuming endpoints and zero-source identities are all closed",
    )
    args = ap.parse_args()

    out = audit(
        args.expanded,
        args.native_trace,
        args.zone,
        args.expect_assets,
        args.expect_xmodels,
        args.expect_expanded_sha256,
        args.expect_expanded_bytes,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "zone": out["zone"],
                "observedXModels": out["observedXModels"],
                "nativeSourceConsumingXModels": out["nativeSourceConsumingXModels"],
                "zeroSourceXModelReferences": out["zeroSourceXModelReferences"],
                "walkerEndpointMatchesNative": out["walkerEndpointMatchesNative"],
                "walkerEndpointMismatchesOrFailures": out[
                    "walkerEndpointMismatchesOrFailures"
                ],
                "gates": out["gates"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.require_source_consuming_closed and not out["gates"][
        "allSourceConsumingXModelsWalkerClosed"
    ]:
        return 2
    if args.require_population_closed and not out["gates"][
        "wholeZoneXModelPopulationClosed"
    ]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
