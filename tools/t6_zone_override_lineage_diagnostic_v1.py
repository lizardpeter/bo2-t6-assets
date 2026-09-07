#!/usr/bin/env python3
"""Diagnose T6 duplicate-XAsset precedence under retained lineage evidence.

This tool is intentionally NON-AUTHORITATIVE.  It encodes the reconstructed
DB_GetZonePriority / DB_OverrideAsset rule recorded in
T6_XASSET_OVERRIDE_LINEAGE_V1_2026-09-07.md and can be used to make concrete,
falsifiable predictions for a future exact-retail executable/runtime gate.

It MUST NOT be used to select a retail asset winner in production manifests.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

# OpenBO2 a64812d21946baf710cec7fa26b98ad0d193903b,
# src/code/src_noserver/database/db_registry.cpp::DB_GetZonePriority.
ZONE_PRIORITY = {
    0x04000000: 58,
    0x10000000: 50,
    0x02000000: 8,
    0x00400000: 62,
    0x00800000: 3,
    0x01000000: 53,
    0x00200000: 12,
    0x00040000: 57,
    0x00080000: 7,
    0x00020000: 6,
    0x00004000: 55,
    0x00008000: 5,
    0x00010000: 56,
    0x00000001: 51,
    0x00000002: 1,
    0x00000004: 63,
    0x00000008: 13,
    0x00000010: 59,
    0x00000020: 9,
    0x00002000: 4,
    0x00000800: 10,
    0x00001000: 54,
    0x00000400: 60,
    0x00000080: 11,
    0x00000100: 52,
    0x00000200: 2,
    0x00000040: 61,
}

ZONE_FLAG_MASK = 0x17FFFFFF


class DiagnosticError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    label: str
    zone_flag: int
    source: str
    load_ordinal: int

    @property
    def masked_flag(self) -> int:
        return self.zone_flag & ZONE_FLAG_MASK

    @property
    def priority(self) -> int:
        try:
            return ZONE_PRIORITY[self.masked_flag]
        except KeyError as exc:
            raise DiagnosticError(
                f"candidate {self.label!r}: unknown lineage zone flag "
                f"0x{self.masked_flag:08x}"
            ) from exc


def parse_flag(value: str) -> int:
    try:
        result = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer/hex flag: {value!r}") from exc
    if not 0 <= result <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("zone flag must fit uint32")
    return result


def load_candidates(path: Path) -> list[Candidate]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("candidates")
    if not isinstance(rows, list) or len(rows) < 2:
        raise DiagnosticError("input must contain at least two candidates")
    result: list[Candidate] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise DiagnosticError(f"candidate {i}: expected object")
        label = row.get("label")
        if not isinstance(label, str) or not label:
            raise DiagnosticError(f"candidate {i}: non-empty label required")
        if label in seen:
            raise DiagnosticError(f"duplicate candidate label {label!r}")
        seen.add(label)
        value = row.get("zoneFlag")
        if isinstance(value, str):
            zone_flag = parse_flag(value)
        elif isinstance(value, int) and not isinstance(value, bool):
            zone_flag = value
        else:
            raise DiagnosticError(f"candidate {label!r}: zoneFlag int/hex string required")
        if not 0 <= zone_flag <= 0xFFFFFFFF:
            raise DiagnosticError(f"candidate {label!r}: zoneFlag outside uint32")
        source = row.get("zoneFlagSource", "unspecified")
        if not isinstance(source, str) or not source:
            raise DiagnosticError(f"candidate {label!r}: invalid zoneFlagSource")
        ordinal = row.get("loadOrdinal", i)
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
            raise DiagnosticError(f"candidate {label!r}: loadOrdinal must be >= 0")
        result.append(Candidate(label, zone_flag, source, ordinal))
    if len({c.load_ordinal for c in result}) != len(result):
        raise DiagnosticError("loadOrdinal values must be unique")
    return result


def diagnose(candidates: list[Candidate]) -> dict:
    # Under the inspected lineage rule a higher priority supersedes a lower one;
    # equality is resolved by the later loaded candidate because DB_OverrideAsset
    # uses >=.  We model this only to generate a prediction to test later.
    ordered = sorted(candidates, key=lambda c: c.load_ordinal)
    primary = ordered[0]
    events = []
    for candidate in ordered[1:]:
        override = candidate.priority >= primary.priority
        events.append(
            {
                "new": candidate.label,
                "existing": primary.label,
                "newPriority": candidate.priority,
                "existingPriority": primary.priority,
                "lineageWouldOverride": override,
            }
        )
        if override:
            primary = candidate

    ranked = sorted(
        candidates,
        key=lambda c: (c.priority, c.load_ordinal),
        reverse=True,
    )
    return {
        "format": "t6-zone-override-lineage-diagnostic-v1",
        "authoritative": False,
        "authorityState": "lineage_prediction_only",
        "lineage": {
            "primarySource": {
                "repository": "builtbyxeno/OpenBO2",
                "commit": "a64812d21946baf710cec7fa26b98ad0d193903b",
                "functions": ["DB_GetZonePriority", "DB_OverrideAsset", "DB_LinkXAssetEntry"],
            },
            "rule": "new_priority >= existing_priority; primary payload swaps on override",
            "zoneFlagMask": f"0x{ZONE_FLAG_MASK:08x}",
        },
        "candidates": [
            {
                "label": c.label,
                "zoneFlag": f"0x{c.zone_flag:08x}",
                "maskedFlag": f"0x{c.masked_flag:08x}",
                "priority": c.priority,
                "zoneFlagSource": c.source,
                "loadOrdinal": c.load_ordinal,
            }
            for c in ordered
        ],
        "events": events,
        "lineagePredictedPrimary": primary.label,
        "lineagePriorityOrder": [c.label for c in ranked],
        "proofBoundary": (
            "NON-AUTHORITATIVE diagnostic. The priority table/link algorithm is retained T6 lineage, "
            "not yet instruction-byte-closed against SHA-256 "
            "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1. "
            "Zone-flag labels from additional reconstruction sources are also lineage evidence. "
            "Do not use lineagePredictedPrimary to choose a retail XAsset in a production census. "
            "Promotion requires exact retail static proof or a genuine runtime duplicate-chain observation."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = diagnose(load_candidates(a.input.resolve()))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authoritative": result["authoritative"],
        "lineagePredictedPrimary": result["lineagePredictedPrimary"],
        "lineagePriorityOrder": result["lineagePriorityOrder"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
