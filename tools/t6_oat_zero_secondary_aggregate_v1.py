#!/usr/bin/env python3
"""Aggregate native OAT zero-asset Secondary resolutions and require exact raw-census coverage."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def _read(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def row_key(row: dict) -> tuple[str, str, int]:
    return row["bankName"], row["aliasIdHex"], int(row["variantIndex"])


def build(zero: dict, shards: list[tuple[dict, str]], *, expected_zero_count: int | None = None, expected_bank_count: int | None = None) -> dict:
    if zero.get("format") != "t6-sndalias-zero-asset-all-fastfile-v1":
        raise ValueError("unexpected zero census format")
    raw_zero_rows = zero.get("zeroRows", [])
    zero_count = len(raw_zero_rows)
    if expected_zero_count is not None and zero_count != expected_zero_count:
        raise ValueError(f"zero row population changed: {zero_count} != {expected_zero_count}")

    raw_keys = [
        (r["bankName"], r["aliasListIdHex"], int(r["variantIndex"]))
        for r in raw_zero_rows
    ]
    if len(raw_keys) != len(set(raw_keys)):
        raise ValueError("raw zero census has duplicate bank/alias/variant keys")
    raw_key_set = set(raw_keys)
    expected_banks = sorted({r["bankName"] for r in raw_zero_rows})
    if expected_bank_count is not None and len(expected_banks) != expected_bank_count:
        raise ValueError(f"zero-bearing bank population changed: {len(expected_banks)} != {expected_bank_count}")

    rows = []
    bank_counts = Counter()
    shard_hashes = []
    for shard, sha in shards:
        if shard.get("format") != "t6-oat-zero-secondary-resolver-v1":
            raise ValueError("unexpected native resolver shard format")
        shard_hashes.append(sha)
        for row in shard.get("rows", []):
            rows.append(row)
            bank_counts[row["bankName"]] += 1

    keys = [row_key(r) for r in rows]
    if len(keys) != len(set(keys)):
        duplicates = [k for k, c in Counter(keys).items() if c > 1]
        raise ValueError(f"duplicate native resolution keys: {duplicates[:10]}")
    key_set = set(keys)
    missing = sorted(raw_key_set - key_set)
    extra = sorted(key_set - raw_key_set)
    if missing or extra:
        raise ValueError(f"native/raw coverage disagreement: missing={len(missing)} extra={len(extra)}")
    if sorted(bank_counts) != expected_banks:
        raise ValueError("native shard bank set does not exactly equal zero-bearing bank set")

    pointer_states = Counter()
    resolved_by_state = Counter()
    secondary_names = Counter()
    noninline_unresolved = []
    bank_summary: dict[str, dict] = {}
    by_bank: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        state = row["rawSecondaryPointerState"]
        pointer_states[state] += 1
        secondary = row["resolvedSecondaryName"]
        if secondary:
            resolved_by_state[state] += 1
            secondary_names[secondary] += 1
        if state == "other_u32" and not secondary:
            noninline_unresolved.append(row)
        by_bank[row["bankName"]].append(row)

    for bank in sorted(by_bank):
        br = by_bank[bank]
        states = Counter(r["rawSecondaryPointerState"] for r in br)
        resolved = Counter(r["rawSecondaryPointerState"] for r in br if r["resolvedSecondaryName"])
        sources = sorted({r["sourceFastFile"] for r in br})
        if len(sources) != 1:
            raise ValueError(f"{bank}: expected one source FastFile, got {sources}")
        bank_summary[bank] = {
            "sourceFastFile": sources[0],
            "zeroAssetOccurrenceCount": len(br),
            "rawSecondaryPointerStateCounts": dict(sorted(states.items())),
            "resolvedNonemptySecondaryByRawPointerState": dict(sorted(resolved.items())),
        }

    null_count = pointer_states.get("null", 0)
    inline_count = pointer_states.get("inline_serialized", 0)
    noninline_count = pointer_states.get("other_u32", 0)
    if resolved_by_state.get("null", 0) != 0:
        raise ValueError("raw null Secondary resolved non-empty")
    if resolved_by_state.get("inline_serialized", 0) != inline_count:
        raise ValueError("not every inline serialized Secondary reproduced through native OAT")

    expected_pointer_states = zero.get("summary", {}).get("zeroPointerStateCounts", {}).get("secondary_ptr", {})
    expected_pointer_states = {k: int(v) for k, v in expected_pointer_states.items()}
    if expected_pointer_states and dict(sorted(pointer_states.items())) != dict(sorted(expected_pointer_states.items())):
        raise ValueError(
            f"native pointer-state population differs from raw zero census: {dict(pointer_states)} != {expected_pointer_states}"
        )

    return {
        "format": "t6-oat-zero-secondary-all-fastfile-v1",
        "summary": {
            "coveredBankCount": len(expected_banks),
            "coveredZeroAssetOccurrenceCount": len(rows),
            "rawSecondaryPointerStateCounts": dict(sorted(pointer_states.items())),
            "resolvedNonemptySecondaryByRawPointerState": dict(sorted(resolved_by_state.items())),
            "nonInlineSecondaryPointerOccurrenceCount": noninline_count,
            "nonInlineSecondaryResolvedNonemptyCount": resolved_by_state.get("other_u32", 0),
            "nonInlineSecondaryResolvedEmptyCount": len(noninline_unresolved),
            "totalResolvedNonemptySecondaryOccurrenceCount": sum(resolved_by_state.values()),
            "uniqueResolvedNonemptySecondaryNameCount": len(secondary_names),
        },
        "resolvedSecondaryNameOccurrenceCounts": dict(sorted(secondary_names.items())),
        "banks": bank_summary,
        "rows": sorted(rows, key=lambda r: (r["bankName"], r["aliasIdHex"], int(r["variantIndex"]))),
        "nonInlineSecondaryUnresolvedRows": noninline_unresolved,
        "shardJsonSha256": sorted(shard_hashes),
        "proofBoundary": (
            "Complete native loaded-SndBank Secondary resolution for the exact raw zero-asset census keys supplied. "
            "Coverage requires an exact set equality over (bankName, aliasId, variantIndex); raw serialized 32-bit pointer values are never interpreted. "
            "Native OAT must reproduce every inline Secondary exactly, and raw null Secondary pointers must remain empty. "
            "Non-inline strings are authoritative only as post-loader OAT `alias.secondaryName` values. "
            "This closes string resolution, not retail playback, fallback, recursion, sequencing, variant selection, or zone precedence."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zero", type=Path, required=True)
    p.add_argument("--shard", type=Path, action="append", required=True)
    p.add_argument("--expected-zero-count", type=int, default=4094)
    p.add_argument("--expected-bank-count", type=int, default=37)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    zero, zsha = _read(a.zero)
    shards = [_read(path) for path in a.shard]
    result = build(zero, shards, expected_zero_count=a.expected_zero_count, expected_bank_count=a.expected_bank_count)
    result["source"] = {"zeroAssetCensusSha256": zsha}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
