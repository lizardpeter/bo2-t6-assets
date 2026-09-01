#!/usr/bin/env python3
"""Census serialized T6 XAnim delta branches directly from expanded retail XFiles.

This extends the Stage 18D structural inventory to cover the retail assetType values
observed in retained MP/Zombies zones, removes the old 128-notify research cap, and
records the full-quaternion branch explicitly.

A zone is count-closed only when the number of structurally accepted XAnimParts
records equals the raw XAsset-list XANIMPARTS count. Partial zones remain labeled as
partial; their negative branch result must not be promoted to a whole-zone proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

FOLLOW = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
SHIFT = 29
MASK = (1 << 29) - 1
XANIM_SIZE = 104


def parse_front(data: bytes):
    blocks = list(struct.unpack_from("<8I", data, 8))
    pos = 40
    sc, sp, dc, dp, ac, ap = struct.unpack_from("<6I", data, pos)
    pos += 24
    if sc:
        ptrs = struct.unpack_from(f"<{sc}I", data, pos)
        pos += sc * 4
        for ptr in ptrs:
            if ptr == FOLLOW:
                pos = data.index(b"\0", pos) + 1
    if dc:
        ptrs = struct.unpack_from(f"<{dc}I", data, pos)
        pos += dc * 4
        for ptr in ptrs:
            if ptr == FOLLOW:
                pos = data.index(b"\0", pos) + 1
    asset_array = pos
    xanim_count = 0
    for i in range(ac):
        asset_type, _ = struct.unpack_from("<II", data, asset_array + i * 8)
        if asset_type == 4:
            xanim_count += 1
    return blocks, asset_array + ac * 8, ac, xanim_count


def valid_pointer(value: int, blocks: list[int], nonnull: bool = False) -> bool:
    if value == 0:
        return not nonnull
    if value == FOLLOW:
        return True
    if value == INSERT:
        return not nonnull
    encoded = (value - 1) & 0xFFFFFFFF
    block = encoded >> SHIFT
    offset = encoded & MASK
    return block < len(blocks) and offset < blocks[block]


def fixed(data: bytes, start: int):
    counts = struct.unpack_from("<6H", data, start + 4)
    random_short_count, index_count = struct.unpack_from("<II", data, start + 40)
    framerate, frequency, primed_length, loop_entry_time = struct.unpack_from("<4f", data, start + 48)
    ptrs = struct.unpack_from("<10I", data, start + 64)
    return {
        "namePtr": struct.unpack_from("<I", data, start)[0],
        "counts": counts,
        "numframes": counts[5],
        "flags": list(data[start + 16:start + 20]),
        "boneCount": list(data[start + 24:start + 34]),
        "notifyCount": data[start + 34],
        "assetType": data[start + 35],
        "isDefault": data[start + 36],
        "pad": data[start + 37:start + 40],
        "randomShortCount": random_short_count,
        "indexCount": index_count,
        "framerate": framerate,
        "frequency": frequency,
        "primedLength": primed_length,
        "loopEntryTime": loop_entry_time,
        "ptrs": ptrs,
    }


def valid_fixed(data: bytes, start: int, rec: dict, blocks: list[int]) -> bool:
    name_ptr = rec["namePtr"]
    if name_ptr == 0 or name_ptr == INSERT:
        return False
    if name_ptr != FOLLOW and not valid_pointer(name_ptr, blocks, True):
        return False
    if any(v not in (0, 1) for v in rec["flags"]):
        return False
    if rec["isDefault"] not in (0, 1) or rec["pad"] != b"\0\0\0":
        return False
    # Values 1,2,6,7 are directly observed on retained retail XAnimParts.
    if rec["assetType"] not in (1, 2, 6, 7):
        return False
    if rec["numframes"] > 8192:
        return False
    if rec["framerate"] not in (24.0, 30.0):
        return False
    if rec["numframes"] > 0 and abs(rec["frequency"] - rec["framerate"] / rec["numframes"]) > 2e-6:
        return False
    if rec["randomShortCount"] > 2_000_000 or rec["indexCount"] > 2_000_000:
        return False
    if any(not math.isfinite(v) or abs(v) > 100000 for v in (
        rec["frequency"], rec["primedLength"], rec["loopEntryTime"]
    )):
        return False
    if any(not valid_pointer(v, blocks) for v in rec["ptrs"]):
        return False
    if name_ptr == FOLLOW:
        end = data.find(b"\0", start + XANIM_SIZE, min(len(data), start + XANIM_SIZE + 161))
        if end < 0 or end == start + XANIM_SIZE:
            return False
        try:
            name = data[start + XANIM_SIZE:end].decode("ascii")
        except UnicodeDecodeError:
            return False
        if not re.fullmatch(r"[A-Za-z0-9_./+\-]{2,160}", name):
            return False
    return True


def parse_trans(data: bytes, pos: int, numframes: int):
    start = pos
    size = struct.unpack_from("<H", data, pos)[0]
    small = data[pos + 2]
    if small not in (0, 1):
        raise ValueError("bad smallTrans")
    if size == 0:
        return {"mode": "constant", "size": 0, "at": start, "bytes": 16}, pos + 16
    count = size + 1
    unit = 1 if numframes < 256 else 2
    frames_ptr = struct.unpack_from("<I", data, pos + 28)[0]
    pos += 32 + count * unit
    if frames_ptr == FOLLOW:
        pos += count * (3 if small else 6)
    return {"mode": "keyed", "size": size, "at": start, "bytes": pos - start}, pos


def parse_quat2(data: bytes, pos: int, numframes: int):
    start = pos
    size = struct.unpack_from("<H", data, pos)[0]
    if size == 0:
        return {"mode": "constant", "size": 0, "at": start, "bytes": 8}, pos + 8
    count = size + 1
    unit = 1 if numframes < 256 else 2
    frames_ptr = struct.unpack_from("<I", data, pos + 4)[0]
    pos += 8 + count * unit
    if frames_ptr == FOLLOW:
        pos += count * 4
    return {"mode": "keyed", "size": size, "at": start, "bytes": pos - start}, pos


def parse_quat(data: bytes, pos: int, numframes: int):
    start = pos
    size = struct.unpack_from("<H", data, pos)[0]
    if size == 0:
        return {
            "mode": "constant",
            "size": 0,
            "at": start,
            "bytes": 12,
            "rawInt16": list(struct.unpack_from("<4h", data, pos + 4)),
        }, pos + 12
    count = size + 1
    unit = 1 if numframes < 256 else 2
    frames_ptr = struct.unpack_from("<I", data, pos + 4)[0]
    pos += 8 + count * unit
    if frames_ptr == FOLLOW:
        pos += count * 8
    return {"mode": "keyed", "size": size, "at": start, "bytes": pos - start}, pos


def walk(data: bytes, start: int, rec: dict):
    pos = start + XANIM_SIZE
    name = None
    if rec["namePtr"] == FOLLOW:
        end = data.find(b"\0", pos, pos + 256)
        if end < 0:
            raise ValueError("unterminated name")
        name = data[pos:end].decode("ascii")
        pos = end + 1
    ptrs = rec["ptrs"]
    if ptrs[0] == FOLLOW:
        pos += rec["boneCount"][9] * 2
    if ptrs[8] == FOLLOW:
        pos += rec["notifyCount"] * 8
    delta = {"trans": None, "quat2": None, "quat": None}
    if ptrs[9] == FOLLOW:
        tr, q2, q = struct.unpack_from("<3I", data, pos)
        pos += 12
        if tr == FOLLOW:
            delta["trans"], pos = parse_trans(data, pos, rec["numframes"])
        if q2 == FOLLOW:
            delta["quat2"], pos = parse_quat2(data, pos, rec["numframes"])
        if q == FOLLOW:
            delta["quat"], pos = parse_quat(data, pos, rec["numframes"])
    arrays = [
        (rec["counts"][0], 1, ptrs[1]),
        (rec["counts"][1], 2, ptrs[2]),
        (rec["counts"][2], 4, ptrs[3]),
        (rec["randomShortCount"], 2, ptrs[4]),
        (rec["counts"][3], 1, ptrs[5]),
        (rec["counts"][4], 4, ptrs[6]),
        (rec["indexCount"], 1 if rec["numframes"] < 256 else 2, ptrs[7]),
    ]
    for count, unit, ptr in arrays:
        if ptr == FOLLOW:
            pos += count * unit
    if pos > len(data):
        raise ValueError("serialized XAnim walk exceeds stream")
    return pos, name, delta


def census(path: Path):
    data = path.read_bytes()
    blocks, body_start, asset_count, expected = parse_front(data)
    starts = set()
    records = []
    for framerate in (24.0, 30.0):
        pattern = struct.pack("<f", framerate)
        search = body_start + 48
        while True:
            hit = data.find(pattern, search)
            if hit < 0:
                break
            search = hit + 1
            start = hit - 48
            if start < body_start or start in starts or start + XANIM_SIZE > len(data):
                continue
            rec = fixed(data, start)
            if not valid_fixed(data, start, rec, blocks):
                continue
            try:
                end, name, delta = walk(data, start, rec)
            except Exception:
                continue
            starts.add(start)
            records.append({
                "start": start,
                "end": end,
                "nameKind": "inline" if rec["namePtr"] == FOLLOW else "packed",
                "name": name,
                "numframes": rec["numframes"],
                "flags": rec["flags"],
                "assetType": rec["assetType"],
                "delta": delta,
                "fixedSha256": hashlib.sha256(data[start:start + XANIM_SIZE]).hexdigest(),
            })
    records.sort(key=lambda x: x["start"])
    branch = {
        "transKeyed": 0, "transConstant": 0,
        "quat2Keyed": 0, "quat2Constant": 0,
        "quatKeyed": 0, "quatConstant": 0,
    }
    constant_full = []
    dynamic_full = []
    for record in records:
        for key, prefix in (("trans", "trans"), ("quat2", "quat2"), ("quat", "quat")):
            track = record["delta"][key]
            if not track:
                continue
            branch[prefix + ("Constant" if track["mode"] == "constant" else "Keyed")] += 1
            if key == "quat":
                item = {
                    "start": record["start"], "name": record["name"],
                    "nameKind": record["nameKind"], "numframes": record["numframes"],
                    "flags": record["flags"], "track": track,
                    "fixedSha256": record["fixedSha256"],
                }
                (constant_full if track["mode"] == "constant" else dynamic_full).append(item)
    overlaps = sum(a["end"] > b["start"] for a, b in zip(records, records[1:]))
    return {
        "file": path.name,
        "expandedBytes": len(data),
        "expandedSha256": hashlib.sha256(data).hexdigest(),
        "xassetCount": asset_count,
        "expectedXAnimCount": expected,
        "structuralRecordCount": len(records),
        "countClosesExactly": len(records) == expected,
        "inlineNames": sum(r["nameKind"] == "inline" for r in records),
        "packedNames": sum(r["nameKind"] == "packed" for r in records),
        "overlaps": overlaps,
        "branches": branch,
        "constantFullQuat": constant_full,
        "dynamicFullQuatCount": len(dynamic_full),
        "dynamicFullQuatExamples": dynamic_full[:20],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    zones = [census(path) for path in args.expanded]
    exact = [z for z in zones if z["countClosesExactly"]]
    keys = ("transKeyed", "transConstant", "quat2Keyed", "quat2Constant", "quatKeyed", "quatConstant")
    result = {
        "format": "t6-retail-xanim-delta-branch-census-v1",
        "zones": zones,
        "summary": {
            "zonesScanned": len(zones),
            "zonesCountClosed": len(exact),
            "expectedXAnimRecordsAllZones": sum(z["expectedXAnimCount"] for z in zones),
            "structuralRecordsIdentifiedAllZones": sum(z["structuralRecordCount"] for z in zones),
            "exactCountXAnimRecords": sum(z["expectedXAnimCount"] for z in exact),
            "exactCountBranchTotals": {k: sum(z["branches"][k] for z in exact) for k in keys},
            "constantFullQuatObservedInExactCountZones": sum(z["branches"]["quatConstant"] for z in exact),
            "dynamicFullQuatObservedAllIdentifiedRecords": sum(z["branches"]["quatKeyed"] for z in zones),
        },
        "proofBoundary": (
            "Negative constant-full-quat evidence is whole-zone proof only for zones whose "
            "countClosesExactly is true. Partial zones are retained as additional observations, "
            "not promoted to exhaustive absence claims."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
