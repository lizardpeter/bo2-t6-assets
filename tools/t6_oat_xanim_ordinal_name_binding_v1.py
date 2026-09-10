#!/usr/bin/env python3
"""Bind pinned-OAT resolved T6 XAnim names to exact retail XAsset ordinals.

Authority split:
- expanded retail XFile bytes establish the physical XAsset table and type-4 ordinals;
- the exact-count Stage18D inventory establishes source-ordered XAnimParts records;
- diagnostic pinned OAT emits the runtime-resolved XAnimParts::name before the
  physical XAsset pointer advances to the next ordinal.

No filesystem ordering, name guessing, pointer-neighborhood inference, or partial
ordinal zip is accepted. All inline names must independently agree with the native
trace before packed names are promoted.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import struct
from pathlib import Path

FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
XANIM_TYPE = 4
TRACE_MARKER = "T6_XANIM_ORDINAL_NAME\t"
PINNED_OAT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cstring_end(data: bytes, pos: int, label: str) -> int:
    if pos < 0 or pos >= len(data):
        raise ValueError(f"{label} starts outside expanded stream: {pos}")
    end = data.find(b"\0", pos)
    if end < 0:
        raise ValueError(f"unterminated {label} at {pos}")
    return end + 1


def parse_xasset_table(data: bytes) -> dict:
    if len(data) < 64:
        raise ValueError("expanded XFile is shorter than T6 XAssetList front")
    block_sizes = list(struct.unpack_from("<8I", data, 8))
    p = 40
    script_count, script_ptr, dep_count, dep_ptr, asset_count, asset_ptr = struct.unpack_from("<6I", data, p)
    if script_count and script_ptr != FOLLOWING:
        raise ValueError(f"ScriptString pointer array is not FOLLOWING: 0x{script_ptr:08X}")
    if dep_count and dep_ptr != FOLLOWING:
        raise ValueError(f"dependency pointer array is not FOLLOWING: 0x{dep_ptr:08X}")
    if asset_count and asset_ptr != FOLLOWING:
        raise ValueError(f"XAsset array is not FOLLOWING: 0x{asset_ptr:08X}")

    pos = 64
    script_table = pos
    script_bytes = script_count * 4
    if pos + script_bytes > len(data):
        raise ValueError("ScriptString pointer table truncated")
    script_ptrs = struct.unpack_from(f"<{script_count}I", data, pos) if script_count else ()
    pos += script_bytes
    for index, raw in enumerate(script_ptrs):
        if raw in (FOLLOWING, INSERT):
            pos = cstring_end(data, pos, f"ScriptString[{index}]")

    dep_table = pos
    dep_bytes = dep_count * 4
    if pos + dep_bytes > len(data):
        raise ValueError("dependency pointer table truncated")
    dep_ptrs = struct.unpack_from(f"<{dep_count}I", data, pos) if dep_count else ()
    pos += dep_bytes
    for index, raw in enumerate(dep_ptrs):
        if raw in (FOLLOWING, INSERT):
            pos = cstring_end(data, pos, f"dependency[{index}]")

    asset_array = pos
    asset_bytes = asset_count * 8
    if asset_array + asset_bytes > len(data):
        raise ValueError("physical XAsset array truncated")
    assets = []
    for index in range(asset_count):
        off = asset_array + index * 8
        asset_type, raw_pointer = struct.unpack_from("<II", data, off)
        assets.append({
            "index": index,
            "assetType": asset_type,
            "rawPointer": raw_pointer,
            "tableSourceOffset": off,
        })
    xanim_ordinals = [row["index"] for row in assets if row["assetType"] == XANIM_TYPE]
    return {
        "blockSizes": block_sizes,
        "scriptCount": script_count,
        "scriptPointerTableSourceOffset": script_table,
        "dependencyCount": dep_count,
        "dependencyPointerTableSourceOffset": dep_table,
        "assetCount": asset_count,
        "assetArraySourceOffset": asset_array,
        "assetBodySourceOffset": asset_array + asset_bytes,
        "xanimOrdinals": xanim_ordinals,
    }


def parse_native_trace(text: str) -> dict[int, str]:
    rows: dict[int, str] = {}
    duplicates = []
    for line_no, line in enumerate(text.splitlines(), 1):
        marker_at = line.find(TRACE_MARKER)
        if marker_at < 0:
            continue
        payload = line[marker_at + len(TRACE_MARKER):]
        if "\t" not in payload:
            raise ValueError(f"malformed native trace line {line_no}: {line!r}")
        ordinal_text, name = payload.split("\t", 1)
        if not re.fullmatch(r"[0-9]+", ordinal_text):
            raise ValueError(f"invalid XAsset ordinal on native trace line {line_no}: {ordinal_text!r}")
        ordinal = int(ordinal_text)
        if not name or name == "<null>":
            raise ValueError(f"native XAnim ordinal {ordinal} has null/empty name")
        if "\t" in name or any(ord(ch) < 0x20 or ord(ch) > 0x7E for ch in name):
            raise ValueError(f"native XAnim ordinal {ordinal} has non-printable name {name!r}")
        if ordinal in rows:
            duplicates.append((ordinal, rows[ordinal], name, line_no))
        else:
            rows[ordinal] = name
    if duplicates:
        raise ValueError(f"duplicate native XAnim ordinal trace rows: {duplicates[:8]!r}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expanded", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--native-log", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--oat-commit", default=PINNED_OAT)
    args = parser.parse_args()

    if args.oat_commit != PINNED_OAT:
        raise SystemExit(f"refusing unpinned OAT commit {args.oat_commit!r}")

    expanded = args.expanded.read_bytes()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    native_log_bytes = args.native_log.read_bytes()
    native_log = native_log_bytes.decode("utf-8", "strict")

    expanded_sha = sha256_bytes(expanded)
    if inventory.get("expanded_sha256") != expanded_sha:
        raise SystemExit("Stage18D inventory expanded SHA-256 does not match supplied retail stream")
    records = inventory.get("records")
    if not isinstance(records, list):
        raise SystemExit("Stage18D inventory lacks records array")
    if not inventory.get("count_closes_exactly"):
        raise SystemExit("refusing partial Stage18D XAnim inventory")
    if inventory.get("overlaps_next_structural_record") != 0:
        raise SystemExit("refusing overlapping Stage18D XAnim inventory")
    if len(records) != inventory.get("raw_xasset_expected_xanim_count"):
        raise SystemExit("Stage18D XAnim population accounting drift")
    starts = [int(row["raw_struct_offset"]) for row in records]
    if starts != sorted(starts) or len(set(starts)) != len(starts):
        raise SystemExit("Stage18D records are not unique strict source order")

    table = parse_xasset_table(expanded)
    ordinals = table["xanimOrdinals"]
    if len(ordinals) != len(records):
        raise SystemExit(f"XAsset/XAnim source-order population mismatch: ordinals={len(ordinals)} records={len(records)}")
    if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals):
        raise SystemExit("physical XAsset type-4 ordinals are not unique strict order")

    native = parse_native_trace(native_log)
    native_ordinals = sorted(native)
    if native_ordinals != ordinals:
        missing = sorted(set(ordinals) - set(native_ordinals))
        extra = sorted(set(native_ordinals) - set(ordinals))
        raise SystemExit(f"native XAnim ordinal trace population mismatch: missing={missing[:20]} extra={extra[:20]}")

    rows = []
    inline_count = 0
    packed_count = 0
    inline_agreement = 0
    packed_resolved = 0
    for ordinal, record in zip(ordinals, records):
        kind = record.get("name_kind")
        native_name = native[ordinal]
        raw_hex = record.get("name_ptr_raw")
        if not isinstance(raw_hex, str) or not re.fullmatch(r"0x[0-9A-Fa-f]{8}", raw_hex):
            raise SystemExit(f"XAsset {ordinal}: invalid Stage18D raw name pointer {raw_hex!r}")
        raw = int(raw_hex, 16)
        stage_name = record.get("name")
        if kind == "inline":
            inline_count += 1
            if raw != FOLLOWING:
                raise SystemExit(f"XAsset {ordinal}: inline record does not carry FOLLOWING name pointer")
            if not isinstance(stage_name, str) or not stage_name:
                raise SystemExit(f"XAsset {ordinal}: inline record lacks Stage18D name")
            if stage_name != native_name:
                raise SystemExit(f"XAsset {ordinal}: inline/native name disagreement {stage_name!r} != {native_name!r}")
            inline_agreement += 1
            resolution = "inline_native_agreement"
        elif kind == "packed":
            packed_count += 1
            if raw in (0, FOLLOWING, INSERT):
                raise SystemExit(f"XAsset {ordinal}: packed record carries sentinel name pointer 0x{raw:08X}")
            encoded = (raw - 1) & 0xFFFFFFFF
            block = encoded >> 29
            offset = encoded & 0x1FFFFFFF
            if block != 5:
                raise SystemExit(f"XAsset {ordinal}: packed XAnim name is block {block}, expected VIRTUAL block 5")
            if stage_name is not None:
                raise SystemExit(f"XAsset {ordinal}: packed Stage18D record unexpectedly already has a name")
            packed_resolved += 1
            resolution = "packed_block5_native_resolved"
        else:
            raise SystemExit(f"XAsset {ordinal}: unsupported Stage18D name kind {kind!r}")

        encoded = None if raw in (0, FOLLOWING, INSERT) else (raw - 1) & 0xFFFFFFFF
        rows.append({
            "xassetIndex": ordinal,
            "rawStructOffset": int(record["raw_struct_offset"]),
            "rawStructEnd": int(record["raw_end_offset"]),
            "nameKind": kind,
            "rawNamePointer": raw_hex.upper().replace("X", "x"),
            "packedBlock": None if encoded is None else encoded >> 29,
            "packedOffset": None if encoded is None else encoded & 0x1FFFFFFF,
            "stage18dInlineName": stage_name,
            "nativeResolvedName": native_name,
            "resolution": resolution,
        })

    if inline_count != inventory.get("inline_record_count") or packed_count != inventory.get("packed_name_record_count"):
        raise SystemExit("Stage18D inline/packed population disagreement during native binding")
    if inline_agreement != inline_count or packed_resolved != packed_count:
        raise SystemExit("native XAnim name binding did not close all records")

    by_name: dict[str, list[int]] = collections.defaultdict(list)
    for row in rows:
        by_name[row["nativeResolvedName"]].append(row["xassetIndex"])
    duplicate_names = [
        {"name": name, "xassetIndices": indices}
        for name, indices in sorted(by_name.items())
        if len(indices) > 1
    ]

    canary = next((row for row in rows if row["rawNamePointer"] == "0xA24CB877"), None)
    if canary is None:
        raise SystemExit("retained packed XAnim canary 0xA24CB877 is absent")

    output = {
        "format": "t6-oat-xanim-ordinal-name-binding-v1",
        "authority": "SHA-pinned retail expanded XFile + exact-count Stage18D source census + pinned OAT native loader ordinal/name trace",
        "oatCommit": args.oat_commit,
        "expandedSha256": expanded_sha,
        "nativeLogSha256": sha256_bytes(native_log_bytes),
        "xassetCount": table["assetCount"],
        "xanimCount": len(rows),
        "inlineNameCount": inline_count,
        "inlineNativeAgreementCount": inline_agreement,
        "packedNameCount": packed_count,
        "packedNativeResolvedCount": packed_resolved,
        "unresolvedNameCount": len(rows) - inline_agreement - packed_resolved,
        "uniqueResolvedNameCount": len(by_name),
        "duplicateResolvedNameGroupCount": len(duplicate_names),
        "duplicateResolvedNameGroups": duplicate_names,
        "canary": canary,
        "rows": rows,
        "proofBoundary": "The native trace is accepted only when its ordinal set exactly equals the independently parsed type-4 XAsset ordinal set, the Stage18D structural census is exact-count/zero-overlap, and every inline Stage18D name agrees byte-for-byte with OAT. Packed names are then promoted only at their exact ordinal; no filesystem ordering or pointer-neighborhood inference participates.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k not in ("rows", "duplicateResolvedNameGroups")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
