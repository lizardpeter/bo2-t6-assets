#!/usr/bin/env python3
"""Aggregate per-zone native XModel identity closures over the available corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-native-xmodel-available-census-v1"
ZONE_FORMAT = "t6-native-xmodel-zone-identity-closure-v2"
MANIFEST_FORMAT = "t6-steam-english-population-input-manifest-v1"


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected object")
    return obj


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--population-manifest", type=Path, required=True)
    ap.add_argument("--results-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expect-available-zones", type=int)
    ap.add_argument("--expect-xmodels", type=int)
    ap.add_argument("--strict-available", action="store_true")
    a = ap.parse_args()

    manifest = load(a.population_manifest)
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ValueError(f"unexpected population manifest format {manifest.get('format')!r}")

    available = [z for z in manifest.get("zones", []) if z.get("sourceAvailable")]
    unavailable = [z for z in manifest.get("zones", []) if not z.get("sourceAvailable")]
    expected_paths = {z["path"] for z in available}
    if len(expected_paths) != len(available):
        raise ValueError("population manifest contains duplicate source-available paths")
    if a.expect_available_zones is not None and len(available) != a.expect_available_zones:
        raise ValueError(f"available zone count {len(available)} != expected {a.expect_available_zones}")

    reports: dict[str, dict[str, Any]] = {}
    report_files = sorted(a.results_root.rglob("*.xmodel-identity.json"))
    for path in report_files:
        report = load(path)
        if report.get("format") != ZONE_FORMAT:
            raise ValueError(f"{path}: unexpected zone report format {report.get('format')!r}")
        zone = report.get("zone")
        if not isinstance(zone, str) or not zone:
            raise ValueError(f"{path}: invalid zone label")
        if zone in reports:
            raise ValueError(f"duplicate zone report for {zone}")
        reports[zone] = report

    present_paths = set(reports)
    missing_reports = sorted(expected_paths - present_paths)
    extra_reports = sorted(present_paths - expected_paths)
    if extra_reports:
        raise ValueError(f"reports outside authoritative source-available manifest: {extra_reports}")

    total_keys = [
        "observedXModels",
        "sourceConsuming",
        "zeroSource",
        "sourceConsumingEndpointClosed",
        "sourceConsumingInlineNameClosed",
        "sourceConsumingPackedNameClosed",
        "sourceConsumingIdentityClosed",
        "zeroSourceNativeIdentityClosed",
        "failures",
    ]
    totals = {k: 0 for k in total_keys}
    closed_zones = 0
    zone_rows: list[dict[str, Any]] = []
    for zone in sorted(reports):
        report = reports[zone]
        counts = report.get("counts") or {}
        gates = report.get("gates") or {}
        for key in total_keys:
            totals[key] += int(counts.get(key, 0))
        closed = bool(gates) and all(bool(v) for v in gates.values())
        if closed:
            closed_zones += 1
        zone_rows.append(
            {
                "path": zone,
                "expandedBytes": report.get("expandedBytes"),
                "expandedSha256": report.get("expandedSha256"),
                "counts": counts,
                "gates": gates,
                "closed": closed,
            }
        )

    expected_xmodels_ok = a.expect_xmodels is None or totals["observedXModels"] == a.expect_xmodels
    gates = {
        "allAvailablePathsHaveReports": not missing_reports and len(reports) == len(available),
        "allAvailableZoneXModelPopulationsClosed": closed_zones == len(available),
        "availableCorpusXModelCountMatchesExpected": expected_xmodels_ok,
        "allSourceConsumingEndpointsClosed": totals["sourceConsumingEndpointClosed"] == totals["sourceConsuming"],
        "allSourceConsumingIdentitiesClosed": totals["sourceConsumingIdentityClosed"] == totals["sourceConsuming"],
        "allZeroSourceReferencesResolvedToIdentity": totals["zeroSourceNativeIdentityClosed"] == totals["zeroSource"],
        "zeroIdentityFailures": totals["failures"] == 0,
    }

    out = {
        "format": FORMAT,
        "scope": "Steam English retail FastFile catalog, source-available subset only",
        "populationManifestFormat": MANIFEST_FORMAT,
        "catalog": {
            "declaredUniqueFastFilePaths": len(manifest.get("zones", [])),
            "sourceAvailablePaths": len(available),
            "sourceUnavailablePaths": len(unavailable),
            "missingAvailableReports": missing_reports,
        },
        "availableSourcePopulation": {
            "reportedZones": len(reports),
            "closedZones": closed_zones,
            **totals,
        },
        "gates": gates,
        "zones": zone_rows,
        "proofBoundary": [
            "Every report is keyed to an exact source-available path from the retained authoritative English-retail population-input manifest.",
            "A zone is closed only when its per-zone v2 native XModel identity adapter closes all source-consuming endpoints, inline/packed name identities, and zero-source native identities.",
            "The available-corpus XModel total is a per-zone population count and is not a global unique-identity count; repeated XModels across zones remain repeated here.",
            "The source-unavailable catalog paths remain explicit blockers. Closing every available zone does not establish complete English-retail XModel population until those source bytes are recovered and audited.",
            "This aggregate makes no character classification, animation semantic, material, texture, TechniqueSet, shader, or export-fidelity claim.",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"catalog": out["catalog"], "availableSourcePopulation": out["availableSourcePopulation"], "gates": gates}, indent=2, sort_keys=True))

    if a.strict_available and not all(gates.values()):
        raise SystemExit("available-corpus native XModel census did not fully close")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
