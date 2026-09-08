#!/usr/bin/env python3
"""Extract exact physical payload spans for selected T6 SABS/SABL identifiers.

The bank structure is validated by t6_audio_bank_id_manifest_v1.parse_bank.
Target identity is the serialized 32-bit SndAlias.assetId / bank identifier.
No filename mapping or runtime variant selection is involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_audio_bank_id_manifest_v1 import parse_bank

FORMAT = "t6-audio-target-payload-extract-v1"


def norm_id(text: str) -> str:
    s = text.strip().upper()
    if s.startswith("0X"):
        s = s[2:]
    value = int(s, 16)
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"identifier outside u32: {text!r}")
    return f"{value:08X}"


def extract(bank_path: Path, targets: list[str], out_dir: Path, source: str = "") -> dict[str, Any]:
    raw = bank_path.read_bytes()
    bank = parse_bank(raw, source=source or str(bank_path))
    target_ids = list(dict.fromkeys(norm_id(x) for x in targets))
    if not target_ids:
        raise ValueError("no target identifiers")

    by_id: dict[str, list[dict[str, Any]]] = {x: [] for x in target_ids}
    for entry in bank["entries"]:
        ident = entry["identifierHex"]
        if ident not in by_id:
            continue
        if not entry["dataInsideFile"]:
            raise ValueError(f"target {ident} payload extends outside bank")
        start = int(entry["dataOffset"])
        end = int(entry["dataEndOffset"])
        payload = raw[start:end]
        if len(payload) != int(entry["dataBytes"]):
            raise ValueError(f"target {ident} payload length mismatch")
        row = dict(entry)
        row["payloadSha256"] = hashlib.sha256(payload).hexdigest()
        row["payloadFile"] = ""
        by_id[ident].append((row, payload))

    missing = [x for x in target_ids if not by_id[x]]
    if missing:
        raise ValueError(f"target identifiers absent from validated bank: {missing}")

    out_dir.mkdir(parents=True, exist_ok=True)
    target_rows = []
    for ident in target_ids:
        occurrences = []
        items = by_id[ident]
        for occurrence_index, (row, payload) in enumerate(items):
            filename = f"{ident}.bin" if len(items) == 1 else f"{ident}_{occurrence_index}.bin"
            path = out_dir / filename
            path.write_bytes(payload)
            if hashlib.sha256(path.read_bytes()).hexdigest() != row["payloadSha256"]:
                raise ValueError(f"written payload hash mismatch for {ident}")
            row["payloadFile"] = filename
            row["occurrenceIndex"] = occurrence_index
            occurrences.append(row)
        target_rows.append({
            "identifierHex": ident,
            "occurrenceCount": len(occurrences),
            "uniquePayloadSha256": sorted({x["payloadSha256"] for x in occurrences}),
            "uniqueChecksum128Hex": sorted({x["checksum128Hex"] for x in occurrences}),
            "occurrences": occurrences,
        })

    return {
        "format": FORMAT,
        "source": source or str(bank_path),
        "bank": bank["bank"],
        "bankSummary": bank["summary"],
        "summary": {
            "targetIdentifierCount": len(target_ids),
            "foundTargetIdentifierCount": len(target_rows),
            "missingTargetIdentifierCount": 0,
            "targetPhysicalOccurrenceCount": sum(x["occurrenceCount"] for x in target_rows),
            "targetPayloadBytes": sum(
                int(o["dataBytes"]) for x in target_rows for o in x["occurrences"]
            ),
        },
        "targets": target_rows,
        "proofBoundary": (
            "The complete physical T6 bank is structurally validated before target extraction. "
            "Every target is an exact 32-bit bank identifier and every emitted payload is the exact "
            "table-declared byte span, SHA-256 hashed after extraction. Sample rate, channels, format, "
            "loop state and checksum are read from the validated bank table. No external filename "
            "mapping, SndAlias runtime variant selection, bank activation rule, or playback semantics are inferred."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("bank", type=Path)
    p.add_argument("--target", action="append", default=[])
    p.add_argument("--target-file", type=Path)
    p.add_argument("--source", default="")
    p.add_argument("--payload-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()

    targets = list(a.target)
    if a.target_file:
        targets.extend(x.strip() for x in a.target_file.read_text(encoding="utf-8").splitlines() if x.strip())
    result = extract(a.bank, targets, a.payload_dir, a.source)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    for row in result["targets"]:
        print(row["identifierHex"], row["occurrenceCount"], row["uniquePayloadSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
