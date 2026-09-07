#!/usr/bin/env python3
"""Build a fail-closed English-retail T6 population-input manifest.

Inputs are repository-retained catalog/source-availability proofs. The output is
one deduplicated 297-path FastFile declaration suitable for population audits.
It preserves every depot owner for overlapping paths, marks the 82 currently
unavailable paths explicitly, and never upgrades source availability into byte
identity or whole-retail completeness.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

FORMAT = "t6-steam-english-population-input-manifest-v1"


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def depot_rows(base: dict[str, Any], full: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, src in (("depots", base), ("additionalDepots", full)):
        ds = src.get(key)
        if not isinstance(ds, list):
            raise ValueError(f"missing/invalid {key}")
        for d in ds:
            if not isinstance(d, dict):
                raise ValueError(f"{key}: depot row must be an object")
            ff = d.get("ff")
            if not isinstance(ff, list):
                raise ValueError(f"depot {d.get('depotId')}: ff must be a list")
            if int(d.get("expectedFfCount", -1)) != len(ff):
                raise ValueError(
                    f"depot {d.get('depotId')}: expectedFfCount={d.get('expectedFfCount')} != {len(ff)}"
                )
            rows.append(d)
    return rows


def zone_name(path: str) -> str:
    if not path.startswith("zone/") or not path.endswith(".ff"):
        raise ValueError(f"invalid FastFile path: {path!r}")
    return Path(path).stem


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-catalog", type=Path, required=True)
    ap.add_argument("--full-catalog", type=Path, required=True)
    ap.add_argument("--availability", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    base = load(a.base_catalog)
    full = load(a.full_catalog)
    avail = load(a.availability)

    if base.get("format") != "t6-steam-english-base-zone-catalog-v1":
        raise ValueError("unexpected base catalog format")
    if full.get("format") != "t6-steam-english-full-zone-catalog-v2":
        raise ValueError("unexpected full catalog format")
    if avail.get("format") != "t6-steam-full-zone-source-availability-checkpoint-v1":
        raise ValueError("unexpected availability checkpoint format")

    depots = depot_rows(base, full)
    owners: dict[str, list[dict[str, Any]]] = defaultdict(list)
    entry_count = 0
    for d in depots:
        for path in d["ff"]:
            if not isinstance(path, str):
                raise ValueError(f"depot {d.get('depotId')}: non-string FastFile path")
            zone_name(path)
            entry_count += 1
            owners[path].append(
                {
                    "depotId": int(d["depotId"]),
                    "manifestId": str(d["manifestId"]),
                    "label": d.get("label"),
                    "sourceUrl": d.get("sourceUrl"),
                }
            )

    paths = sorted(owners)
    totals = full.get("totals") or {}
    if entry_count != int(totals.get("depotFfEntries", -1)):
        raise ValueError(f"depot entry count {entry_count} != retained total {totals.get('depotFfEntries')}")
    if len(paths) != int(totals.get("uniqueFfPaths", -1)):
        raise ValueError(f"unique path count {len(paths)} != retained total {totals.get('uniqueFfPaths')}")

    duplicates = {p: sorted(x["depotId"] for x in os) for p, os in owners.items() if len(os) > 1}
    expected_dups = {
        p: sorted(int(x) for x in ids)
        for p, ids in (full.get("expectedOverlappingDepotPaths") or {}).items()
    }
    if duplicates != expected_dups:
        raise ValueError(f"overlap ownership mismatch: actual={duplicates!r} expected={expected_dups!r}")
    if len(duplicates) != int(totals.get("overlappingUniquePaths", -1)):
        raise ValueError("overlapping path count does not match retained total")

    cat = avail.get("catalog") or {}
    if int(cat.get("uniqueFfPaths", -1)) != len(paths):
        raise ValueError("availability checkpoint catalog size mismatch")
    if cat.get("englishRetailFfCatalogComplete") is not True:
        raise ValueError("availability checkpoint does not retain English catalog completeness")

    union = avail.get("sourceContainerUnion") or {}
    missing = set(union.get("missing") or [])
    unknown_missing = sorted(missing - set(paths))
    if unknown_missing:
        raise ValueError(f"availability contains paths outside catalog: {unknown_missing}")
    if int(union.get("missingCount", -1)) != len(missing):
        raise ValueError("availability missingCount mismatch")
    present = set(paths) - missing
    if int(union.get("present", -1)) != len(present):
        raise ValueError("availability present count mismatch")

    rows = []
    for path in paths:
        folder = path.split("/")[1]
        name = zone_name(path)
        is_present = path in present
        row = {
            "zone": name,
            "path": path,
            "zoneFolder": folder,
            "depotOwners": owners[path],
            "overlappingDepotOwnership": len(owners[path]) > 1,
            "sourceAvailable": is_present,
            "sourceState": "flat-r2-present" if is_present else "unavailable-in-retained-source-union",
            "flatR2Url": f"https://r2.houseofkublai.com/bo2/{path}" if is_present else None,
            "byteIdentityComplete": False if len(owners[path]) > 1 else None,
        }
        rows.append(row)

    result = {
        "format": FORMAT,
        "scope": "English PC retail FastFile population inputs only",
        "catalog": {
            "completeForEnglishRetailFfScope": True,
            "wholeRetailAllLanguagesComplete": False,
            "depotFfEntries": entry_count,
            "uniqueFfPaths": len(paths),
            "overlappingUniquePaths": len(duplicates),
        },
        "sourceAvailability": {
            "present": len(present),
            "unavailable": len(missing),
            "completeForCatalog": len(missing) == 0,
        },
        "corpusClaim": {
            "complete": False,
            "reason": (
                "The English FastFile path catalog is complete for its declared scope, but population input identity is not complete: "
                f"{len(missing)} catalog paths are unavailable in the retained source union and {len(duplicates)} multi-depot paths still require exact byte-identity closure."
            ),
        },
        "zones": rows,
        "gates": {
            "catalogStructurallyClosed": True,
            "englishRetailFfCatalogComplete": True,
            "sourceContainerUnionComplete": len(missing) == 0,
            "overlapByteIdentityComplete": False if duplicates else True,
            "populationInputIdentityComplete": False,
            "wholeRetailAllLanguagesCatalogComplete": False,
        },
        "proofBoundary": [
            "This manifest is a deterministic join of the retained Steam English FastFile catalog and retained source-availability checkpoint.",
            "sourceAvailable means the exact catalog path is retrievable from the retained flat R2 mirror state; it does not by itself establish historical Steam depot byte identity.",
            "All 82 unavailable paths remain declared and blocking. No population audit may silently drop them.",
            "All six multi-depot paths retain every owner. Their byte identity remains unclosed until exact hashes or independently matching retail bytes prove it.",
            "This is English retail FastFile scope, not all-language whole-retail scope.",
        ],
    }

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "format": FORMAT,
                "depotFfEntries": entry_count,
                "uniqueFfPaths": len(paths),
                "present": len(present),
                "unavailable": len(missing),
                "overlappingUniquePaths": len(duplicates),
                "populationInputIdentityComplete": result["gates"]["populationInputIdentityComplete"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
