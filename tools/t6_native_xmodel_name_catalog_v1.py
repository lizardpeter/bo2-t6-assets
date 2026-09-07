#!/usr/bin/env python3
"""Build an exact native-name/provenance catalog from closed XModel zone reports.

This intentionally groups only by exact pinned-native XModel name string. Equal
names across zones are useful export/classification keys, but they are NOT
promoted to cross-zone payload byte identity by this catalog.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

FORMAT = "t6-native-xmodel-name-catalog-v1"
ZONE_FORMAT = "t6-native-xmodel-zone-identity-closure-v2"
MANIFEST_FORMAT = "t6-steam-english-population-input-manifest-v1"


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def valid_name(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value != "<null>"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--population-manifest", type=Path, required=True)
    ap.add_argument("--results-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expect-available-zones", type=int)
    ap.add_argument("--expect-occurrences", type=int)
    ap.add_argument("--require-closed", action="store_true")
    a = ap.parse_args()

    manifest = load(a.population_manifest)
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ValueError(f"unexpected population manifest format {manifest.get('format')!r}")
    available = [z for z in manifest.get("zones", []) if z.get("sourceAvailable")]
    expected_paths = {z["path"] for z in available}
    if len(expected_paths) != len(available):
        raise ValueError("population manifest has duplicate source-available paths")
    if a.expect_available_zones is not None and len(available) != a.expect_available_zones:
        raise ValueError(f"available zones {len(available)} != expected {a.expect_available_zones}")

    reports: dict[str, dict[str, Any]] = {}
    for path in sorted(a.results_root.rglob("*.xmodel-identity.json")):
        obj = load(path)
        if obj.get("format") != ZONE_FORMAT:
            raise ValueError(f"{path}: unexpected report format {obj.get('format')!r}")
        zone = obj.get("zone")
        if not isinstance(zone, str) or not zone:
            raise ValueError(f"{path}: invalid zone")
        if zone in reports:
            raise ValueError(f"duplicate report for {zone}")
        reports[zone] = obj

    report_paths = set(reports)
    missing_reports = sorted(expected_paths - report_paths)
    extra_reports = sorted(report_paths - expected_paths)
    if extra_reports:
        raise ValueError(f"reports outside authoritative available set: {extra_reports}")

    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failures: list[dict[str, Any]] = []
    source_consuming = 0
    zero_source = 0
    closed_zones = 0

    for zone in sorted(reports):
        report = reports[zone]
        gates = report.get("gates") or {}
        if gates and all(bool(v) for v in gates.values()):
            closed_zones += 1
        else:
            failures.append({"zone": zone, "reason": "zone report gates are not all closed"})
        for row in report.get("xmodels", []):
            idx = int(row.get("xassetIndex", -1))
            name = row.get("nativeResolvedName")
            if row.get("identityClosed") is not True:
                failures.append({"zone": zone, "xassetIndex": idx, "reason": "identityClosed is not true"})
                continue
            if not valid_name(name):
                failures.append({"zone": zone, "xassetIndex": idx, "reason": "native resolved name is null/invalid"})
                continue
            source_kind = row.get("sourceKind")
            if source_kind == "native-source-consuming":
                source_consuming += 1
            elif source_kind == "zero-source-reference":
                zero_source += 1
            else:
                failures.append({"zone": zone, "xassetIndex": idx, "reason": f"unknown sourceKind {source_kind!r}"})
                continue
            by_name[name].append(
                {
                    "zone": zone,
                    "xassetIndex": idx,
                    "headerRaw": row.get("headerRaw"),
                    "sourceKind": source_kind,
                    "sourceStart": row.get("sourceStart"),
                    "sourceEnd": row.get("sourceEnd"),
                    "nativeSerializedBytes": row.get("nativeSerializedBytes"),
                    "resolvedOwnerIndex": row.get("resolvedOwnerIndex"),
                    "resolvedSeenEarlier": row.get("resolvedSeenEarlier"),
                    "nameIdentityMethod": row.get("nameIdentityMethod") or row.get("identityMethod"),
                }
            )

    names = []
    for name in sorted(by_name):
        occ = sorted(by_name[name], key=lambda x: (x["zone"], x["xassetIndex"]))
        zones = sorted({x["zone"] for x in occ})
        sc = sum(x["sourceKind"] == "native-source-consuming" for x in occ)
        zs = sum(x["sourceKind"] == "zero-source-reference" for x in occ)
        names.append(
            {
                "nativeName": name,
                "occurrences": len(occ),
                "zoneCount": len(zones),
                "zones": zones,
                "sourceConsumingOccurrences": sc,
                "zeroSourceOccurrences": zs,
                "crossZoneRepeatedName": len(zones) > 1,
                "occurrenceRows": occ,
            }
        )

    occurrences = sum(len(v) for v in by_name.values())
    expected_occurrences_ok = a.expect_occurrences is None or occurrences == a.expect_occurrences
    gates = {
        "allAvailablePathsHaveReports": not missing_reports and len(reports) == len(available),
        "allAvailableZoneReportsClosed": closed_zones == len(available),
        "allXModelOccurrencesHaveClosedNativeNames": not failures,
        "occurrenceCountMatchesExpected": expected_occurrences_ok,
    }
    out = {
        "format": FORMAT,
        "scope": "Exact native-resolved XModel name/provenance catalog for the source-available Steam English FastFile subset",
        "catalog": {
            "sourceAvailableZones": len(available),
            "reportedZones": len(reports),
            "closedZones": closed_zones,
            "missingReports": missing_reports,
            "xmodelOccurrences": occurrences,
            "sourceConsumingOccurrences": source_consuming,
            "zeroSourceOccurrences": zero_source,
            "exactNativeNames": len(names),
            "namesRepeatedAcrossZones": sum(n["crossZoneRepeatedName"] for n in names),
        },
        "gates": gates,
        "failures": failures,
        "names": names,
        "proofBoundary": [
            "Every occurrence comes from a per-zone v2 report whose XModel identity was closed through native source endpoint/name or native resolved-reference evidence.",
            "Names are grouped by exact case-sensitive pinned-native XModel name string only; there is no fuzzy normalization or prefix/suffix inference.",
            "Equal native names across zones are retained as repeated-name provenance, not promoted to cross-zone payload byte identity.",
            "This catalog does not classify characters, bodies, heads, gear, weapons, vehicles, props, maps, or any other semantic model category.",
            "The 82 source-unavailable English-retail FastFiles remain outside this available-corpus name catalog and therefore continue to block whole-English-retail model completeness."
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"catalog": out["catalog"], "gates": gates, "failureCount": len(failures)}, indent=2, sort_keys=True))
    if a.require_closed and not all(gates.values()):
        raise SystemExit("native XModel name catalog did not fully close")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
