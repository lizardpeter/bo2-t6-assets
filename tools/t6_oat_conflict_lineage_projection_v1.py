#!/usr/bin/env python3
"""Project native OAT dependency conflicts through T6 zone-priority lineage.

This tool exists to quantify the leverage of the still-unproven retail duplicate
XAsset priority rule. It consumes the exact conflict census, maps physical OAT
roots to explicit zone flags supplied by the caller, and reports what the
retained lineage priority table would predict.

It can never authorize a winner. Unique maximum priority is reported only as a
lineage prediction; ties, unmapped roots, and missing-parent owner-universe gaps
remain unresolved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import t6_zone_override_lineage_diagnostic_v1 as lineage

FORMAT = "t6-oat-conflict-lineage-projection-v1"


class ProjectionError(RuntimeError):
    pass


def parse_root_zone(value: str) -> tuple[str, int, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--root-zone must be ROOT=FLAG")
    root, raw = value.rsplit("=", 1)
    root = root.strip()
    raw = raw.strip()
    if not root or not raw:
        raise argparse.ArgumentTypeError("--root-zone must be ROOT=FLAG")
    try:
        flag = int(raw, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid zone flag {raw!r}") from exc
    if not 0 <= flag <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("zone flag must fit uint32")
    return str(Path(root).resolve()), flag, raw


def build(conflict_doc: dict, root_flags: dict[str, int]) -> dict:
    if conflict_doc.get("format") != "t6-oat-parent-dependency-conflict-census-v1":
        raise ProjectionError(f"unexpected conflict census format {conflict_doc.get('format')!r}")
    if conflict_doc.get("authoritativeWinnerSelection") is not False:
        raise ProjectionError("conflict census must explicitly be non-selecting")

    normalized_flags = {str(Path(root).resolve()): flag for root, flag in root_flags.items()}
    projections = []
    unique_predictions = 0
    unresolved_ties = 0
    unmapped = 0
    owner_universe_gaps = 0

    for conflict in conflict_doc.get("conflicts", []):
        raw_owners = conflict.get("parentOwners", [])
        if not isinstance(raw_owners, list):
            raise ProjectionError(f"conflict {conflict.get('conflictKey')} parentOwners must be a list")
        owners = [str(Path(root).resolve()) for root in raw_owners]
        owner_rows = []
        missing_roots = []
        predicted = None

        # A missing parent TechniqueSet is not a duplicate-owner precedence
        # question at all. Keep the owner-universe gap explicit and do not try
        # to manufacture an owner from zone-priority lineage.
        if not owners:
            state = "no-parent-owner-in-supplied-universe"
            owner_universe_gaps += 1
        else:
            for owner in owners:
                if owner not in normalized_flags:
                    missing_roots.append(owner)
                    continue
                flag = normalized_flags[owner]
                masked = flag & lineage.ZONE_FLAG_MASK
                if masked not in lineage.ZONE_PRIORITY:
                    raise ProjectionError(
                        f"root {owner}: unknown lineage zone flag 0x{masked:08x}"
                    )
                owner_rows.append({
                    "root": owner,
                    "zoneFlag": f"0x{flag:08x}",
                    "maskedFlag": f"0x{masked:08x}",
                    "lineagePriority": lineage.ZONE_PRIORITY[masked],
                })

            state = "unmapped-root"
            if missing_roots:
                unmapped += 1
            else:
                max_priority = max(row["lineagePriority"] for row in owner_rows)
                winners = [row["root"] for row in owner_rows if row["lineagePriority"] == max_priority]
                if len(winners) == 1:
                    predicted = winners[0]
                    state = "unique-lineage-priority-maximum"
                    unique_predictions += 1
                else:
                    state = "lineage-priority-tie-load-order-required"
                    unresolved_ties += 1

        projections.append({
            "conflictKey": conflict.get("conflictKey"),
            "kind": conflict.get("kind"),
            "techniqueSet": conflict.get("techniqueSet"),
            "technique": conflict.get("technique"),
            "declaredTechniqueTypes": conflict.get("declaredTechniqueTypes", []),
            "materials": conflict.get("materials", []),
            "owners": owner_rows,
            "unmappedParentOwners": missing_roots,
            "projectionState": state,
            "lineagePredictedPrimaryRoot": predicted,
            "authoritative": False,
        })

    return {
        "format": FORMAT,
        "authoritative": False,
        "authorityState": "lineage_projection_only",
        "sourceConflictFormat": conflict_doc.get("format"),
        "rootZoneFlags": {
            root: f"0x{flag:08x}" for root, flag in sorted(normalized_flags.items())
        },
        "summary": {
            "conflictCount": len(projections),
            "uniqueLineagePredictionCount": unique_predictions,
            "lineagePriorityTieCount": unresolved_ties,
            "unmappedConflictCount": unmapped,
            "ownerUniverseGapConflictCount": owner_universe_gaps,
            "authoritativeWinnerCount": 0,
        },
        "projections": projections,
        "proofBoundary": (
            "NON-AUTHORITATIVE projection. Parent-owned conflicts come from exact pinned-OAT provenance, but zone flags and DB_GetZonePriority/DB_OverrideAsset behavior used here remain lineage until independently closed against the exact retail executable/runtime. "
            "A unique lineage priority maximum is a falsifiable prediction only. Missing-parent TechniqueSet conflicts are owner-universe gaps, not precedence candidates, and remain unresolved. "
            "No projection may be fed into the authoritative native Material census as a winner."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--conflicts", type=Path, required=True)
    p.add_argument("--root-zone", action="append", default=[], metavar="ROOT=FLAG")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    root_flags: dict[str, int] = {}
    for value in a.root_zone:
        root, flag, _raw = parse_root_zone(value)
        if root in root_flags and root_flags[root] != flag:
            raise ProjectionError(f"conflicting flags supplied for root {root}")
        root_flags[root] = flag
    if not root_flags:
        raise ProjectionError("at least one --root-zone mapping is required")
    doc = json.loads(a.conflicts.read_text(encoding="utf-8"))
    result = build(doc, root_flags)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
