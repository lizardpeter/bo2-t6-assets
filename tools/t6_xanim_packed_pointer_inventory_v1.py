#!/usr/bin/env python3
"""Exact packed-pointer census for a count-closed expanded retail T6 XAnim corpus.

This tool does not resolve packed pointers. It freezes the dependency population
needed by the next native/OAT alias proof and deliberately keeps direct XString
name offsets separate from XAnim child/member pointers.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

FOLLOW = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
XANIM_TYPE = 4
XANIM_FIXED = 104
PTR_FIELDS = [
    ("XAnimParts.name", 0, "direct_xstring"),
    ("XAnimParts.names", 64, "temp_member"),
    ("XAnimParts.dataByte", 68, "temp_member"),
    ("XAnimParts.dataShort", 72, "temp_member"),
    ("XAnimParts.dataInt", 76, "temp_member"),
    ("XAnimParts.randomDataShort", 80, "temp_member"),
    ("XAnimParts.randomDataByte", 84, "temp_member"),
    ("XAnimParts.randomDataInt", 88, "temp_member"),
    ("XAnimParts.indices", 92, "temp_member"),
    ("XAnimParts.notify", 96, "temp_member"),
    ("XAnimParts.deltaPart", 100, "temp_member"),
]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def ptr(raw: int, blocks: list[int]) -> dict:
    raw &= 0xFFFFFFFF
    if raw == 0:
        return {"kind": "null", "raw": raw, "rawHex": "0x00000000"}
    if raw == FOLLOW:
        return {"kind": "following", "raw": raw, "rawHex": "0xFFFFFFFF"}
    if raw == INSERT:
        return {"kind": "insert", "raw": raw, "rawHex": "0xFFFFFFFE"}
    enc = (raw - 1) & 0xFFFFFFFF
    block = enc >> 29
    offset = enc & 0x1FFFFFFF
    if block >= len(blocks) or offset >= blocks[block]:
        raise ValueError(f"packed pointer 0x{raw:08X} outside declared block {block} size")
    return {"kind": "packed", "raw": raw, "rawHex": f"0x{raw:08X}", "block": block, "offset": offset}


def parse_front(data: bytes):
    blocks = list(struct.unpack_from("<8I", data, 8))
    sc, sp, dc, dp, ac, ap = struct.unpack_from("<6I", data, 40)
    if ap != FOLLOW:
        raise ValueError(f"XAsset array pointer is 0x{ap:08X}, expected FOLLOWING")
    pos = 64
    if sc:
        if sp != FOLLOW:
            raise ValueError("ScriptString pointer array is not FOLLOWING")
        ptrs = struct.unpack_from(f"<{sc}I", data, pos)
        pos += sc * 4
        for raw in ptrs:
            if raw == FOLLOW:
                end = data.find(b"\0", pos)
                if end < 0:
                    raise ValueError("unterminated ScriptString")
                pos = end + 1
    elif sp != 0:
        raise ValueError("zero ScriptString count with nonnull pointer")
    if dc:
        if dp != FOLLOW:
            raise ValueError("dependency pointer array is not FOLLOWING")
        ptrs = struct.unpack_from(f"<{dc}I", data, pos)
        pos += dc * 4
        for raw in ptrs:
            if raw == FOLLOW:
                end = data.find(b"\0", pos)
                if end < 0:
                    raise ValueError("unterminated dependency string")
                pos = end + 1
    elif dp != 0:
        raise ValueError("zero dependency count with nonnull pointer")
    table = []
    for i in range(ac):
        typ, raw = struct.unpack_from("<II", data, pos + i * 8)
        table.append({"index": i, "type": typ, "pointer": raw})
    return blocks, table, pos + ac * 8


def locate_delta(data: bytes, start: int) -> int:
    cur = start + XANIM_FIXED
    if struct.unpack_from("<I", data, start)[0] == FOLLOW:
        end = data.find(b"\0", cur)
        if end < 0:
            raise ValueError("unterminated XAnim name")
        cur = end + 1
    all_bones = data[start + 33]
    notify = data[start + 34]
    if struct.unpack_from("<I", data, start + 64)[0] == FOLLOW:
        cur += all_bones * 2
    if struct.unpack_from("<I", data, start + 96)[0] == FOLLOW:
        cur += notify * 8
    return cur


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--full-inventory", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    source_sha = hashlib.sha256(data).hexdigest()
    blocks, table, _ = parse_front(data)
    expected_indices = [row["index"] for row in table if row["type"] == XANIM_TYPE]
    inv = json.loads(args.full_inventory.read_text(encoding="utf-8"))
    records = inv.get("records", [])
    if not inv.get("count_closes_exactly") or len(records) != len(expected_indices):
        raise SystemExit("full XAnim inventory is not exact-count closed")
    inv_sha = inv.get("expanded_sha256") or inv.get("expanded_stream_sha256")
    if inv_sha != source_sha:
        raise SystemExit(f"inventory/source SHA mismatch: {inv_sha} != {source_sha}")
    records = sorted(records, key=lambda row: int(row["raw_struct_offset"]))

    occurrences = []
    for xasset_index, row in zip(expected_indices, records):
        start = int(row["raw_struct_offset"])
        if start < 0 or start + XANIM_FIXED > len(data):
            raise SystemExit(f"bad XAnim source start {start}")
        for field, rel, cls in PTR_FIELDS:
            raw = struct.unpack_from("<I", data, start + rel)[0]
            dec = ptr(raw, blocks)
            occurrences.append({
                "xassetIndex": xasset_index,
                "fixedSourceOffset": start,
                "pointerSourceOffset": start + rel,
                "field": field,
                "class": cls,
                "pointer": dec,
            })

        delta_raw = struct.unpack_from("<I", data, start + 100)[0]
        if delta_raw == FOLLOW:
            d = locate_delta(data, start)
            if d + 12 > len(data):
                raise SystemExit(f"truncated deltaPart for XAsset {xasset_index}")
            for i, field in enumerate(("XAnimParts.deltaPart.trans", "XAnimParts.deltaPart.quat2", "XAnimParts.deltaPart.quat")):
                raw = struct.unpack_from("<I", data, d + i * 4)[0]
                occurrences.append({
                    "xassetIndex": xasset_index,
                    "fixedSourceOffset": start,
                    "pointerSourceOffset": d + i * 4,
                    "field": field,
                    "class": "nested_delta",
                    "pointer": ptr(raw, blocks),
                })

    fixed_expected = len(records) * len(PTR_FIELDS)
    fixed_actual = sum(1 for row in occurrences if row["field"] in {x[0] for x in PTR_FIELDS})
    if fixed_actual != fixed_expected:
        raise SystemExit(f"fixed pointer accounting drift {fixed_actual} != {fixed_expected}")

    kind_counts = Counter(row["pointer"]["kind"] for row in occurrences)
    class_counts = Counter(row["class"] for row in occurrences if row["pointer"]["kind"] == "packed")
    block_counts = Counter(row["pointer"]["block"] for row in occurrences if row["pointer"]["kind"] == "packed")
    packed_groups = defaultdict(list)
    for row in occurrences:
        if row["pointer"]["kind"] == "packed":
            packed_groups[row["pointer"]["rawHex"]].append(row)
    grouped = []
    for raw_hex, rows in sorted(packed_groups.items()):
        first = rows[0]["pointer"]
        grouped.append({
            "rawHex": raw_hex,
            "block": first["block"],
            "offset": first["offset"],
            "occurrenceCount": len(rows),
            "xassetIndices": sorted({row["xassetIndex"] for row in rows}),
            "fields": sorted({row["field"] for row in rows}),
            "classes": sorted({row["class"] for row in rows}),
        })

    out = {
        "format": "t6-xanim-packed-pointer-inventory-v1",
        "authority": "expanded retail T6 XFile bytes + exact-count Stage18D XAnim structural inventory",
        "expandedSha256": source_sha,
        "xassetCount": len(table),
        "xanimCount": len(records),
        "fixedPointerOccurrences": fixed_actual,
        "nestedPointerOccurrences": len(occurrences) - fixed_actual,
        "pointerOccurrences": len(occurrences),
        "pointerKindCounts": dict(sorted(kind_counts.items())),
        "packedClassCounts": dict(sorted(class_counts.items())),
        "packedBlockCounts": {str(k): v for k, v in sorted(block_counts.items())},
        "uniquePackedRawPointers": len(grouped),
        "occurrences": occurrences,
        "packedGroups": grouped,
        "proofBoundary": "Inventory only. direct_xstring packed names are kept separate from TEMP/nested XAnim dependencies. No packed pointer is dereferenced or promoted to an owner by this tool.",
    }
    if sum(kind_counts.values()) != len(occurrences):
        raise SystemExit("pointer-kind accounting drift")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("occurrences", "packedGroups")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
