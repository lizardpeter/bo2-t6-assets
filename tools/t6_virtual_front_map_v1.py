#!/usr/bin/env python3
"""Replay the proven T6 VIRTUAL front allocations and resolve packed XString targets.

Scope
-----
This tool intentionally stops at the XAsset body stream. It replays only the
front allocations that are already proven by the raw XAsset parser:

- ScriptString pointer array and FOLLOWING string payloads
- dependency pointer array and FOLLOWING string payloads
- 4-byte destination alignment between the front groups
- 8-byte XAsset array

The physical source cursor is never alignment-rounded. Destination VIRTUAL
offsets are alignment-rounded exactly where the loader does so.

A packed pointer is promoted to an exact string only when it targets the first
byte of a replayed FOLLOWING front string. Offsets into pointer arrays, the
XAsset array, string interiors, or allocations after the XAsset array remain
classified but unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
BLOCK_VIRTUAL = 5
XASSET_SIZE = 8
XASSET_HEADER_OFFSET = 4


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_cstring(data: bytes, start: int) -> tuple[str, int]:
    if start < 0 or start >= len(data):
        raise ValueError(f"string start outside stream: {start}")
    end = data.find(b"\0", start)
    if end < 0:
        raise ValueError(f"unterminated string at {start}")
    return data[start:end].decode("latin1"), end + 1


def decode_zone_pointer(value: int) -> dict[str, Any]:
    value &= 0xFFFFFFFF
    if value == 0:
        return {"kind": "null", "raw": value, "rawHex": "0x00000000"}
    if value == PTR_FOLLOWING:
        return {"kind": "following", "raw": value, "rawHex": "0xFFFFFFFF"}
    if value == PTR_INSERT:
        return {"kind": "insert", "raw": value, "rawHex": "0xFFFFFFFE"}
    encoded = (value - 1) & 0xFFFFFFFF
    return {
        "kind": "packed",
        "raw": value,
        "rawHex": f"0x{value:08X}",
        "block": encoded >> 29,
        "offset": encoded & 0x1FFFFFFF,
    }


def _alloc_record(kind: str, virtual_start: int, virtual_end: int,
                  raw_start: int, raw_end: int, **extra) -> dict[str, Any]:
    return {
        "kind": kind,
        "virtualStart": virtual_start,
        "virtualEnd": virtual_end,
        "virtualBytes": virtual_end - virtual_start,
        "rawStart": raw_start,
        "rawEnd": raw_end,
        "rawBytes": raw_end - raw_start,
        **extra,
    }


def build_front_map(data: bytes) -> dict[str, Any]:
    if len(data) < 64:
        raise ValueError("expanded stream too small for T6 XAssetList")
    block_sizes = list(struct.unpack_from("<8I", data, 8))
    sc, sp, dc, dp, ac, ap = struct.unpack_from("<6I", data, 40)
    src = 64
    virt = 0
    allocs: list[dict[str, Any]] = []

    if sc:
        if sp != PTR_FOLLOWING:
            raise ValueError(f"ScriptString pointer array is not FOLLOWING: 0x{sp:08X}")
        raw_start = src
        raw_end = raw_start + sc * 4
        if raw_end > len(data):
            raise ValueError("ScriptString pointer array truncated")
        ptrs = struct.unpack_from(f"<{sc}I", data, raw_start)
        vstart = virt
        vend = vstart + sc * 4
        allocs.append(_alloc_record("script-string-pointer-array", vstart, vend, raw_start, raw_end, count=sc))
        src = raw_end
        virt = vend
        for index, raw in enumerate(ptrs):
            if raw == 0:
                continue
            if raw != PTR_FOLLOWING:
                continue
            text, raw_end = read_cstring(data, src)
            vstart = virt
            vend = vstart + (raw_end - src)
            allocs.append(_alloc_record(
                "script-string", vstart, vend, src, raw_end,
                index=index, text=text, exactStringStart=True,
            ))
            src = raw_end
            virt = vend
    elif sp not in (0, PTR_FOLLOWING):
        raise ValueError(f"ScriptString count is zero but pointer is 0x{sp:08X}")

    virt_before_dep_align = virt
    virt = align(virt, 4)

    if dc:
        if dp != PTR_FOLLOWING:
            raise ValueError(f"dependency pointer array is not FOLLOWING: 0x{dp:08X}")
        raw_start = src
        raw_end = raw_start + dc * 4
        if raw_end > len(data):
            raise ValueError("dependency pointer array truncated")
        ptrs = struct.unpack_from(f"<{dc}I", data, raw_start)
        vstart = virt
        vend = vstart + dc * 4
        allocs.append(_alloc_record("dependency-pointer-array", vstart, vend, raw_start, raw_end, count=dc))
        src = raw_end
        virt = vend
        for index, raw in enumerate(ptrs):
            if raw == 0:
                continue
            if raw != PTR_FOLLOWING:
                continue
            text, raw_end = read_cstring(data, src)
            vstart = virt
            vend = vstart + (raw_end - src)
            allocs.append(_alloc_record(
                "dependency-string", vstart, vend, src, raw_end,
                index=index, text=text, exactStringStart=True,
            ))
            src = raw_end
            virt = vend
    elif dp not in (0, PTR_FOLLOWING):
        raise ValueError(f"dependency count is zero but pointer is 0x{dp:08X}")

    virt_before_asset_align = virt
    virt = align(virt, 4)
    if ac:
        if ap != PTR_FOLLOWING:
            raise ValueError(f"XAsset array is not FOLLOWING: 0x{ap:08X}")
        raw_start = src
        raw_end = raw_start + ac * XASSET_SIZE
        if raw_end > len(data):
            raise ValueError("XAsset array truncated")
        vstart = virt
        vend = vstart + ac * XASSET_SIZE
        allocs.append(_alloc_record(
            "xasset-array", vstart, vend, raw_start, raw_end,
            count=ac, elementBytes=XASSET_SIZE, headerOffset=XASSET_HEADER_OFFSET,
        ))
        src = raw_end
        virt = vend
    elif ap not in (0, PTR_FOLLOWING):
        raise ValueError(f"asset count is zero but pointer is 0x{ap:08X}")

    return {
        "format": "t6-virtual-front-map-v1",
        "expandedBytes": len(data),
        "expandedSha256": sha256_bytes(data),
        "blockSizes": block_sizes,
        "scriptStringCount": sc,
        "dependencyCount": dc,
        "assetCount": ac,
        "assetBodyRawOffset": src,
        "virtualOffsetAfterAssetArray": virt,
        "alignment": {
            "beforeDependency": {
                "from": virt_before_dep_align,
                "to": align(virt_before_dep_align, 4),
                "destinationOnlyBytes": align(virt_before_dep_align, 4) - virt_before_dep_align,
            },
            "beforeAssetArray": {
                "from": virt_before_asset_align,
                "to": align(virt_before_asset_align, 4),
                "destinationOnlyBytes": align(virt_before_asset_align, 4) - virt_before_asset_align,
            },
        },
        "allocations": allocs,
        "proofBoundary": (
            "Only VIRTUAL allocations before the XAsset body stream are replayed. "
            "No asset-body allocation is inferred. Exact string promotion requires "
            "an exact allocation-start match to a FOLLOWING front string."
        ),
    }


def resolve_virtual_offset(front: dict[str, Any], offset: int) -> dict[str, Any]:
    if offset < 0:
        return {"status": "invalid-negative-offset", "offset": offset}
    for alloc in front["allocations"]:
        start = int(alloc["virtualStart"])
        end = int(alloc["virtualEnd"])
        if start <= offset < end:
            delta = offset - start
            base = {
                "status": "front-allocation-match",
                "offset": offset,
                "allocationKind": alloc["kind"],
                "allocationVirtualStart": start,
                "allocationVirtualEnd": end,
                "deltaIntoAllocation": delta,
            }
            if alloc["kind"] in {"script-string", "dependency-string"}:
                base["text"] = alloc["text"]
                base["stringIndex"] = alloc["index"]
                base["exactStringStart"] = delta == 0
                if delta == 0:
                    base["status"] = "exact-front-xstring"
                else:
                    base["status"] = "front-xstring-interior"
                return base
            if alloc["kind"] == "xasset-array":
                index = delta // XASSET_SIZE
                sub = delta % XASSET_SIZE
                base["assetIndex"] = index
                base["assetByteOffset"] = sub
                if sub == XASSET_HEADER_OFFSET:
                    base["status"] = "xasset-header-slot"
                else:
                    base["status"] = "xasset-array-non-header-byte"
                return base
            return base
    end = int(front["virtualOffsetAfterAssetArray"])
    if offset >= end:
        return {
            "status": "later-virtual-allocation",
            "offset": offset,
            "virtualOffsetAfterAssetArray": end,
        }
    return {
        "status": "front-alignment-hole",
        "offset": offset,
        "virtualOffsetAfterAssetArray": end,
    }


def resolve_packed_pointer(front: dict[str, Any], raw_value: int) -> dict[str, Any]:
    dec = decode_zone_pointer(raw_value)
    if dec["kind"] != "packed":
        return {"status": f"not-packed-{dec['kind']}", "pointer": dec}
    if dec["block"] != BLOCK_VIRTUAL:
        return {"status": "packed-non-virtual-block", "pointer": dec}
    return {"pointer": dec, **resolve_virtual_offset(front, int(dec["offset"]))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--pointer", help="optional raw 32-bit zone pointer, e.g. 0xA0001234")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    front = build_front_map(data)
    if args.pointer is not None:
        front["resolution"] = resolve_packed_pointer(front, int(args.pointer, 0))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(front, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "assetBodyRawOffset": front["assetBodyRawOffset"],
        "virtualOffsetAfterAssetArray": front["virtualOffsetAfterAssetArray"],
        "resolution": front.get("resolution"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
