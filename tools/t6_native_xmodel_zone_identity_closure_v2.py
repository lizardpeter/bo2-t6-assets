#!/usr/bin/env python3
"""Fail-closed native identity reconciliation for one T6 XModel zone.

This adapter joins three independently produced views of a retail FastFile:
  1. the raw top-level XAsset table parsed from the expanded stream,
  2. pinned native OAT source-consumption endpoints, and
  3. pinned native OAT resolved XAsset identities.

Source-consuming XModels must always close structurally against the native
source endpoint. Inline XModel names additionally require exact walker/native
string equality. Packed XModel names consume no source XString bytes, so their
identity is accepted only when the fixed-record name pointer is itself packed
and the pinned native loader resolves the real XModel object to a non-null
name. Zero-source top-level XModel references are likewise native-identity
closed and are never inferred from adjacency or byte scanning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from t6_clipmap_serialized_walker import is_inline, ptr_kind
from t6_material_techset_top_level_walk_v1 import parse_front
from t6_xmodel_serialized_walker_v2 import XModelWalker

FORMAT = "t6-native-xmodel-zone-identity-closure-v2"
SOURCE_PAT = re.compile(
    r"^T6_EXPANDED_XASSET index=(\d+) type=(\d+) beforeLocal=(\d+) "
    r"afterLocal=(\d+) before=(\d+) after=(\d+)$"
)
IDENT_PAT = re.compile(
    r"^T6_RESOLVED_XASSET index=(\d+) type=(\d+) rawHeader=0x([0-9a-fA-F]+) "
    r"resolved=0x([0-9a-fA-F]+) resolvedOwnerIndex=(\d+) resolvedSeenEarlier=(\d+)"
    r"(?: xmodelName=(.*))?$"
)


def valid_native_name(name: str | None) -> bool:
    return bool(name) and name != "<null>"


def parse_source_trace(path: Path) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = SOURCE_PAT.fullmatch(line.strip())
        if not m:
            raise ValueError(f"{path}: bad source trace line {line!r}")
        i, t, before_local, after_local, before, after = map(int, m.groups())
        rows.append(
            {
                "xassetIndex": i,
                "type": t,
                "beforeLocal": before_local,
                "afterLocal": after_local,
                "sourceStart": before,
                "sourceEnd": after,
            }
        )
    return rows


def parse_identity_trace(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = IDENT_PAT.fullmatch(line.strip())
        if not m:
            raise ValueError(f"{path}: bad identity trace line {line!r}")
        i, t, raw, resolved, owner, seen, xname = m.groups()
        rows.append(
            {
                "xassetIndex": int(i),
                "type": int(t),
                "rawHeader": int(raw, 16),
                "resolvedPointerNonzero": int(resolved, 16) != 0,
                "resolvedOwnerIndex": int(owner),
                "resolvedSeenEarlier": bool(int(seen)),
                "xmodelName": xname,
            }
        )
    return rows


def reconcile(
    data: bytes,
    source: list[dict[str, int]],
    identities: list[dict[str, Any]],
    zone: str,
    *,
    expected_top_level_xassets: int | None = None,
    expected_xmodels: int | None = None,
) -> dict[str, Any]:
    _blocks, assets, _body = parse_front(data)
    if len(source) != len(assets) or len(identities) != len(assets):
        raise ValueError(
            f"{zone}: trace/table length mismatch source={len(source)} assets={len(assets)} identities={len(identities)}"
        )
    if expected_top_level_xassets is not None and len(assets) != expected_top_level_xassets:
        raise ValueError(
            f"{zone}: top-level XAsset count {len(assets)} != expected {expected_top_level_xassets}"
        )
    observed_xmodels = sum(a["type"] == 5 for a in assets)
    if expected_xmodels is not None and observed_xmodels != expected_xmodels:
        raise ValueError(f"{zone}: XModel count {observed_xmodels} != expected {expected_xmodels}")

    rows: list[dict[str, Any]] = []
    counts = {
        "observedXModels": 0,
        "sourceConsuming": 0,
        "zeroSource": 0,
        "sourceConsumingEndpointClosed": 0,
        "sourceConsumingInlineNameClosed": 0,
        "sourceConsumingPackedNameClosed": 0,
        "sourceConsumingIdentityClosed": 0,
        "zeroSourceNativeIdentityClosed": 0,
        "failures": 0,
    }

    for asset, src, ident in zip(assets, source, identities):
        if src["xassetIndex"] != ident["xassetIndex"] or src["xassetIndex"] != asset["xassetIndex"]:
            raise ValueError(f"{zone}: XAsset index mismatch: {asset!r} {src!r} {ident!r}")
        if src["type"] != ident["type"] or src["type"] != asset["type"]:
            raise ValueError(f"{zone}: XAsset type mismatch at {asset['xassetIndex']}")
        if ident["rawHeader"] != asset["headerRaw"]:
            raise ValueError(f"{zone}: raw XAsset header mismatch at {asset['xassetIndex']}")
        if asset["type"] != 5:
            continue

        counts["observedXModels"] += 1
        rec: dict[str, Any] = {
            "xassetIndex": asset["xassetIndex"],
            "headerRaw": f"0x{asset['headerRaw']:08X}",
            "sourceStart": src["sourceStart"],
            "sourceEnd": src["sourceEnd"],
            "nativeSerializedBytes": src["sourceEnd"] - src["sourceStart"],
            "nativeResolvedName": ident["xmodelName"],
            "resolvedOwnerIndex": ident["resolvedOwnerIndex"],
            "resolvedSeenEarlier": ident["resolvedSeenEarlier"],
        }

        if src["sourceEnd"] != src["sourceStart"]:
            counts["sourceConsuming"] += 1
            rec["sourceKind"] = "native-source-consuming"
            if src["sourceStart"] + 4 > len(data):
                rec["walkerException"] = "XModel fixed-record name pointer falls beyond expanded stream"
                rec["walkerEndpointMatchesNative"] = False
                rec["nameIdentityClosed"] = False
                rec["identityClosed"] = False
                counts["failures"] += 1
                rows.append(rec)
                continue

            name_ptr = int.from_bytes(data[src["sourceStart"] : src["sourceStart"] + 4], "little")
            name_pointer = ptr_kind(name_ptr)
            rec["namePointer"] = name_pointer
            try:
                walked = XModelWalker(data, src["sourceStart"]).walk_xmodel()
                walker_name = walked["xmodel"].get("name")
                endpoint_closed = not walked["blockers"] and int(walked["assetSerializedEnd"]) == src["sourceEnd"]
                rec["walkerName"] = walker_name
                rec["walkerSourceEnd"] = int(walked["assetSerializedEnd"])
                rec["walkerBlockers"] = walked["blockers"]
                rec["walkerEndpointMatchesNative"] = endpoint_closed
                if endpoint_closed:
                    counts["sourceConsumingEndpointClosed"] += 1

                if is_inline(name_ptr):
                    rec["nameIdentityMethod"] = "inline serialized XString + exact native-name equality"
                    rec["nativeNameMatchesWalker"] = ident["xmodelName"] == walker_name
                    rec["nameIdentityClosed"] = rec["nativeNameMatchesWalker"] and valid_native_name(ident["xmodelName"])
                    if rec["nameIdentityClosed"]:
                        counts["sourceConsumingInlineNameClosed"] += 1
                elif name_pointer["kind"] == "packed":
                    rec["nameIdentityMethod"] = "packed XString pointer + pinned native loader resolved XModel object name"
                    rec["nativeNameMatchesWalker"] = None
                    rec["nameIdentityClosed"] = (
                        walker_name is None
                        and valid_native_name(ident["xmodelName"])
                        and ident["resolvedPointerNonzero"]
                    )
                    if rec["nameIdentityClosed"]:
                        counts["sourceConsumingPackedNameClosed"] += 1
                else:
                    rec["nameIdentityMethod"] = "unsupported null/non-inline name pointer"
                    rec["nativeNameMatchesWalker"] = None
                    rec["nameIdentityClosed"] = False
            except Exception as exc:
                rec["walkerException"] = repr(exc)
                rec["walkerEndpointMatchesNative"] = False
                rec["nativeNameMatchesWalker"] = False
                rec["nameIdentityClosed"] = False

            rec["identityClosed"] = bool(rec.get("walkerEndpointMatchesNative")) and bool(rec.get("nameIdentityClosed"))
            if rec["identityClosed"]:
                counts["sourceConsumingIdentityClosed"] += 1
            else:
                counts["failures"] += 1
        else:
            counts["zeroSource"] += 1
            rec["sourceKind"] = "zero-source-reference"
            rec["identityMethod"] = "pinned native OAT resolved top-level XAsset object name"
            rec["identityClosed"] = valid_native_name(ident["xmodelName"]) and ident["resolvedPointerNonzero"]
            if rec["identityClosed"]:
                counts["zeroSourceNativeIdentityClosed"] += 1
            else:
                counts["failures"] += 1
        rows.append(rec)

    gates = {
        "rawXModelCountMatchesExpected": expected_xmodels is None or counts["observedXModels"] == expected_xmodels,
        "allSourceConsumingEndpointsClosed": counts["sourceConsumingEndpointClosed"] == counts["sourceConsuming"],
        "allSourceConsumingXModelsIdentityClosed": counts["sourceConsumingIdentityClosed"] == counts["sourceConsuming"],
        "allZeroSourceXModelReferencesResolvedToIdentity": counts["zeroSourceNativeIdentityClosed"] == counts["zeroSource"],
        "wholeZoneXModelPopulationClosed": counts["failures"] == 0 and counts["observedXModels"] == observed_xmodels,
    }
    return {
        "format": FORMAT,
        "zone": zone,
        "expandedBytes": len(data),
        "expandedSha256": hashlib.sha256(data).hexdigest(),
        "topLevelXAssets": len(assets),
        "counts": counts,
        "gates": gates,
        "xmodels": rows,
        "proofBoundary": [
            "Every source-consuming XModel requires an independent structural-walker endpoint equal to the exact pinned native source endpoint, with zero walker blockers.",
            "An inline XModel name pointer requires exact equality between the source-walker XString and the pinned native resolved XModel name.",
            "A packed XModel name pointer consumes no source XString bytes; identity is promoted only when the raw fixed-record name pointer is structurally classified as packed and the pinned native loader resolves the real XModel object to a non-null name.",
            "Zero-source top-level XModel references are promoted only when the pinned native loader resolves the real top-level XAsset to a non-null XModel object with a non-null object name.",
            "Resolved process addresses are used only as a same-run non-null check and are not persisted as cross-run identities.",
            "No source-byte name scan, adjacency inference, surface similarity, or visual matching is used for packed-name or zero-source identity.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--source-trace", type=Path, required=True)
    ap.add_argument("--identity-trace", type=Path, required=True)
    ap.add_argument("--expect-top-level-xassets", type=int)
    ap.add_argument("--expect-xmodels", type=int)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--require-closed", action="store_true")
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    out = reconcile(
        data,
        parse_source_trace(args.source_trace),
        parse_identity_trace(args.identity_trace),
        args.zone,
        expected_top_level_xassets=args.expect_top_level_xassets,
        expected_xmodels=args.expect_xmodels,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"zone": args.zone, "counts": out["counts"], "gates": out["gates"]}, indent=2, sort_keys=True))
    if args.require_closed and not all(out["gates"].values()):
        raise SystemExit(f"{args.zone}: native XModel identity closure did not fully close")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
