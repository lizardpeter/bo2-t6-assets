#!/usr/bin/env python3
"""Aggregate per-zone population audits over the 297-path Steam English catalog.

This is a proof-preserving join, not a discovery tool. The population-input
manifest remains authoritative for which paths exist in scope and which source
bytes are currently available. Every sourceAvailable path must have exactly one
per-zone audit result; unavailable paths stay explicit blockers.

The aggregate never upgrades English-retail scope to all-language whole-retail
scope and never upgrades source availability to depot byte identity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-steam-english-population-census-aggregate-v1"
INPUT_FORMAT = "t6-steam-english-population-input-manifest-v1"
ZONE_FORMAT = "t6-retail-zone-population-audit-v1"


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def result_name(path: str) -> str:
    # Full catalog path is encoded so identical basenames in different zone
    # folders cannot collide in the shard result directory.
    return path.replace("/", "__") + ".population.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--population-manifest", type=Path, required=True)
    ap.add_argument("--results-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--strict-available",
        action="store_true",
        help="fail unless every sourceAvailable path has a valid per-zone result",
    )
    args = ap.parse_args()

    manifest = load(args.population_manifest)
    if manifest.get("format") != INPUT_FORMAT:
        raise ValueError(f"unexpected population manifest format {manifest.get('format')!r}")
    zones = manifest.get("zones")
    if not isinstance(zones, list) or len(zones) != 297:
        raise ValueError(f"expected exactly 297 declared catalog paths, got {len(zones) if isinstance(zones, list) else None}")

    rows = []
    missing_results: list[str] = []
    invalid_results: list[dict[str, str]] = []
    unavailable: list[str] = []
    audited = 0
    total_xassets = total_xanim = total_xmodel = 0
    xanim_closed = xmodel_source_closed = xmodel_identity_closed = 0

    declared_result_names = set()
    for spec in zones:
        path = spec.get("path")
        if not isinstance(path, str) or not path.startswith("zone/") or not path.endswith(".ff"):
            raise ValueError(f"invalid declared FastFile path {path!r}")
        rname = result_name(path)
        if rname in declared_result_names:
            raise ValueError(f"result-name collision for {path}")
        declared_result_names.add(rname)
        result_path = args.results_root / rname
        source_available = spec.get("sourceAvailable") is True
        row = {
            "path": path,
            "zone": spec.get("zone"),
            "sourceAvailable": source_available,
            "sourceState": spec.get("sourceState"),
            "overlappingDepotOwnership": spec.get("overlappingDepotOwnership") is True,
            "depotOwners": spec.get("depotOwners"),
            "resultPath": str(result_path),
        }
        if not source_available:
            unavailable.append(path)
            row["auditState"] = "source-unavailable-blocker"
            row["resultPresent"] = result_path.is_file()
            if result_path.is_file():
                invalid_results.append(
                    {
                        "path": path,
                        "error": "per-zone result exists for path declared sourceAvailable=false; retained source state must be reconciled before use",
                    }
                )
            rows.append(row)
            continue

        if not result_path.is_file():
            missing_results.append(path)
            row["auditState"] = "missing-result"
            row["resultPresent"] = False
            rows.append(row)
            continue

        try:
            result = load(result_path)
            if result.get("format") != ZONE_FORMAT:
                raise ValueError(f"unexpected per-zone format {result.get('format')!r}")
            # Workers should use the full catalog path as their zone identity.
            if result.get("zone") != path:
                raise ValueError(f"per-zone identity {result.get('zone')!r} != catalog path {path!r}")
            gates = result.get("gates") or {}
            raw = result.get("rawXAssetInventory") or {}
            audited += 1
            total_xassets += int(raw.get("assetCount", 0))
            total_xanim += int(raw.get("xanimparts", 0))
            total_xmodel += int(raw.get("xmodels", 0))
            if gates.get("xanimPopulationClosed") is True:
                xanim_closed += 1
            if gates.get("xmodelSourceConsumingRecordsClosed") is True:
                xmodel_source_closed += 1
            if gates.get("xmodelPopulationIdentityClosed") is True:
                xmodel_identity_closed += 1
            row.update(
                auditState="audited",
                resultPresent=True,
                expandedSha256=result.get("expandedSha256"),
                expandedBytes=result.get("expandedBytes"),
                xassets=int(raw.get("assetCount", 0)),
                xanims=int(raw.get("xanimparts", 0)),
                xmodels=int(raw.get("xmodels", 0)),
                gates=gates,
            )
        except Exception as exc:
            invalid_results.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})
            row["auditState"] = "invalid-result"
            row["resultPresent"] = True
            row["error"] = invalid_results[-1]["error"]
        rows.append(row)

    # Extra shard files are blockers because they can indicate a stale or mixed
    # corpus result directory.
    actual_result_names = {p.name for p in args.results_root.glob("*.population.json")}
    undeclared_results = sorted(actual_result_names - declared_result_names)

    available = sum(z.get("sourceAvailable") is True for z in zones)
    expected_unavailable = len(zones) - available
    if available != int((manifest.get("sourceAvailability") or {}).get("present", -1)):
        raise ValueError("manifest sourceAvailable count disagrees with sourceAvailability.present")
    if expected_unavailable != int((manifest.get("sourceAvailability") or {}).get("unavailable", -1)):
        raise ValueError("manifest unavailable count disagrees with sourceAvailability.unavailable")

    all_available_audited = (
        audited == available
        and not missing_results
        and not invalid_results
        and not undeclared_results
    )
    all_available_xanim_closed = all_available_audited and xanim_closed == available
    all_available_xmodel_source_closed = (
        all_available_audited and xmodel_source_closed == available
    )
    all_available_xmodel_identity_closed = (
        all_available_audited and xmodel_identity_closed == available
    )

    corpus_claim_complete = (manifest.get("corpusClaim") or {}).get("complete") is True
    population_input_identity_complete = (manifest.get("gates") or {}).get(
        "populationInputIdentityComplete"
    ) is True

    out = {
        "format": FORMAT,
        "scope": "Steam English PC retail FastFile catalog only",
        "populationManifest": {
            "path": str(args.population_manifest),
            "format": manifest.get("format"),
            "catalog": manifest.get("catalog"),
            "sourceAvailability": manifest.get("sourceAvailability"),
            "corpusClaim": manifest.get("corpusClaim"),
            "gates": manifest.get("gates"),
        },
        "inventory": {
            "declaredPaths": len(zones),
            "sourceAvailablePaths": available,
            "sourceUnavailablePaths": len(unavailable),
            "auditedAvailablePaths": audited,
            "missingAvailableResults": missing_results,
            "invalidResults": invalid_results,
            "undeclaredResultFiles": undeclared_results,
            "unavailablePaths": unavailable,
        },
        "totalsForAuditedAvailablePaths": {
            "xassets": total_xassets,
            "xanimparts": total_xanim,
            "xmodels": total_xmodel,
        },
        "closureCountsForAvailablePaths": {
            "xanimPopulationClosed": xanim_closed,
            "xmodelSourceConsumingRecordsClosed": xmodel_source_closed,
            "xmodelPopulationIdentityClosed": xmodel_identity_closed,
        },
        "zones": rows,
        "gates": {
            "allSourceAvailablePathsAudited": all_available_audited,
            "allSourceAvailableXAnimPopulationsClosed": all_available_xanim_closed,
            "allSourceAvailableXModelSourceRecordsClosed": all_available_xmodel_source_closed,
            "allSourceAvailableXModelIdentitiesClosed": all_available_xmodel_identity_closed,
            "populationInputIdentityComplete": population_input_identity_complete,
            "englishRetailXAnimPopulationComplete": (
                corpus_claim_complete
                and population_input_identity_complete
                and all_available_xanim_closed
            ),
            "englishRetailXModelPopulationComplete": (
                corpus_claim_complete
                and population_input_identity_complete
                and all_available_xmodel_identity_closed
            ),
            "wholeRetailAllLanguagesPopulationComplete": False,
            "characterClassificationComplete": False,
            "semanticCoverageComplete": False,
        },
        "proofBoundary": [
            "All 297 catalog paths remain represented in this aggregate, including every unavailable path.",
            "A sourceAvailable path without a valid per-zone result is a blocker; no available path may be silently dropped.",
            "The 82 retained unavailable paths and six unresolved multi-depot byte-identity cases keep populationInputIdentityComplete false until separately closed.",
            "Closing every currently available shard does not by itself close the English retail population while corpus/input identity remains incomplete.",
            "This is English PC retail FastFile scope only, not all-language whole-retail scope.",
            "XMODEL population identity closure is distinct from later character classification and semantic/material/shader relationship closure."
        ]
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "declared": len(zones),
                "available": available,
                "unavailable": len(unavailable),
                "audited": audited,
                "totals": out["totalsForAuditedAvailablePaths"],
                "closureCounts": out["closureCountsForAvailablePaths"],
                "gates": out["gates"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.strict_available and not all_available_audited:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
