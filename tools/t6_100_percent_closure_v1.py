#!/usr/bin/env python3
"""Validate and summarize the hard T6 100-percent closure manifest.

This deliberately does not turn subjective partial states into a fake rounded
percentage. The release condition is boolean: 100% means every named gate is
closed. Intermediate output reports exact gate counts and blocker IDs so future
retail runs can update the ledger mechanically.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ALLOWED = {"closed", "implemented-awaiting-retail", "partial", "open"}


class ClosureError(RuntimeError):
    pass


def validate(document: dict) -> dict:
    if document.get("format") != "t6-100-percent-closure-v1":
        raise ClosureError(f"unexpected closure format {document.get('format')!r}")
    gates = document.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ClosureError("closure manifest must contain non-empty gates[]")
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    blockers: list[dict] = []
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            raise ClosureError(f"gate {index} is not an object")
        gate_id = str(gate.get("id") or "")
        if not gate_id:
            raise ClosureError(f"gate {index} has empty id")
        if gate_id in seen:
            raise ClosureError(f"duplicate gate id {gate_id!r}")
        seen.add(gate_id)
        status = str(gate.get("status") or "")
        if status not in ALLOWED:
            raise ClosureError(f"gate {gate_id!r} has invalid status {status!r}")
        if not str(gate.get("closureRequirement") or ""):
            raise ClosureError(f"gate {gate_id!r} has no closureRequirement")
        evidence = gate.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ClosureError(f"gate {gate_id!r} has no evidence list")
        counts[status] += 1
        if status != "closed":
            blockers.append({
                "id": gate_id,
                "title": gate.get("title"),
                "status": status,
                "closureRequirement": gate["closureRequirement"],
            })

    total = len(gates)
    closed = counts["closed"]
    release100 = closed == total
    return {
        "format": "t6-100-percent-closure-summary-v1",
        "gateCount": total,
        "closedGateCount": closed,
        "implementedAwaitingRetailGateCount": counts["implemented-awaiting-retail"],
        "partialGateCount": counts["partial"],
        "openGateCount": counts["open"],
        "release100Percent": release100,
        "blockerCount": len(blockers),
        "blockerIds": [row["id"] for row in blockers],
        "blockers": blockers,
        "policy": (
            "No intermediate numeric percent is manufactured from partial gates. "
            "release100Percent becomes true only when every required gate is closed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text(encoding="utf-8"))
    summary = validate(document)
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if summary["release100Percent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
