#!/usr/bin/env python3
"""Project native OAT duplicate conflicts through exact T6 PC dedicated-server semantics.

This is deliberately NOT retail-client authority. It consumes a fail-closed
parent-dependency conflict census and the exact SHA-pinned PC dedicated-server
override proof, then records what that server build would select for conflicts
whose physical roots have source-closed server flag/priority identities.

No projection may be fed back into the authoritative retail-client census.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FORMAT = "t6-oat-conflict-pc-server-projection-v1"
CONFLICT_FORMAT = "t6-oat-parent-dependency-conflict-census-v1"
SERVER_PROOF_FORMAT = "t6-pc-server-xasset-override-proof-v1"


class ProjectionError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProjectionError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ProjectionError(f"expected object in {path}")
    return obj


def build(conflicts: dict, server: dict) -> dict:
    if conflicts.get("format") != CONFLICT_FORMAT:
        raise ProjectionError(f"unexpected conflict format {conflicts.get('format')!r}")
    if conflicts.get("authoritativeWinnerSelection") is not False:
        raise ProjectionError("source conflict census must not have selected winners")
    if server.get("format") != SERVER_PROOF_FORMAT:
        raise ProjectionError(f"unexpected server proof format {server.get('format')!r}")
    authority = server.get("authority", {})
    if authority.get("pcDedicatedServerBuild") is not True:
        raise ProjectionError("server proof is not authoritative for its PC dedicated-server build")
    if authority.get("retailT6mpClient") is not False:
        raise ProjectionError("server proof must explicitly block retail-client promotion")

    flags = server.get("mpFlags", {})
    required = {
        "/tmp/map_out": ("ordinaryBuiltInMpMap", "mp_nuketown_2020"),
        "/tmp/common_out": ("common_mp", "common_mp"),
        "/tmp/patch_out": ("patch_mp", "patch_mp"),
    }
    roots = {}
    for root, (key, label) in required.items():
        row = flags.get(key)
        if not isinstance(row, dict) or not isinstance(row.get("priority"), int):
            raise ProjectionError(f"server proof missing priority for {key}")
        roots[root] = {
            "serverZoneClass": key,
            "serverLabel": label,
            "allocFlagsHex": row.get("allocFlagsHex"),
            "priority": row["priority"],
        }

    rows = []
    predicted = 0
    owner_gaps = 0
    unmapped = 0
    ties = 0
    predicted_by_root: dict[str, int] = {}
    material_users: set[str] = set()

    for conflict in conflicts.get("conflicts", []):
        if not isinstance(conflict, dict):
            raise ProjectionError("non-object conflict row")
        kind = conflict.get("kind")
        base = {
            "conflictKey": conflict.get("conflictKey"),
            "kind": kind,
            "techniqueSet": conflict.get("techniqueSet"),
            "technique": conflict.get("technique"),
            "materials": conflict.get("materials", []),
            "authoritativeForRetailClient": False,
        }
        material_users.update(m for m in base["materials"] if isinstance(m, str))
        if kind == "missing-parent-techniqueset-owner":
            owner_gaps += 1
            rows.append({
                **base,
                "serverPredictedPrimaryRoot": None,
                "projectionState": "owner-universe-gap-not-a-precedence-conflict",
                "reason": "no physical parent TechniqueSet owner exists in the supplied roots; precedence cannot select a missing dependency",
            })
            continue
        if kind != "divergent-parent-owned-child":
            rows.append({
                **base,
                "serverPredictedPrimaryRoot": None,
                "projectionState": "unsupported-conflict-kind",
            })
            unmapped += 1
            continue

        owners = conflict.get("parentOwners")
        if not isinstance(owners, list) or len(owners) < 2:
            raise ProjectionError(f"divergent conflict {base['conflictKey']} lacks parentOwners")
        missing = [r for r in owners if r not in roots]
        candidates = [{"root": r, **roots[r]} for r in owners if r in roots]
        if missing:
            unmapped += 1
            rows.append({
                **base,
                "parentOwners": owners,
                "serverCandidates": candidates,
                "unmappedParentOwners": missing,
                "serverPredictedPrimaryRoot": None,
                "projectionState": "unmapped-server-zone-class",
            })
            continue

        max_priority = max(r["priority"] for r in candidates)
        maxima = [r for r in candidates if r["priority"] == max_priority]
        if len(maxima) != 1:
            ties += 1
            rows.append({
                **base,
                "parentOwners": owners,
                "serverCandidates": candidates,
                "serverPredictedPrimaryRoot": None,
                "projectionState": "server-priority-tie-load-order-required",
            })
            continue

        winner = maxima[0]["root"]
        predicted += 1
        predicted_by_root[winner] = predicted_by_root.get(winner, 0) + 1
        rows.append({
            **base,
            "parentOwners": owners,
            "serverCandidates": candidates,
            "serverPredictedPrimaryRoot": winner,
            "projectionState": "unique-exact-pc-server-priority-maximum",
            "authoritativeForPcDedicatedServerBuild": True,
        })

    expected = conflicts.get("summary", {}).get("unresolvedConflictCount")
    if isinstance(expected, int) and expected != len(rows):
        raise ProjectionError(f"projected {len(rows)} conflicts but source summary says {expected}")

    return {
        "format": FORMAT,
        "authorityState": "exact_pc_dedicated_server_projection_only",
        "authoritativeForPcDedicatedServerBuild": True,
        "authoritativeForRetailClient": False,
        "serverExecutable": server.get("pcDedicatedServer"),
        "rootSemantics": roots,
        "summary": {
            "sourceConflictCount": len(rows),
            "serverUniquePredictionCount": predicted,
            "ownerUniverseGapCount": owner_gaps,
            "unmappedServerZoneClassCount": unmapped,
            "serverPriorityTieCount": ties,
            "authoritativeRetailClientWinnerCount": 0,
            "distinctAffectedMaterialCount": len(material_users),
            "serverPredictedPrimaryRootCounts": predicted_by_root,
        },
        "projections": rows,
        "proofBoundary": (
            "The conflict identities and physical parent roots come from the fail-closed pinned-OAT census. "
            "The flag propagation, common_mp/map/patch_mp flags, priority values, >= comparison, and primary payload replacement are exact only for the SHA-pinned CoDMPServer_PC.exe + linker MAP proof. "
            "A unique result is authoritative for that exact PC dedicated-server build only. It is a falsifiable projection for the retail t6mp.exe client, not a retail-client winner. "
            "Missing-parent TechniqueSet conflicts remain owner-universe gaps and are never resolved by precedence."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--conflicts", type=Path, required=True)
    p.add_argument("--server-proof", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(_load(a.conflicts), _load(a.server_proof))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
