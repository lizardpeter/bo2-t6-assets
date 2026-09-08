#!/usr/bin/env python3
"""Compatibility adapter for retained Stage-18D raw T6 analyzers.

The older Stage-18D XAnim and WeaponAttachmentUnique tools accept a small helper
module through ``--raw-parser``.  This adapter reconstructs that interface from
the now-durable raw XFile layout without adding any semantic guesses.

Authority is the expanded retail T6 XFile byte stream.  It exposes:

* exact eight XBlock sizes;
* ScriptStringList values in source order;
* exact XAsset array rows with raw/decoded 32-bit headers;
* asset type counts and body-stream boundary;
* the same T6 packed-pointer decoding used by later raw tools.
"""
from __future__ import annotations

import hashlib
import struct
from collections import Counter
from typing import Any

import t6_raw_xasset_inventory as base

PTR_FOLLOWING = base.PTR_FOLLOWING
PTR_INSERT = base.PTR_INSERT
BLOCK_NAMES = base.BLOCK_NAMES
ASSET_TYPES = base.ASSET_TYPES


def decode_zone_pointer(value: int, block_sizes: list[int]) -> dict[str, Any]:
    row = base.zone_pointer(int(value) & 0xFFFFFFFF, block_sizes)
    kind = row.get("kind")
    out = {
        "raw": f"0x{int(value) & 0xFFFFFFFF:08X}",
        "kind": kind,
        "block": row.get("block"),
        "block_name": row.get("block_name"),
        "offset": row.get("offset"),
    }
    if kind == "packed":
        block = row.get("block")
        offset = row.get("offset")
        valid = (
            isinstance(block, int)
            and isinstance(offset, int)
            and 0 <= block < len(block_sizes)
            and 0 <= offset < int(block_sizes[block])
        )
        out["valid_for_declared_block_size"] = valid
        out["valid"] = valid
    else:
        out["valid_for_declared_block_size"] = True
        out["valid"] = True
    return out


def _cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.find(b"\0", pos)
    if end < 0:
        raise ValueError(f"unterminated cstring at {pos}")
    raw = data[pos:end]
    return raw.decode("latin1"), end + 1


def parse_front(data: bytes) -> dict[str, Any]:
    if len(data) < 64:
        raise ValueError("expanded XFile too short")
    declared_size, external_size = struct.unpack_from("<II", data, 0)
    blocks = list(struct.unpack_from("<8I", data, 8))
    pos = 40
    sc, sp, dc, dp, ac, ap = struct.unpack_from("<6I", data, pos)
    pos += 24

    script_strings: list[str | None] = []
    if sc:
        if sp != PTR_FOLLOWING:
            raise ValueError("ScriptStringList pointer is not FOLLOWING")
        ptrs = list(struct.unpack_from(f"<{sc}I", data, pos))
        pos += sc * 4
        for ptr in ptrs:
            if ptr == 0:
                script_strings.append(None)
            elif ptr == PTR_FOLLOWING:
                text, pos = _cstring(data, pos)
                script_strings.append(text)
            else:
                raise ValueError(f"unexpected ScriptString pointer 0x{ptr:08X}")

    dependencies: list[str | None] = []
    if dc:
        if dp != PTR_FOLLOWING:
            raise ValueError("dependency-list pointer is not FOLLOWING")
        ptrs = list(struct.unpack_from(f"<{dc}I", data, pos))
        pos += dc * 4
        for ptr in ptrs:
            if ptr == 0:
                dependencies.append(None)
            elif ptr == PTR_FOLLOWING:
                text, pos = _cstring(data, pos)
                dependencies.append(text)
            else:
                raise ValueError(f"unexpected dependency pointer 0x{ptr:08X}")

    if ap != PTR_FOLLOWING:
        raise ValueError("XAsset array pointer is not FOLLOWING")
    asset_array = pos
    assets = []
    counts: Counter[str] = Counter()
    for index in range(ac):
        asset_type, header_raw = struct.unpack_from("<II", data, pos)
        pos += 8
        if not 0 <= asset_type < len(ASSET_TYPES):
            raise ValueError(f"bad XAsset type {asset_type} at index {index}")
        type_name = ASSET_TYPES[asset_type]
        counts[type_name] += 1
        assets.append({
            "index": index,
            "type_index": asset_type,
            "type": type_name,
            "header_raw": f"0x{header_raw:08X}",
            "header": decode_zone_pointer(header_raw, blocks),
        })

    return {
        "expanded_bytes": len(data),
        "expanded_sha256": hashlib.sha256(data).hexdigest(),
        "declared_zone_size": declared_size,
        "declared_external_size": external_size,
        "block_sizes": [
            {"index": i, "name": BLOCK_NAMES[i], "bytes": n}
            for i, n in enumerate(blocks)
        ],
        "script_string_count": sc,
        "script_strings": script_strings,
        "dependency_count": dc,
        "dependencies": dependencies,
        "asset_count": ac,
        "asset_array_raw_offset": asset_array,
        "asset_body_stream_raw_offset": pos,
        "asset_type_counts": dict(sorted(counts.items())),
        "assets": assets,
    }
