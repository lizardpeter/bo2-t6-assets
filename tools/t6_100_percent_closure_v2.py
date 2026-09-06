#!/usr/bin/env python3
"""Validate and summarize T6 100-percent closure manifests.

V1 hard-coded the v1 manifest format and therefore could not validate the
canonical v2 ledger.  This validator is deliberately version-aware while
keeping the release rule strict: 100% is boolean and every required gate must
be closed.  It also rejects stale hand-written summaries that contradict the
gates they summarize.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ALLOWED_FORMATS = {
    "t6-100-percent-closure-v1",
    "t6-100-percent-closure-v2",
    "t6-100-percent-closure-v3",
}
ALLOWED_STATUSES = {"closed", "implemented-awaiting-retail", "partial", "open"}


class ClosureError(RuntimeError):
    pass


def _require_text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClosureError(f"{label} must be non-empty text")
    return value


def validate(document: dict) -> dict:
    if not isinstance(document, dict):
        raise ClosureError("closure manifest must be an object")
    fmt = document.get("format")
    if fmt not in ALLOWED_FORMATS:
        raise ClosureError(f"unsupported closure format {fmt!r}")
    _require_text(document.get("goal"), "goal")

    gates = document.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ClosureError("closure manifest must contain non-empty gates[]")

    seen: set[str] = set()
    counts: Counter[str] = Counter()
    blockers: list[dict] = []
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            raise ClosureError(f"gate {index} is not an object")
        gate_id = _require_text(gate.get("id"), f"gate {index} id")
        if gate_id in seen:
            raise ClosureError(f"duplicate gate id {gate_id!r}")
        seen.add(gate_id)
        _require_text(gate.get("title"), f"gate {gate_id!r} title")
        status = gate.get("status")
        if status not in ALLOWED_STATUSES:
            raise ClosureError(f"gate {gate_id!r} has invalid status {status!r}")
        _require_text(gate.get("closureRequirement"), f"gate {gate_id!r} closureRequirement")
        evidence = gate.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) and x for x in evidence):
            raise ClosureError(f"gate {gate_id!r} must have a non-empty string evidence[]")
        counts[status] += 1
        if status != "closed":
            blockers.append({
                "id": gate_id,
                "title": gate["title"],
                "status": status,
                "closureRequirement": gate["closureRequirement"],
            })

    total = len(gates)
    closed = counts["closed"]
    summary = {
        "format": "t6-100-percent-closure-summary-v2",
        "sourceFormat": fmt,
        "gateCount": total,
        "closedGateCount": closed,
        "implementedAwaitingRetailGateCount": counts["implemented-awaiting-retail"],
        "partialGateCount": counts["partial"],
        "openGateCount": counts["open"],
        "release100Percent": closed == total,
        "blockerCount": len(blockers),
        "blockerIds": [row["id"] for row in blockers],
        "blockers": blockers,
        "policy": (
            "No intermediate numeric percent is manufactured from partial gates. "
            "release100Percent is true only when every required gate is closed."
        ),
    }

    declared = document.get("summary")
    if isinstance(declared, dict):
        aliases = {
            "gateCount": total,
            "closed": closed,
            "closedGateCount": closed,
            "implementedAwaitingRetail": counts["implemented-awaiting-retail"],
            "implementedAwaitingRetailGateCount": counts["implemented-awaiting-retail"],
            "partial": counts["partial"],
            "partialGateCount": counts["partial"],
            "open": counts["open"],
            "openGateCount": counts["open"],
            "release100Percent": closed == total,
        }
        for key, expected in aliases.items():
            if key in declared and declared[key] != expected:
                raise ClosureError(
                    f"declared summary {key}={declared[key]!r} contradicts computed {expected!r}"
                )

    release_rule = document.get("releaseRule")
    if release_rule is not None:
        _require_text(release_rule, "releaseRule")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    doc = json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    summary = validate(doc)
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if summary["release100Percent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
