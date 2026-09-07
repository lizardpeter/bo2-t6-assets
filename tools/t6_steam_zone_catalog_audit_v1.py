#!/usr/bin/env python3
"""Fail-closed audit for the retained Steam-manifest T6 FastFile catalog."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

FMT = "t6-steam-english-base-zone-catalog-v1"
OUTFMT = "t6-steam-zone-catalog-audit-v1"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def seed_path(zone: str) -> str:
    folder = "english" if zone.startswith("en_") else "all"
    return f"zone/{folder}/{zone}.ff"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--seed", type=Path)
    ap.add_argument("--probe-tsv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    c = load_json(a.catalog)
    errors: list[str] = []
    if c.get("format") != FMT:
        errors.append(f"unexpected format {c.get('format')!r}")
    depots = c.get("depots")
    if not isinstance(depots, list) or not depots:
        errors.append("depots missing/empty")
        depots = []

    rows = []
    for d in depots:
        ff = d.get("ff") if isinstance(d.get("ff"), list) else []
        if int(d.get("expectedFfCount", -1)) != len(ff):
            errors.append(f"depot {d.get('depotId')} expectedFfCount mismatch")
        folder = d.get("zoneFolder")
        if folder not in ("all", "english"):
            errors.append(f"depot {d.get('depotId')} invalid zoneFolder")
        for p in ff:
            if not isinstance(p, str) or not p.endswith(".ff"):
                errors.append(f"invalid FF path in depot {d.get('depotId')}: {p!r}")
                continue
            if folder and not p.startswith(f"zone/{folder}/"):
                errors.append(f"folder mismatch for {p}")
            rows.append({"path": p, "depotId": d.get("depotId"), "manifestId": d.get("manifestId"), "label": d.get("label")})

    counts = Counter(r["path"] for r in rows)
    dupes = sorted(p for p, n in counts.items() if n > 1)
    if dupes:
        errors.append(f"duplicate FF paths: {dupes}")
    expected_total = int(c.get("totals", {}).get("ff", -1))
    if expected_total != len(rows):
        errors.append(f"catalog total FF mismatch: {expected_total} != {len(rows)}")
    expected_depots = int(c.get("totals", {}).get("depots", -1))
    if expected_depots != len(depots):
        errors.append(f"catalog depot total mismatch: {expected_depots} != {len(depots)}")

    catalog_paths = set(counts)
    seed_info = None
    if a.seed:
        s = load_json(a.seed)
        seed_zones = [z["zone"] for z in s.get("zones", [])]
        seed_paths = {seed_path(z) for z in seed_zones}
        seed_info = {
            "zones": len(seed_zones),
            "matchedPaths": sorted(seed_paths & catalog_paths),
            "outsideCatalogPaths": sorted(seed_paths - catalog_paths),
            "catalogPathsNotInSeed": len(catalog_paths - seed_paths),
        }

    probe = None
    if a.probe_tsv:
        status = {}
        malformed = []
        for line in a.probe_tsv.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                malformed.append(line)
                continue
            status[parts[0]] = parts[1]
        missing_probe_rows = sorted(catalog_paths - set(status))
        unknown_probe_rows = sorted(set(status) - catalog_paths)
        unavailable = sorted(p for p in catalog_paths if status.get(p) != "present")
        probe = {
            "rows": len(status),
            "present": sum(status.get(p) == "present" for p in catalog_paths),
            "unavailable": unavailable,
            "missingProbeRows": missing_probe_rows,
            "unknownProbeRows": unknown_probe_rows,
            "malformedRows": malformed,
        }

    structurally_valid = not errors
    claimed_scope = bool(c.get("scope", {}).get("completeForClaimedScope")) and structurally_valid
    r2_complete = bool(probe is not None and not probe["unavailable"] and not probe["missingProbeRows"] and not probe["unknownProbeRows"] and not probe["malformedRows"])
    whole_retail = bool(c.get("scope", {}).get("wholeRetailComplete")) and claimed_scope and r2_complete

    out = {
        "format": OUTFMT,
        "catalog": str(a.catalog),
        "catalogTotals": {"depots": len(depots), "ff": len(rows)},
        "errors": errors,
        "seedCoverage": seed_info,
        "r2Probe": probe,
        "gates": {
            "catalogStructurallyValid": structurally_valid,
            "claimedScopeCatalogComplete": claimed_scope,
            "r2MirrorCompleteForCatalog": r2_complete,
            "wholeRetailCatalogComplete": whole_retail,
        },
        "proofBoundary": [
            "Steam/SteamDB path enumeration does not prove retail file bytes; R2 availability is a separate mirror check.",
            "The catalog explicitly excludes the four major map packs and non-English depots, so wholeRetailCatalogComplete must remain false in v1.",
            "No XAnim/XModel population claim is promoted by this catalog audit alone."
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"catalogFF": len(rows), "catalogDepots": len(depots), "errors": len(errors), "r2Complete": r2_complete, "wholeRetail": whole_retail}, indent=2))
    if errors:
        raise SystemExit("catalog validation failed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
