#!/usr/bin/env python3
import importlib.util
import struct
from pathlib import Path

P = Path(__file__).with_name("t6_virtual_front_map_v1.py")
spec = importlib.util.spec_from_file_location("frontmap", P)
mod = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(mod)

FOLLOWING = 0xFFFFFFFF


def packed(block: int, offset: int) -> int:
    return (((block << 29) | offset) + 1) & 0xFFFFFFFF


def fixture() -> bytes:
    # Header + front data. The declared VIRTUAL block is intentionally larger
    # than this synthetic front so later offsets remain valid packed targets.
    b = bytearray(256)
    struct.pack_into("<II", b, 0, 256, 0)
    blocks = [4096] * 8
    struct.pack_into("<8I", b, 8, *blocks)
    # Two ScriptStrings, one dependency, one XAsset.
    struct.pack_into("<6I", b, 40, 2, FOLLOWING, 1, FOLLOWING, 1, FOLLOWING)
    pos = 64
    struct.pack_into("<2I", b, pos, FOLLOWING, FOLLOWING)
    pos += 8
    b[pos:pos + 6] = b"alpha\0"
    pos += 6
    b[pos:pos + 15] = b"peacekeeper_mp\0"
    pos += 15
    struct.pack_into("<I", b, pos, FOLLOWING)
    pos += 4
    b[pos:pos + 4] = b"dep\0"
    pos += 4
    struct.pack_into("<II", b, pos, 25, FOLLOWING)
    pos += 8
    return bytes(b[:pos])


data = fixture()
front = mod.build_front_map(data)
assert front["assetBodyRawOffset"] == len(data), front
# VIRTUAL: 8-byte SS ptr table + 6 + 15 = 29; align to 32;
# dep ptr 4 + dep string 4 = 40; asset array 8 => 48.
assert front["virtualOffsetAfterAssetArray"] == 48, front["virtualOffsetAfterAssetArray"]

peace = [a for a in front["allocations"] if a["kind"] == "script-string" and a["text"] == "peacekeeper_mp"]
assert len(peace) == 1, peace
peace_off = peace[0]["virtualStart"]
assert peace_off == 14, peace

exact = mod.resolve_packed_pointer(front, packed(5, peace_off))
assert exact["status"] == "exact-front-xstring", exact
assert exact["text"] == "peacekeeper_mp", exact

interior = mod.resolve_packed_pointer(front, packed(5, peace_off + 1))
assert interior["status"] == "front-xstring-interior", interior

asset = [a for a in front["allocations"] if a["kind"] == "xasset-array"]
assert len(asset) == 1
header_off = asset[0]["virtualStart"] + 4
header = mod.resolve_packed_pointer(front, packed(5, header_off))
assert header["status"] == "xasset-header-slot", header
assert header["assetIndex"] == 0, header

later = mod.resolve_packed_pointer(front, packed(5, front["virtualOffsetAfterAssetArray"] + 100))
assert later["status"] == "later-virtual-allocation", later

non_virtual = mod.resolve_packed_pointer(front, packed(0, 10))
assert non_virtual["status"] == "packed-non-virtual-block", non_virtual

print("test_t6_virtual_front_map_v1: PASS")
