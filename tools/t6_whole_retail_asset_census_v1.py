#!/usr/bin/env python3
"""Fail-closed whole-retail T6 XAnim/XModel population census wrapper.

This tool does not define the retail corpus. It consumes an explicit corpus manifest,
audits which declared expanded XFiles are actually present, derives exact top-level
XAsset counts from each XFile, and reuses the retained v3 structural XAnimParts census.

Whole-retail gates remain false unless the corpus manifest itself carries an explicit
complete-corpus claim and every declared zone is present/count-closed. XModel top-level
counts are exact XAsset-list facts, but XModel population closure remains unclaimed until
a generic structural XModel parser is wired into this wrapper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_raw_xasset_inventory import parse_front
from t6_xanim_retail_delta_branch_census_v3 import census as xanim_census

FORMAT = "t6-whole-retail-asset-census-v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("corpus manifest must be a JSON object")
    zones = obj.get("zones")
    if not isinstance(zones, list) or not zones:
        raise ValueError("corpus manifest zones must be a non-empty list")
    names: list[str] = []
    normalized: list[dict[str, Any]] = []
    for item in zones:
        if isinstance(item, str):
            row = {"zone": item}
        elif isinstance(item, dict):
            row = dict(item)
        else:
            raise ValueError("every corpus zone must be a string or object")
        zone = row.get("zone")
        if not isinstance(zone, str) or not zone or "/" in zone or "\\" in zone:
            raise ValueError(f"invalid zone name: {zone!r}")
        if zone in names:
            raise ValueError(f"duplicate zone in corpus manifest: {zone}")
        names.append(zone)
        normalized.append(row)
    obj["zones"] = normalized
    return obj


def bool_reason(value: bool, true_reason: str, false_reason: str) -> dict[str, Any]:
    return {"value": bool(value), "reason": true_reason if value else false_reason}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-manifest", type=Path, required=True)
    ap.add_argument("--expanded-root", type=Path, required=True)
    ap.add_argument("--raw-root", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit nonzero unless all whole-retail completeness gates are closed",
    )
    args = ap.parse_args()

    manifest = load_manifest(args.corpus_manifest)
    corpus_claim = manifest.get("corpusClaim") or {}
    manifest_complete = corpus_claim.get("complete") is True

    args.expanded_root.mkdir(parents=True, exist_ok=True)
    declared = [row["zone"] for row in manifest["zones"]]
    declared_set = set(declared)
    discovered_paths = sorted(args.expanded_root.glob("*.expanded"))
    discovered = [p.name[: -len(".expanded")] for p in discovered_paths]
    undeclared = sorted(set(discovered) - declared_set)

    zones: list[dict[str, Any]] = []
    missing: list[str] = []
    failed: list[str] = []
    parser_errors: list[dict[str, str]] = []

    for spec in manifest["zones"]:
        zone = spec["zone"]
        expanded = args.expanded_root / f"{zone}.expanded"
        raw = args.raw_root / f"{zone}.ff" if args.raw_root else None
        row: dict[str, Any] = {
            "zone": zone,
            "declared": True,
            "expandedPath": str(expanded),
            "rawPath": str(raw) if raw else None,
            "present": expanded.is_file(),
            "expected": {
                "rawSha256": spec.get("expectedRawSha256"),
                "expandedSha256": spec.get("expectedExpandedSha256"),
                "xanimCount": spec.get("expectedXAnimCount"),
            },
            "xmodelStructuralParser": {
                "configured": False,
                "structuralRecordCount": None,
                "countClosesExactly": None,
                "reason": (
                    "Top-level XMODEL count is exact from the raw XAsset list, but this "
                    "wrapper does not yet have a generic whole-zone structural XModel walker."
                ),
            },
        }
        if raw and raw.is_file():
            row["rawBytes"] = raw.stat().st_size
            row["rawSha256"] = sha256_file(raw)
            exp_raw = spec.get("expectedRawSha256")
            row["rawSha256MatchesExpected"] = None if not exp_raw else row["rawSha256"] == exp_raw
        else:
            row["rawBytes"] = None
            row["rawSha256"] = None
            row["rawSha256MatchesExpected"] = None

        if not expanded.is_file():
            row["status"] = "missing-expanded"
            missing.append(zone)
            zones.append(row)
            continue

        try:
            data = expanded.read_bytes()
            front = parse_front(data)
            front.pop("_blocks", None)
            xasset_counts = front["asset_type_counts"]
            expected_xanim = int(xasset_counts.get("XANIMPARTS", 0))
            expected_xmodel = int(xasset_counts.get("XMODEL", 0))
            row.update(
                status="parsed",
                expandedBytes=len(data),
                expandedSha256=front["expanded_sha256"],
                xassetCount=front["asset_count"],
                xassetTypeCounts=xasset_counts,
                expectedXAnimCountFromXAssetList=expected_xanim,
                expectedXModelCountFromXAssetList=expected_xmodel,
            )
            exp_sha = spec.get("expectedExpandedSha256")
            row["expandedSha256MatchesExpected"] = (
                None if not exp_sha else row["expandedSha256"] == exp_sha
            )
            exp_count = spec.get("expectedXAnimCount")
            row["xanimCountMatchesManifestRegression"] = (
                None if exp_count is None else expected_xanim == int(exp_count)
            )

            xa = xanim_census(expanded)
            row["xanimStructural"] = {
                "structuralRecordCount": xa["structuralRecordCount"],
                "emptyPlaceholderCount": xa.get("emptyPlaceholderCount", 0),
                "inlineNames": xa["inlineNames"],
                "packedNames": xa["packedNames"],
                "overlaps": xa["overlaps"],
                "countClosesExactly": xa["countClosesExactly"],
            }
            if not xa["countClosesExactly"]:
                failed.append(zone)
        except Exception as exc:
            row["status"] = "parser-error"
            row["error"] = f"{type(exc).__name__}: {exc}"
            failed.append(zone)
            parser_errors.append({"zone": zone, "error": row["error"]})
        zones.append(row)

    parsed = [z for z in zones if z["status"] == "parsed"]
    all_declared_present = not missing
    all_declared_raw_inventory = len(parsed) == len(zones)
    all_declared_xanim_closed = all_declared_raw_inventory and all(
        z.get("xanimStructural", {}).get("countClosesExactly") is True for z in zones
    )
    no_undeclared = not undeclared
    corpus_complete = (
        manifest_complete and all_declared_present and no_undeclared and not parser_errors
    )
    zone_inventory_complete = corpus_complete and all_declared_raw_inventory
    xanim_population_complete = zone_inventory_complete and all_declared_xanim_closed

    # Deliberately false in v1. Exact XAsset-list XMODEL counts are retained below, but
    # population identity/structural closure is a separate proof layer.
    xmodel_population_complete = False
    semantic_coverage_complete = False

    total_xassets = sum(int(z.get("xassetCount", 0)) for z in parsed)
    total_xanim = sum(int(z.get("expectedXAnimCountFromXAssetList", 0)) for z in parsed)
    total_xmodel = sum(int(z.get("expectedXModelCountFromXAssetList", 0)) for z in parsed)
    total_xanim_structural = sum(
        int(z.get("xanimStructural", {}).get("structuralRecordCount", 0)) for z in parsed
    )

    result = {
        "format": FORMAT,
        "producer": "tools/t6_whole_retail_asset_census_v1.py",
        "corpusManifest": {
            "path": str(args.corpus_manifest),
            "format": manifest.get("format"),
            "name": manifest.get("name"),
            "claim": corpus_claim,
        },
        "inventory": {
            "zonesDeclared": len(declared),
            "zonesDiscovered": len(discovered),
            "zonesAttempted": len(zones),
            "zonesSucceeded": len(parsed),
            "zonesFailed": len(set(failed)),
            "zonesMissing": sorted(missing),
            "zonesUndeclaredOnDisk": undeclared,
            "declaredZoneNames": declared,
            "discoveredZoneNames": discovered,
        },
        "zones": zones,
        "totalsForSuccessfullyParsedDeclaredZones": {
            "xassets": total_xassets,
            "xanimpartsFromXAssetLists": total_xanim,
            "xanimpartsStructurallyIdentified": total_xanim_structural,
            "xmodelsFromXAssetLists": total_xmodel,
        },
        "declaredCorpusChecks": {
            "allDeclaredZonesPresent": all_declared_present,
            "allDeclaredZonesRawXAssetParsed": all_declared_raw_inventory,
            "allDeclaredZonesXAnimCountClosed": all_declared_xanim_closed,
            "noUndeclaredExpandedZones": no_undeclared,
            "parserErrorCount": len(parser_errors),
            "parserErrors": parser_errors,
        },
        "gates": {
            "corpusComplete": bool_reason(
                corpus_complete,
                "Manifest explicitly claims a complete retail corpus and the materialized set matches it.",
                (
                    "Whole-retail corpus completeness is unproven: the manifest must explicitly "
                    "claim completeness, every declared zone must be present, no undeclared zone "
                    "may be materialized, and parsing must be error-free."
                ),
            ),
            "zoneInventoryComplete": bool_reason(
                zone_inventory_complete,
                "Every zone in a proven-complete corpus has an exact raw XAsset inventory.",
                "Requires corpusComplete plus successful raw XAsset parsing for every declared zone.",
            ),
            "xanimPopulationComplete": bool_reason(
                xanim_population_complete,
                "Every XANIMPARTS entry in every zone of a proven-complete corpus is structurally count-closed.",
                "Requires zoneInventoryComplete and exact structural XAnim count closure in every zone.",
            ),
            "xmodelPopulationComplete": bool_reason(
                xmodel_population_complete,
                "",
                (
                    "Not closed in v1: exact top-level XMODEL XAsset counts are recorded, but a "
                    "generic whole-zone structural XModel walker/identity census is not yet wired in."
                ),
            ),
            "semanticCoverageComplete": bool_reason(
                semantic_coverage_complete,
                "",
                (
                    "Not closed by this structural census. Animation semantics, XModel relationships, "
                    "character classification, aliases, materials, and shader semantics remain separate gates."
                ),
            ),
        },
        "regressionBoundaries": [
            (
                "tools/stage18d_xanim_full_inventory.py remains independent; this wrapper does not "
                "modify or redefine any of its scoped canaries."
            ),
            (
                "The retained 18-XFile XAnim census is a regression seed, not evidence that the "
                "18-zone declaration is the complete BO2 retail corpus."
            ),
            (
                "XMODEL counts here come only from type 5 entries in each raw top-level XAsset list; "
                "they are not character classifications or structural XModel identity closure."
            ),
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "format": FORMAT,
        "zonesDeclared": len(declared),
        "zonesSucceeded": len(parsed),
        "zonesMissing": len(missing),
        "zonesFailed": len(set(failed)),
        "xanimparts": total_xanim,
        "xmodels": total_xmodel,
        "gates": {k: v["value"] for k, v in result["gates"].items()},
    }, indent=2, sort_keys=True))

    if args.strict and not all(v["value"] for v in result["gates"].values()):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
