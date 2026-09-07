#!/usr/bin/env python3
"""Join the proven 30-body MP faction corpus to the global native XModel name catalog.

This is an exact provenance join only. It does not discover characters by name
patterns. Every body must already be independently proven by the retained
mp_player_body_faction_corpus_checkpoint_v1.json and must occur under its exact
native XModel name in the exact expected faction FastFile.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BODY_FORMAT = "t6-mp-player-body-faction-corpus-checkpoint-v1"
CATALOG_FORMAT = "t6-native-xmodel-name-catalog-v1"
FORMAT = "t6-mp-player-body-native-name-join-v1"


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected object")
    return obj


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-corpus", type=Path, required=True)
    ap.add_argument("--name-catalog", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--require-closed", action="store_true")
    a = ap.parse_args()

    bodies = load(a.body_corpus)
    catalog = load(a.name_catalog)
    if bodies.get("format") != BODY_FORMAT:
        raise ValueError(f"unexpected body corpus format {bodies.get('format')!r}")
    if catalog.get("format") != CATALOG_FORMAT:
        raise ValueError(f"unexpected name catalog format {catalog.get('format')!r}")

    columns = bodies.get("columns")
    rows = bodies.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise ValueError("body corpus columns/rows missing")
    col = {name: i for i, name in enumerate(columns)}
    required = ["name", "zone", "fixedStart", "fixedRecordSha256", "bones", "roots", "surfaces", "vertices", "triangles", "corpusSkeletonSha256"]
    missing_cols = [x for x in required if x not in col]
    if missing_cols:
        raise ValueError(f"body corpus missing columns {missing_cols}")

    name_rows = catalog.get("names")
    if not isinstance(name_rows, list):
        raise ValueError("name catalog names missing")
    by_name: dict[str, dict[str, Any]] = {}
    for n in name_rows:
        if not isinstance(n, dict) or not isinstance(n.get("nativeName"), str):
            raise ValueError("invalid name catalog row")
        name = n["nativeName"]
        if name in by_name:
            raise ValueError(f"duplicate nativeName row {name!r}")
        by_name[name] = n

    joined = []
    failures = []
    seen_body_names = set()
    for r in rows:
        if not isinstance(r, list) or len(r) != len(columns):
            raise ValueError("invalid body corpus row")
        name = r[col["name"]]
        zone = r[col["zone"]]
        if name in seen_body_names:
            raise ValueError(f"duplicate proven body name {name!r}")
        seen_body_names.add(name)
        expected_path = f"zone/all/{zone}.ff"
        n = by_name.get(name)
        if n is None:
            failures.append({"name": name, "expectedPath": expected_path, "reason": "exact native name absent from global catalog"})
            continue
        occ = n.get("occurrenceRows")
        if not isinstance(occ, list):
            failures.append({"name": name, "expectedPath": expected_path, "reason": "catalog occurrenceRows missing"})
            continue
        expected_occ = [x for x in occ if isinstance(x, dict) and x.get("zone") == expected_path]
        if not expected_occ:
            failures.append({"name": name, "expectedPath": expected_path, "reason": "name exists globally but not in exact proven faction FastFile"})
            continue
        joined.append({
            "name": name,
            "provenFactionZone": zone,
            "expectedFastFilePath": expected_path,
            "globalOccurrences": int(n.get("occurrences", len(occ))),
            "globalZoneCount": int(n.get("zoneCount", len({x.get('zone') for x in occ if isinstance(x, dict)}))),
            "globalZones": n.get("zones"),
            "expectedZoneOccurrences": expected_occ,
            "bodyProof": {
                "fixedStart": r[col["fixedStart"]],
                "fixedRecordSha256": r[col["fixedRecordSha256"]],
                "bones": r[col["bones"]],
                "roots": r[col["roots"]],
                "surfaces": r[col["surfaces"]],
                "vertices": r[col["vertices"]],
                "triangles": r[col["triangles"]],
                "corpusSkeletonSha256": r[col["corpusSkeletonSha256"]],
            },
        })

    summary = bodies.get("summary") or {}
    expected_bodies = int(summary.get("bodies", -1))
    gates = {
        "retainedBodyCorpusHasExpected30Bodies": expected_bodies == 30 and len(rows) == 30,
        "allProvenBodyNamesUnique": len(seen_body_names) == len(rows),
        "allProvenBodiesPresentInGlobalNativeNameCatalog": len(joined) == len(rows),
        "allProvenBodiesPresentInExactExpectedFactionFastFile": not failures and len(joined) == len(rows),
        "allProvenBodiesRetain102BoneOneRootContract": all(j["bodyProof"]["bones"] == 102 and j["bodyProof"]["roots"] == 1 for j in joined),
    }

    out = {
        "format": FORMAT,
        "scope": "Exact join of the independently proven 30-body base MP faction corpus to the source-available native XModel name catalog",
        "summary": {
            "provenBodyRows": len(rows),
            "joinedBodies": len(joined),
            "joinFailures": len(failures),
            "distinctBodyNames": len(seen_body_names),
            "globalOccurrenceSumForTheseNames": sum(j["globalOccurrences"] for j in joined),
            "bodiesRepeatedOutsideTheirProvenFactionZone": sum(j["globalZoneCount"] > 1 for j in joined),
        },
        "gates": gates,
        "failures": failures,
        "bodies": sorted(joined, key=lambda x: (x["provenFactionZone"], x["name"])),
        "proofBoundary": [
            "No model is classified as a player body by name syntax or fuzzy matching. Membership comes only from the previously retained direct-retail 30-body faction corpus proof.",
            "The global catalog join is exact case-sensitive native XModel name equality plus exact expected faction FastFile path equality.",
            "Repeated occurrences of a body name in other FastFiles are retained as provenance only and do not establish payload byte identity across zones.",
            "This join proves identity/provenance for the 30 already-closed base MP player bodies; it does not claim every character model in the game is one of these 30 bodies.",
            "Material, texture, TechniqueSet, shader, animation-selection, and portable-export fidelity remain separate gates for each body."
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"summary": out["summary"], "gates": gates}, indent=2, sort_keys=True))
    if a.require_closed and not all(gates.values()):
        raise SystemExit("MP player-body native-name join did not fully close")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
