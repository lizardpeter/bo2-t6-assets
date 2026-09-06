#!/usr/bin/env python3
"""Byte-level synthetic regression for t6_raw_xasset_inventory_v2.py."""
from __future__ import annotations

import struct

from t6_raw_xasset_inventory_v2 import (
    ASSET_TYPES,
    PTR_FOLLOWING,
    decode_zone_pointer,
    parse_front,
)


def packed_pointer(block: int, offset: int) -> int:
    if not 0 <= block < 8:
        raise ValueError(block)
    if not 0 <= offset <= 0x1FFFFFFF:
        raise ValueError(offset)
    return ((block << 29) | offset) + 1


def synthetic_stream() -> bytes:
    # Header: two arbitrary declared sizes + 8 XFile block sizes.
    blocks = [64, 64, 64, 64, 64, 1024, 1024, 64]
    data = bytearray()
    data += struct.pack("<II8I", 4096, 0, *blocks)

    # XAssetList at raw offset 40:
    # 2 ScriptStrings, no dependency list, 2 XAssets, all inline.
    data += struct.pack(
        "<6I",
        2,
        PTR_FOLLOWING,
        0,
        0,
        2,
        PTR_FOLLOWING,
    )

    # ScriptString pointer table. String 0 is inline; string 1 is a null entry.
    data += struct.pack("<2I", PTR_FOLLOWING, 0)
    data += b"j_gun\0"

    # XAsset array. First header is a valid packed VIRTUAL pointer, second is
    # FOLLOWING. The body itself is intentionally absent: this regression is
    # only for the front/XAsset-header contract.
    data += struct.pack("<II", ASSET_TYPES.index("XANIMPARTS"), packed_pointer(5, 32))
    data += struct.pack("<II", ASSET_TYPES.index("XMODEL"), PTR_FOLLOWING)
    return bytes(data)


def main() -> int:
    data = synthetic_stream()
    doc = parse_front(data)

    assert doc["script_string_count"] == 2
    assert doc["script_strings"] == ["j_gun", None]
    assert doc["script_string_validation"] == {
        "count": 2,
        "nullCount": 1,
        "allIndicesPreserved": True,
    }

    assert doc["asset_count"] == 2
    assert doc["asset_type_counts"] == {"XANIMPARTS": 1, "XMODEL": 1}
    assert [a["type"] for a in doc["assets"]] == ["XANIMPARTS", "XMODEL"]

    first = doc["assets"][0]
    assert first["index"] == 0
    assert first["header"]["kind"] == "packed"
    assert first["header"]["block"] == 5
    assert first["header"]["offset"] == 32
    assert first["header"]["valid_for_declared_block_size"] is True

    second = doc["assets"][1]
    assert second["header"]["kind"] == "following"
    assert second["header"]["valid_for_declared_block_size"] is True

    assert doc["asset_header_summary"] == {
        "count": 2,
        "packed": 1,
        "following": 1,
        "insert": 0,
        "null": 0,
        "invalidPacked": 0,
    }

    bad = decode_zone_pointer(packed_pointer(5, 2048), [64, 64, 64, 64, 64, 1024, 1024, 64])
    assert bad["kind"] == "packed"
    assert bad["valid_for_declared_block_size"] is False

    print("PASS: T6 raw XAsset inventory v2 byte-level regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
