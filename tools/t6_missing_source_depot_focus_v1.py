#!/usr/bin/env python3
"""Reduce the retained missing English-retail FastFile set to owning Steam depots."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

FORMAT = "t6-missing-source-depot-focus-v1"


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def depot_rows(base: dict[str, Any], full: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, src in (("depots", base), ("additionalDepots", full)):
        value = src.get(key)
        if not isinstance(value, list):
            raise ValueError(f"missing/invalid {key}")
        rows.extend(value)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-catalog", type=Path, required=True)
    ap.add_argument("--full-catalog", type=Path, required=True)
    ap.add_argument("--availability", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--require-single-owner-depot", action="store_true")
    a = ap.parse_args()

    base = load(a.base_catalog)
    full = load(a.full_catalog)
    availability = load(a.availability)
    if base.get("format") != "t6-steam-english-base-zone-catalog-v1":
        raise ValueError("unexpected base catalog format")
    if full.get("format") != "t6-steam-english-full-zone-catalog-v2":
        raise ValueError("unexpected full catalog format")
    if availability.get("format") != "t6-steam-full-zone-source-availability-checkpoint-v1":
        raise ValueError("unexpected availability format")

    depots = depot_rows(base, full)
    path_owners: dict[str, list[dict[str, Any]]] = defaultdict(list)
    depot_by_id: dict[int, dict[str, Any]] = {}
    for depot in depots:
        did = int(depot["depotId"])
        depot_by_id[did] = depot
        ff = depot.get("ff")
        if not isinstance(ff, list) or len(ff) != int(depot.get("expectedFfCount", -1)):
            raise ValueError(f"depot {did}: invalid FastFile inventory")
        for path in ff:
            path_owners[path].append(depot)

    union = availability.get("sourceContainerUnion") or {}
    missing = sorted(union.get("missing") or [])
    if len(missing) != int(union.get("missingCount", -1)):
        raise ValueError("availability missingCount mismatch")
    unknown = [p for p in missing if p not in path_owners]
    if unknown:
        raise ValueError(f"missing paths absent from catalog: {unknown}")

    missing_set = set(missing)
    owner_counts: dict[int, int] = defaultdict(int)
    missing_rows = []
    for path in missing:
        owners = path_owners[path]
        ids = sorted(int(d["depotId"]) for d in owners)
        for did in ids:
            owner_counts[did] += 1
        missing_rows.append({"path": path, "depotOwners": ids})

    owner_depots = []
    for did in sorted(owner_counts):
        depot = depot_by_id[did]
        depot_ff = list(depot["ff"])
        depot_missing = sorted(p for p in depot_ff if p in missing_set)
        depot_present = sorted(p for p in depot_ff if p not in missing_set)
        owner_depots.append(
            {
                "depotId": did,
                "manifestId": str(depot["manifestId"]),
                "label": depot.get("label"),
                "catalogFastFiles": len(depot_ff),
                "missingFastFiles": len(depot_missing),
                "retainedPresentFastFiles": len(depot_present),
                "missingPaths": depot_missing,
                "retainedPresentPaths": depot_present,
            }
        )

    single = len(owner_depots) == 1
    out = {
        "format": FORMAT,
        "missingFastFiles": len(missing),
        "missingOwnerDepotCount": len(owner_depots),
        "ownerDepots": owner_depots,
        "missingRows": missing_rows,
        "gates": {
            "allMissingPathsHaveCatalogOwners": not unknown,
            "missingSetOwnedBySingleDepot": single,
            "missingCountMatchesAvailabilityCheckpoint": len(missing) == int(union.get("missingCount", -1)),
        },
        "proofBoundary": [
            "Depot ownership is derived only from the retained Steam English FastFile catalogs and the retained 82-path source-availability missing set.",
            "This proves which catalog depot inventories contain the missing paths; it does not prove that source bytes have been recovered or that SteamDB manifest metadata is a raw retail-file hash oracle.",
            "Any retained-present paths in the owning depot are source-availability controls only until exact depot byte identity is independently closed.",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"missingFastFiles": len(missing), "missingOwnerDepotCount": len(owner_depots), "ownerDepots": owner_depots}, indent=2, sort_keys=True))
    if a.require_single_owner_depot and not all(out["gates"].values()):
        raise SystemExit("missing-source depot focus did not close to a single owning depot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
