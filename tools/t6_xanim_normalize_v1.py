#!/usr/bin/env python3
"""Normalize T6 XAnimParts into named bone tracks with exact pool accounting.

This layer sits above t6_xanim_serialized_walker.py. It reproduces the pinned
OpenAssetTools FlatXAnimReader pool-consumption rules, resolves ScriptString
bone/notify names from the retail zone, and fails if any consumed flat-data pool
is not exhausted exactly.

Compressed quaternion values are retained losslessly. Translation tracks also
include the engine's decoded quantization step (raw size / 255 or / 65535), so
individual keyed translations can be reconstructed as mins + quantized*step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from t6_xanim_serialized_walker import XAnimWalker

QUAT_TYPES = ["NO_QUAT", "HALF_QUAT", "FULL_QUAT", "HALF_QUAT_NO_SIZE", "FULL_QUAT_NO_SIZE"]
TRANS_TYPES = ["SMALL_TRANS", "FULL_TRANS", "TRANS_NO_SIZE", "NO_TRANS"]
HALF_TRANS_SIZE_SCALE = 0.003921568859368563  # decompiled T6 literal ~= 1/255
FULL_TRANS_SIZE_SCALE = 0.00001525902189314365  # decompiled T6 literal ~= 1/65535


class NormalizeError(RuntimeError):
    pass


def parse_scriptstrings(data: bytes) -> tuple[list[str | None], int]:
    # XAssetList begins immediately after the 40-byte XFile memory header.
    count = struct.unpack_from("<I", data, 40)[0]
    ptr = struct.unpack_from("<I", data, 44)[0]
    if count == 0:
        return [], 64
    if ptr != 0xFFFFFFFF:
        raise NormalizeError(f"script string table is not inline: 0x{ptr:08X}")
    p = 64 + count * 4
    out: list[str | None] = [None]
    for _ in range(1, count):
        end = data.index(b"\0", p)
        out.append(data[p:end].decode("latin1", "replace"))
        p = end + 1
    if len(out) != count:
        raise NormalizeError(f"script string count mismatch {len(out)} != {count}")
    return out, p


def section_by_name(walk: dict, name: str) -> dict | None:
    for s in walk["sections"]:
        if s["name"] == name:
            return s
    return None


def read_pool(data: bytes, section: dict | None, kind: str) -> list[int]:
    if section is None:
        return []
    raw = data[section["start"]:section["end"]]
    if kind == "u8":
        return list(raw)
    if kind == "i16":
        return list(struct.unpack("<" + "h" * (len(raw) // 2), raw))
    if kind == "u16":
        return list(struct.unpack("<" + "H" * (len(raw) // 2), raw))
    if kind == "i32":
        return list(struct.unpack("<" + "i" * (len(raw) // 4), raw))
    raise ValueError(kind)


def int_bits_to_float(v: int) -> float:
    return struct.unpack("<f", struct.pack("<i", v))[0]


class PoolCursor:
    def __init__(self, *, data_byte, data_short, data_int, random_byte, random_short, indices):
        self.pools = {
            "dataByte": data_byte,
            "dataShort": data_short,
            "dataInt": data_int,
            "randomDataByte": random_byte,
            "randomDataShort": random_short,
            "indices": indices,
        }
        self.pos = {k: 0 for k in self.pools}

    def remaining(self, name: str) -> int:
        return len(self.pools[name]) - self.pos[name]

    def pop(self, name: str) -> int:
        if self.remaining(name) < 1:
            raise NormalizeError(f"exhausted {name}")
        i = self.pos[name]
        self.pos[name] += 1
        return self.pools[name][i]

    def read(self, name: str, n: int) -> list[int]:
        if self.remaining(name) < n:
            raise NormalizeError(f"exhausted {name}: need {n}, remaining {self.remaining(name)}")
        a = self.pos[name]
        self.pos[name] += n
        return self.pools[name][a:a+n]

    def skip(self, name: str, n: int):
        self.read(name, n)

    def float3(self) -> list[float]:
        return [int_bits_to_float(self.pop("dataInt")) for _ in range(3)]

    def packed_indices(self, stored_size: int, use_byte_indices: bool) -> tuple[list[int], dict]:
        count = stored_size + 1
        if use_byte_indices:
            return self.read("dataByte", count), {"sourcePool": "dataByte", "checkpointCount": 0}
        if stored_size >= 64:
            values = self.read("indices", count)
            checkpoint_count = ((count - 2) // 256) + 2
            checkpoints = self.read("dataShort", checkpoint_count)
            return [v & 0xFFFF for v in values], {
                "sourcePool": "indices",
                "checkpointCount": checkpoint_count,
                "checkpoints": [v & 0xFFFF for v in checkpoints],
            }
        values = self.read("dataShort", count)
        return [v & 0xFFFF for v in values], {"sourcePool": "dataShort", "checkpointCount": 0}

    def end_state(self) -> dict:
        return {
            k: {"count": len(v), "consumed": self.pos[k], "remaining": len(v)-self.pos[k]}
            for k, v in self.pools.items()
        }

    def assert_exhausted(self):
        rem = {k: self.remaining(k) for k in self.pools if self.remaining(k)}
        if rem:
            raise NormalizeError(f"flat pools not exhausted: {rem}")


def decode_delta(data: bytes, walk: dict) -> dict | None:
    delta = walk.get("delta")
    if not delta:
        return None
    numframes = walk["header"]["numframes"]
    use_byte = numframes < 256
    out: dict = {"trans": None, "quat2": None, "quat": None}
    for typ in ("trans", "quat2", "quat"):
        meta = delta.get(typ)
        if not meta:
            continue
        sec = section_by_name(walk, f"XAnimParts.deltaPart.{typ}")
        if sec is None:
            raise NormalizeError(f"missing delta section {typ}")
        a = sec["start"]
        if typ == "trans":
            size = meta["size"]
            if size == 0:
                out[typ] = {
                    "mode": "constant",
                    "value": list(struct.unpack_from("<3f", data, a + 4)),
                    "smallTrans": bool(meta["smallTrans"]),
                }
            else:
                count = size + 1
                idx_width = 1 if use_byte else 2
                idx_start = a + 32
                if idx_width == 1:
                    indices = list(data[idx_start:idx_start+count])
                else:
                    indices = list(struct.unpack_from("<" + "H"*count, data, idx_start))
                mins = list(struct.unpack_from("<3f", data, a + 4))
                raw_size = list(struct.unpack_from("<3f", data, a + 16))
                scale = HALF_TRANS_SIZE_SCALE if meta["smallTrans"] else FULL_TRANS_SIZE_SCALE
                step = [x * scale for x in raw_size]
                frames_start = idx_start + count*idx_width
                frames = []
                decoded = []
                if meta["smallTrans"]:
                    for i in range(count):
                        q = list(data[frames_start+i*3:frames_start+i*3+3])
                        frames.append(q)
                        decoded.append([mins[k] + q[k]*step[k] for k in range(3)])
                else:
                    for i in range(count):
                        q = list(struct.unpack_from("<3H", data, frames_start+i*6))
                        frames.append(q)
                        decoded.append([mins[k] + q[k]*step[k] for k in range(3)])
                out[typ] = {
                    "mode": "dynamic", "smallTrans": bool(meta["smallTrans"]),
                    "indices": indices, "mins": mins, "rawSize": raw_size,
                    "decodedStep": step, "quantizedFrames": frames,
                    "decodedFrames": decoded,
                }
        else:
            size = meta["size"]
            comps = 2 if typ == "quat2" else 4
            if size == 0:
                values = list(struct.unpack_from("<" + "h"*comps, data, a+4))
                out[typ] = {"mode": "constant", "rawInt16": values, "normalized": [v/32767.0 for v in values]}
            else:
                count = size + 1
                idx_width = 1 if use_byte else 2
                idx_start = a + 8
                if idx_width == 1:
                    indices = list(data[idx_start:idx_start+count])
                else:
                    indices = list(struct.unpack_from("<" + "H"*count, data, idx_start))
                fs = idx_start + count*idx_width
                frames = [list(struct.unpack_from("<" + "h"*comps, data, fs+i*comps*2)) for i in range(count)]
                out[typ] = {"mode": "dynamic", "indices": indices, "rawInt16Frames": frames,
                            "normalizedFrames": [[v/32767.0 for v in f] for f in frames]}
    return out


def normalize(data: bytes, start: int) -> dict:
    walk = XAnimWalker(data, start).walk()
    ss, script_end = parse_scriptstrings(data)
    h = walk["header"]
    bone_counts = h["boneCount"]
    bone_count = bone_counts[9]
    if sum(bone_counts[:5]) != bone_count:
        raise NormalizeError(f"quat category sum {sum(bone_counts[:5])} != PART_TYPE_ALL {bone_count}")
    if sum(bone_counts[5:9]) != bone_count:
        raise NormalizeError(f"trans category sum {sum(bone_counts[5:9])} != PART_TYPE_ALL {bone_count}")

    names_sec = section_by_name(walk, "XAnimParts.names")
    name_ids = [] if bone_count == 0 else list(struct.unpack_from("<" + "H"*bone_count, data, names_sec["start"]))
    names = []
    for sid in name_ids:
        if sid >= len(ss):
            raise NormalizeError(f"bone ScriptString {sid} outside table {len(ss)}")
        names.append(ss[sid])

    use_byte = h["numframes"] < 256
    pools = PoolCursor(
        data_byte=read_pool(data, section_by_name(walk, "XAnimParts.dataByte"), "u8"),
        data_short=read_pool(data, section_by_name(walk, "XAnimParts.dataShort"), "i16"),
        data_int=read_pool(data, section_by_name(walk, "XAnimParts.dataInt"), "i32"),
        random_byte=read_pool(data, section_by_name(walk, "XAnimParts.randomDataByte"), "u8"),
        random_short=read_pool(data, section_by_name(walk, "XAnimParts.randomDataShort"), "i16"),
        indices=(read_pool(data, section_by_name(walk, "XAnimParts.indices"), "u8") if use_byte
                 else read_pool(data, section_by_name(walk, "XAnimParts.indices"), "u16")),
    )

    tracks = [{"boneIndex": i, "scriptString": name_ids[i], "name": names[i], "quat": None, "trans": None} for i in range(bone_count)]
    bi = 0
    for qtype_i, qtype in enumerate(QUAT_TYPES):
        for _ in range(bone_counts[qtype_i]):
            tr = tracks[bi]
            if qtype == "NO_QUAT":
                tr["quat"] = {"type": qtype}
            elif qtype == "HALF_QUAT":
                stored = pools.pop("dataShort") & 0xFFFF
                indices, idxmeta = pools.packed_indices(stored, use_byte)
                frames = [pools.read("randomDataShort", 2) for _ in range(stored+1)]
                tr["quat"] = {"type": qtype, "storedSize": stored, "indices": indices, "indexStorage": idxmeta,
                              "rawInt16Frames": frames, "normalizedFrames": [[v/32767.0 for v in f] for f in frames]}
            elif qtype == "FULL_QUAT":
                stored = pools.pop("dataShort") & 0xFFFF
                indices, idxmeta = pools.packed_indices(stored, use_byte)
                frames = [pools.read("randomDataShort", 4) for _ in range(stored+1)]
                tr["quat"] = {"type": qtype, "storedSize": stored, "indices": indices, "indexStorage": idxmeta,
                              "rawInt16Frames": frames, "normalizedFrames": [[v/32767.0 for v in f] for f in frames]}
            elif qtype == "HALF_QUAT_NO_SIZE":
                frame = pools.read("dataShort", 2)
                tr["quat"] = {"type": qtype, "rawInt16Frames": [frame], "normalizedFrames": [[v/32767.0 for v in frame]]}
            elif qtype == "FULL_QUAT_NO_SIZE":
                frame = pools.read("dataShort", 4)
                tr["quat"] = {"type": qtype, "rawInt16Frames": [frame], "normalizedFrames": [[v/32767.0 for v in frame]]}
            bi += 1
    if bi != bone_count:
        raise NormalizeError(f"quat assignment ended at {bi}, expected {bone_count}")

    assigned = [False]*bone_count
    for tindex, ttype in enumerate(TRANS_TYPES):
        count = bone_counts[5+tindex]
        for _ in range(count):
            bone = pools.pop("dataByte")
            if bone >= bone_count or assigned[bone]:
                raise NormalizeError(f"invalid/duplicate trans bone index {bone}")
            assigned[bone] = True
            tr = tracks[bone]
            if ttype in ("SMALL_TRANS", "FULL_TRANS"):
                stored = pools.pop("dataShort") & 0xFFFF
                mins = pools.float3()
                raw_size = pools.float3()
                indices, idxmeta = pools.packed_indices(stored, use_byte)
                n = stored + 1
                small = ttype == "SMALL_TRANS"
                scale = HALF_TRANS_SIZE_SCALE if small else FULL_TRANS_SIZE_SCALE
                step = [x*scale for x in raw_size]
                if small:
                    qframes = [pools.read("randomDataByte", 3) for _ in range(n)]
                else:
                    qframes = [[v & 0xFFFF for v in pools.read("randomDataShort", 3)] for _ in range(n)]
                decoded = [[mins[k] + q[k]*step[k] for k in range(3)] for q in qframes]
                tr["trans"] = {"type": ttype, "storedSize": stored, "indices": indices, "indexStorage": idxmeta,
                               "mins": mins, "rawSize": raw_size, "decodedStep": step,
                               "quantizedFrames": qframes, "decodedFrames": decoded}
            elif ttype == "TRANS_NO_SIZE":
                tr["trans"] = {"type": ttype, "constant": pools.float3()}
            else:
                tr["trans"] = {"type": ttype}
    if not all(assigned):
        raise NormalizeError(f"unassigned translation tracks: {[i for i,x in enumerate(assigned) if not x]}")

    pool_state = pools.end_state()
    pools.assert_exhausted()

    notify_sec = section_by_name(walk, "XAnimParts.notify")
    notifies = []
    if notify_sec:
        for row in notify_sec.get("decoded", []):
            sid = row["scriptString"]
            notifies.append({"scriptString": sid, "name": ss[sid] if sid < len(ss) else None, "time": row["time"]})

    # randomDataInt is preserved by the source walker but is not part of the T6
    # FlatXAnimReader's bone-track cursor. Surface it explicitly if it appears.
    rdi = section_by_name(walk, "XAnimParts.randomDataInt")
    random_int_raw = [] if rdi is None else read_pool(data, rdi, "i32")

    return {
        "format": "t6-xanim-normalized-v1",
        "name": walk["name"],
        "assetFixedStart": start,
        "assetSerializedEnd": walk["assetSerializedEnd"],
        "assetSerializedSha256": walk["assetSerializedSha256"],
        "header": h,
        "scriptStringTable": {"count": len(ss), "serializedEnd": script_end},
        "boneTracks": tracks,
        "notifies": notifies,
        "delta": decode_delta(data, walk),
        "flatPoolExhaustion": pool_state,
        "allFlatPoolsExhausted": True,
        "randomDataIntRaw": random_int_raw,
        "walkerDependencies": walk["dependencies"],
        "walkerBlockers": walk["blockers"],
        "decodeRules": {
            "boneNames": "ScriptString IDs from XAnimParts.names; count = boneCount[9]",
            "quatTrackOrder": QUAT_TYPES,
            "transTrackOrder": TRANS_TYPES,
            "longIndexThreshold": "storedSize >= 64 (frameCount >= 65) moves 16-bit indices to top-level indices pool",
            "longIndexCheckpoints": "dataShort stores first, every 256th, and final index",
            "smallTranslationStepScale": HALF_TRANS_SIZE_SCALE,
            "fullTranslationStepScale": FULL_TRANS_SIZE_SCALE,
            "translationDecode": "mins + quantizedFrame * (rawSize * scale)",
            "quatNormalizedView": "raw int16 / 32767; raw int16 values remain authoritative",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--asset-start", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    result = normalize(data, args.asset_start)
    result["expandedSha256"] = hashlib.sha256(data).hexdigest()
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
