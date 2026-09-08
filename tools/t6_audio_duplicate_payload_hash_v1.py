#!/usr/bin/env python3
"""Hash exact physical payload spans for duplicated T6 SABS/SABL identifiers.

The retained physical manifest already proves every bank table entry, offset, size and
bank SHA. This module adds a stronger byte-level layer: for every identifier that
occurs in more than one physical bank entry, hash the exact `[dataOffset,dataEndOffset)`
payload bytes from SHA-verified bank files and require complete occurrence coverage.

Stored 128-bit bank checksum records are retained as metadata only; they are not used
as a substitute for payload SHA-256 equality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def _read_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def duplicate_ids(physical: dict) -> dict[str, int]:
    if physical.get("format") != "t6-audio-physical-id-manifest-v1":
        raise ValueError("unexpected physical manifest format")
    counts = {str(k): int(v) for k, v in physical.get("identifierOccurrenceCounts", {}).items()}
    return {k: v for k, v in counts.items() if v > 1}


def expected_occurrences(physical: dict) -> dict[tuple[str, int, str], dict]:
    dups = duplicate_ids(physical)
    out: dict[tuple[str, int, str], dict] = {}
    for e in physical.get("entries", []):
        ident = e["identifierHex"]
        if ident not in dups:
            continue
        key = (e["bankPath"], int(e["entryIndex"]), ident)
        if key in out:
            raise ValueError(f"duplicate physical occurrence key {key}")
        out[key] = e
    if len(out) != sum(dups.values()):
        raise ValueError(f"duplicate occurrence population mismatch: {len(out)} != {sum(dups.values())}")
    return out


def hash_bank_payloads(physical: dict, bank_path: str, bank_bytes: bytes) -> dict:
    banks = {b["zipPath"]: b for b in physical.get("banks", [])}
    meta = banks.get(bank_path)
    if meta is None:
        raise ValueError(f"bank not present in physical manifest: {bank_path}")
    bank_sha = hashlib.sha256(bank_bytes).hexdigest()
    expected_bank_sha = meta["bank"]["sha256"]
    if bank_sha != expected_bank_sha:
        raise ValueError(f"{bank_path}: bank SHA mismatch {bank_sha} != {expected_bank_sha}")
    if len(bank_bytes) != int(meta["bank"]["bytes"]):
        raise ValueError(f"{bank_path}: bank byte count mismatch")

    dups = duplicate_ids(physical)
    rows = []
    for e in physical.get("entries", []):
        if e["bankPath"] != bank_path or e["identifierHex"] not in dups:
            continue
        start = int(e["dataOffset"]); end = int(e["dataEndOffset"]); size = int(e["dataBytes"])
        if not (0 <= start <= end <= len(bank_bytes)) or end - start != size:
            raise ValueError(f"{bank_path} entry {e['entryIndex']}: invalid payload span")
        payload = bank_bytes[start:end]
        rows.append({
            "bankPath": bank_path,
            "bankSha256": bank_sha,
            "entryIndex": int(e["entryIndex"]),
            "identifierHex": e["identifierHex"],
            "dataOffset": start,
            "dataBytes": size,
            "dataEndOffset": end,
            "payloadSha256": hashlib.sha256(payload).hexdigest(),
            "checksum128Hex": e["checksum128Hex"],
            "formatName": e["formatName"],
            "sampleCount": int(e["sampleCount"]),
            "sampleRateHz": e["sampleRateHz"],
            "channels": int(e["channels"]),
            "loopRaw": int(e["loopRaw"]),
        })
    return {
        "format": "t6-audio-duplicate-payload-hash-bank-v1",
        "bankPath": bank_path,
        "bankSha256": bank_sha,
        "rows": rows,
        "summary": {"duplicateIdentifierOccurrenceCountInBank": len(rows)},
    }


def aggregate(physical: dict, observations: list[dict], *, physical_sha256: str = "") -> dict:
    dups = duplicate_ids(physical)
    expected = expected_occurrences(physical)
    seen: dict[tuple[str, int, str], dict] = {}
    for obs in observations:
        if obs.get("format") not in {"t6-audio-duplicate-payload-hash-bank-v1", "t6-audio-duplicate-payload-hash-shard-v1"}:
            raise ValueError("unexpected duplicate payload observation format")
        for row in obs.get("rows", []):
            key = (row["bankPath"], int(row["entryIndex"]), row["identifierHex"])
            if key in seen:
                raise ValueError(f"duplicate observed occurrence {key}")
            if key not in expected:
                raise ValueError(f"unexpected observed occurrence {key}")
            exp = expected[key]
            for field in ("dataOffset", "dataBytes", "dataEndOffset", "checksum128Hex", "formatName", "sampleCount", "sampleRateHz", "channels", "loopRaw"):
                if row[field] != exp[field]:
                    raise ValueError(f"{key}: observed {field} disagrees with physical manifest")
            seen[key] = row

    missing = sorted(set(expected) - set(seen))
    if missing:
        raise ValueError(f"missing duplicate payload occurrences: {len(missing)}")

    by_id: dict[str, list[dict]] = defaultdict(list)
    for row in seen.values():
        by_id[row["identifierHex"]].append(row)
    if set(by_id) != set(dups):
        raise ValueError("observed duplicated identifier set does not equal physical manifest duplicated set")

    equal_ids = []
    divergent_ids = []
    max_mult = 0
    for ident in sorted(by_id):
        rows = sorted(by_id[ident], key=lambda r: (r["bankPath"], r["entryIndex"]))
        max_mult = max(max_mult, len(rows))
        if len(rows) != dups[ident]:
            raise ValueError(f"{ident}: occurrence multiplicity changed")
        hashes = sorted({r["payloadSha256"] for r in rows})
        item = {
            "identifierHex": ident,
            "occurrenceCount": len(rows),
            "uniquePayloadSha256Count": len(hashes),
            "payloadSha256": hashes[0] if len(hashes) == 1 else "",
            "payloadSha256Values": hashes,
            "occurrences": rows,
        }
        if len(hashes) == 1:
            equal_ids.append(item)
        else:
            divergent_ids.append(item)

    return {
        "format": "t6-audio-duplicate-payload-closure-v1",
        "source": {"physicalManifestSha256": physical_sha256},
        "summary": {
            "physicalEntryCount": int(physical["summary"]["entryCount"]),
            "uniquePhysicalIdentifierCount": int(physical["summary"]["uniqueIdentifierCount"]),
            "duplicatedIdentifierCount": len(dups),
            "duplicatedIdentifierOccurrenceCount": len(expected),
            "duplicateExtraOccurrenceCount": len(expected) - len(dups),
            "maxIdentifierMultiplicity": max_mult,
            "payloadByteEqualDuplicatedIdentifierCount": len(equal_ids),
            "payloadByteDivergentDuplicatedIdentifierCount": len(divergent_ids),
            "payloadByteDivergentOccurrenceCount": sum(x["occurrenceCount"] for x in divergent_ids),
        },
        "equalIdentifiers": equal_ids,
        "divergentIdentifiers": divergent_ids,
        "proofBoundary": (
            "Exact SHA-256 comparison of every physical payload byte span for every identifier duplicated in the complete 116-bank T6 manifest. "
            "Each source bank must reproduce its retained full-bank SHA-256 before payload hashing. Coverage is exact over (bankPath,entryIndex,identifier). "
            "Stored 128-bit checksum records and matching metadata are retained but never substituted for payload-byte hashes. "
            "This proves duplicate payload equality/divergence only; it does not establish runtime bank precedence or alias selection."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bank")
    b.add_argument("--physical", type=Path, required=True)
    b.add_argument("--bank-path", required=True)
    b.add_argument("--bank-file", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("aggregate")
    a.add_argument("--physical", type=Path, required=True)
    a.add_argument("--observation", type=Path, action="append", required=True)
    a.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    physical, psha = _read_json(args.physical)
    if args.cmd == "bank":
        result = hash_bank_payloads(physical, args.bank_path, args.bank_file.read_bytes())
    else:
        observations = [_read_json(x)[0] for x in args.observation]
        result = aggregate(physical, observations, physical_sha256=psha)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
