#!/usr/bin/env python3
"""General T6 PC32 serialized XAnimParts source-byte walker.

Walk one T6 XAnimParts asset from a caller-provided fixed-record source offset.
The walk follows the pinned T6 XAnimParts ZoneCode reorder contract and keeps
native-memory alignment separate from serialized-source consumption.

Retail-proven source rules encoded here:
- XAnimParts fixed record: 104 bytes
- XAnimNotifyInfo: 8 source bytes
- XAnimDeltaPart: 12 source bytes
- names count is boneCount[PART_TYPE_ALL] (boneCount[9]), not sum(boneCount)
- dynamic frame indices are u8 when numframes < 256, otherwise u16
- dynamic index arrays begin at their inline-array member offset; no nominal
  native struct tail/padding is inserted before the variable-length array.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
XANIM_FIXED = 104
NOTIFY_SIZE = 8
DELTA_PART_SIZE = 12


def ptr_kind(v: int) -> dict:
    v &= 0xFFFFFFFF
    if v == 0:
        return {"raw": v, "rawHex": "0x00000000", "kind": "null"}
    if v == FOLLOWING:
        return {"raw": v, "rawHex": "0xFFFFFFFF", "kind": "following"}
    if v == INSERT:
        return {"raw": v, "rawHex": "0xFFFFFFFE", "kind": "insert"}
    x = (v - 1) & 0xFFFFFFFF
    return {
        "raw": v,
        "rawHex": f"0x{v:08X}",
        "kind": "packed",
        "block": x >> 29,
        "offset": x & 0x1FFFFFFF,
    }


def is_inline(v: int) -> bool:
    return v in (FOLLOWING, INSERT)


class WalkError(RuntimeError):
    pass


class XAnimWalker:
    def __init__(self, data: bytes, start: int):
        self.data = data
        self.start = start
        self.pos = start
        self.sections: list[dict] = []
        self.dependencies: list[dict] = []
        self.blockers: list[dict] = []

    def need_at(self, pos: int, n: int, label: str):
        if pos < 0 or n < 0 or pos + n > len(self.data):
            raise WalkError(f"{label}: need {n} bytes at {pos}, file={len(self.data)}")

    def sha(self, a: int, b: int) -> str:
        return hashlib.sha256(self.data[a:b]).hexdigest()

    def take(self, n: int, label: str, **meta) -> tuple[int, int]:
        self.need_at(self.pos, n, label)
        a = self.pos
        self.pos += n
        rec = {
            "name": label,
            "start": a,
            "end": self.pos,
            "bytes": n,
            "sha256": self.sha(a, self.pos),
        }
        rec.update(meta)
        self.sections.append(rec)
        return a, self.pos

    def cstring(self, label: str) -> str:
        try:
            end = self.data.index(b"\0", self.pos)
        except ValueError as exc:
            raise WalkError(f"{label}: unterminated string at {self.pos}") from exc
        a = self.pos
        self.pos = end + 1
        text = self.data[a:end].decode("latin1", "replace")
        self.sections.append({
            "name": label,
            "start": a,
            "end": self.pos,
            "bytes": self.pos - a,
            "text": text,
            "sha256": self.sha(a, self.pos),
        })
        return text

    def u16(self, pos: int) -> int:
        return struct.unpack_from("<H", self.data, pos)[0]

    def u32(self, pos: int) -> int:
        return struct.unpack_from("<I", self.data, pos)[0]

    def f32(self, pos: int) -> float:
        return struct.unpack_from("<f", self.data, pos)[0]

    def walk_pointer_array(self, ptr: int, count: int, elem_bytes: int, label: str):
        if count == 0 or ptr == 0:
            return
        if is_inline(ptr):
            self.take(count * elem_bytes, label, count=count, recordBytes=elem_bytes)
        else:
            self.dependencies.append({
                "field": label,
                "pointer": ptr_kind(ptr),
                "count": count,
                "recordBytes": elem_bytes,
                "serializedSourceBytes": 0,
            })

    def walk_delta_trans(self, label: str, numframes: int) -> dict:
        a = self.pos
        self.need_at(a, 4, label)
        size = self.u16(a)
        small = self.data[a + 2]
        if small not in (0, 1):
            raise WalkError(f"{label}: invalid smallTrans {small}")
        if size == 0:
            # Retail-proven on zm_prison: size:u16 + small:u8 + pad:u8 + frame0 vec3 = 16 source bytes.
            self.take(16, label, size=0, smallTrans=bool(small), frameMode="constant")
            return {"size": 0, "smallTrans": bool(small), "frameMode": "constant"}

        index_width = 1 if numframes < 256 else 2
        count = size + 1
        # Source prefix ends immediately before flexible indices:
        # outer(size,small,pad)=4 + frames(mins,sizevec,framesPtr)=28.
        prefix = 32
        self.need_at(a, prefix, label)
        frames_ptr = self.u32(a + 28)
        if frames_ptr == 0:
            raise WalkError(f"{label}: size={size} but frames pointer is null")
        if not is_inline(frames_ptr):
            self.blockers.append({
                "kind": "packed_delta_trans_frames_not_source_owned",
                "field": label,
                "pointer": ptr_kind(frames_ptr),
            })
            # Packed frames mean this source span contains only the native active
            # header variant. This branch needs a retail oracle before claiming a
            # source stride, so fail closed.
            raise WalkError(f"{label}: packed dynamic frames not retail-closed")

        idx_bytes = count * index_width
        frame_bytes = 3 if small else 6
        total = prefix + idx_bytes + count * frame_bytes
        self.take(total, label,
                  size=size, smallTrans=bool(small), frameMode="dynamic",
                  indexWidthBytes=index_width, indexCount=count,
                  indicesStart=a + prefix,
                  framesStart=a + prefix + idx_bytes,
                  frameCount=count, frameRecordBytes=frame_bytes,
                  framesPointer=ptr_kind(frames_ptr))
        return {
            "size": size,
            "smallTrans": bool(small),
            "frameMode": "dynamic",
            "indexWidthBytes": index_width,
            "indexCount": count,
            "frameCount": count,
            "frameRecordBytes": frame_bytes,
        }

    def walk_delta_quat2(self, label: str, numframes: int) -> dict:
        a = self.pos
        self.need_at(a, 4, label)
        size = self.u16(a)
        if size == 0:
            # Retail-proven on zm_prison: size:u16 + pad:u16 + XQuat2 frame0 = 8 source bytes.
            self.take(8, label, size=0, frameMode="constant")
            return {"size": 0, "frameMode": "constant"}

        index_width = 1 if numframes < 256 else 2
        count = size + 1
        prefix = 8  # size/pad + frames pointer
        frames_ptr = self.u32(a + 4)
        if not is_inline(frames_ptr):
            raise WalkError(f"{label}: dynamic frames pointer is not inline: {ptr_kind(frames_ptr)}")
        idx_bytes = count * index_width
        total = prefix + idx_bytes + count * 4
        self.take(total, label,
                  size=size, frameMode="dynamic",
                  indexWidthBytes=index_width, indexCount=count,
                  indicesStart=a + prefix,
                  framesStart=a + prefix + idx_bytes,
                  frameCount=count, frameRecordBytes=4,
                  framesPointer=ptr_kind(frames_ptr))
        return {
            "size": size, "frameMode": "dynamic",
            "indexWidthBytes": index_width, "indexCount": count,
            "frameCount": count, "frameRecordBytes": 4,
        }

    def walk_delta_quat(self, label: str, numframes: int) -> dict:
        a = self.pos
        self.need_at(a, 4, label)
        size = self.u16(a)
        if size == 0:
            # Struct-derived only: no constant full-quat retail fixture found yet.
            # size:u16 + pad:u16 + XQuat frame0 (4 * int16) = 12 source bytes.
            self.take(12, label, size=0, frameMode="constant")
            return {"size": 0, "frameMode": "constant"}

        index_width = 1 if numframes < 256 else 2
        count = size + 1
        prefix = 8
        frames_ptr = self.u32(a + 4)
        if not is_inline(frames_ptr):
            raise WalkError(f"{label}: dynamic frames pointer is not inline: {ptr_kind(frames_ptr)}")
        idx_bytes = count * index_width
        total = prefix + idx_bytes + count * 8
        self.take(total, label,
                  size=size, frameMode="dynamic",
                  indexWidthBytes=index_width, indexCount=count,
                  indicesStart=a + prefix,
                  framesStart=a + prefix + idx_bytes,
                  frameCount=count, frameRecordBytes=8,
                  framesPointer=ptr_kind(frames_ptr))
        return {
            "size": size, "frameMode": "dynamic",
            "indexWidthBytes": index_width, "indexCount": count,
            "frameCount": count, "frameRecordBytes": 8,
        }

    def walk(self) -> dict:
        base = self.start
        self.need_at(base, XANIM_FIXED, "XAnimParts.fixed")

        name_ptr = self.u32(base + 0)
        data_byte_count = self.u16(base + 4)
        data_short_count = self.u16(base + 6)
        data_int_count = self.u16(base + 8)
        random_byte_count = self.u16(base + 10)
        random_int_count = self.u16(base + 12)
        numframes = self.u16(base + 14)
        b_loop, b_delta, b_delta3d, b_lh_grip = [bool(x) for x in self.data[base + 16:base + 20]]
        streamed_file_size = self.u32(base + 20)
        bone_count = list(self.data[base + 24:base + 34])
        notify_count = self.data[base + 34]
        asset_type = self.data[base + 35]
        is_default = bool(self.data[base + 36])
        random_short_count = self.u32(base + 40)
        index_count = self.u32(base + 44)
        framerate, frequency, primed_length, loop_entry_time = struct.unpack_from("<4f", self.data, base + 48)
        for label, value in (("framerate", framerate), ("frequency", frequency), ("primedLength", primed_length), ("loopEntryTime", loop_entry_time)):
            if not math.isfinite(value):
                raise WalkError(f"{label} is non-finite")

        names_ptr = self.u32(base + 64)
        data_byte_ptr = self.u32(base + 68)
        data_short_ptr = self.u32(base + 72)
        data_int_ptr = self.u32(base + 76)
        random_short_ptr = self.u32(base + 80)
        random_byte_ptr = self.u32(base + 84)
        random_int_ptr = self.u32(base + 88)
        indices_ptr = self.u32(base + 92)
        notify_ptr = self.u32(base + 96)
        delta_ptr = self.u32(base + 100)

        self.take(XANIM_FIXED, "XAnimParts.fixed")

        name = None
        if is_inline(name_ptr):
            name = self.cstring("XAnimParts.name")
        elif name_ptr:
            self.dependencies.append({"field": "XAnimParts.name", "pointer": ptr_kind(name_ptr)})

        # The T6 contract explicitly counts names by PART_TYPE_ALL only.
        names_count = bone_count[9]
        self.walk_pointer_array(names_ptr, names_count, 2, "XAnimParts.names")

        if notify_count and is_inline(notify_ptr):
            a, _ = self.take(notify_count * NOTIFY_SIZE, "XAnimParts.notify",
                             count=notify_count, recordBytes=NOTIFY_SIZE)
            decoded = []
            for i in range(notify_count):
                b = a + i * NOTIFY_SIZE
                decoded.append({"scriptString": self.u16(b), "time": self.f32(b + 4)})
            self.sections[-1]["decoded"] = decoded
        elif notify_count and notify_ptr:
            self.dependencies.append({
                "field": "XAnimParts.notify", "pointer": ptr_kind(notify_ptr),
                "count": notify_count, "recordBytes": NOTIFY_SIZE,
            })

        delta = None
        if is_inline(delta_ptr):
            a, _ = self.take(DELTA_PART_SIZE, "XAnimParts.deltaPart.fixed")
            trans_ptr, quat2_ptr, quat_ptr = struct.unpack_from("<III", self.data, a)
            self.sections[-1]["pointers"] = [ptr_kind(trans_ptr), ptr_kind(quat2_ptr), ptr_kind(quat_ptr)]
            delta = {"trans": None, "quat2": None, "quat": None}
            if is_inline(trans_ptr):
                delta["trans"] = self.walk_delta_trans("XAnimParts.deltaPart.trans", numframes)
            elif trans_ptr:
                self.dependencies.append({"field": "XAnimParts.deltaPart.trans", "pointer": ptr_kind(trans_ptr)})
            if is_inline(quat2_ptr):
                delta["quat2"] = self.walk_delta_quat2("XAnimParts.deltaPart.quat2", numframes)
            elif quat2_ptr:
                self.dependencies.append({"field": "XAnimParts.deltaPart.quat2", "pointer": ptr_kind(quat2_ptr)})
            if is_inline(quat_ptr):
                delta["quat"] = self.walk_delta_quat("XAnimParts.deltaPart.quat", numframes)
            elif quat_ptr:
                self.dependencies.append({"field": "XAnimParts.deltaPart.quat", "pointer": ptr_kind(quat_ptr)})
        elif delta_ptr:
            self.dependencies.append({"field": "XAnimParts.deltaPart", "pointer": ptr_kind(delta_ptr)})

        # Reordered top-level scalar arrays.
        self.walk_pointer_array(data_byte_ptr, data_byte_count, 1, "XAnimParts.dataByte")
        self.walk_pointer_array(data_short_ptr, data_short_count, 2, "XAnimParts.dataShort")
        self.walk_pointer_array(data_int_ptr, data_int_count, 4, "XAnimParts.dataInt")
        self.walk_pointer_array(random_short_ptr, random_short_count, 2, "XAnimParts.randomDataShort")
        self.walk_pointer_array(random_byte_ptr, random_byte_count, 1, "XAnimParts.randomDataByte")
        self.walk_pointer_array(random_int_ptr, random_int_count, 4, "XAnimParts.randomDataInt")
        index_width = 1 if numframes < 256 else 2
        self.walk_pointer_array(indices_ptr, index_count, index_width, "XAnimParts.indices")

        end = self.pos
        return {
            "format": "t6-xanimparts-serialized-walk-v1",
            "assetFixedStart": self.start,
            "assetSerializedEnd": end,
            "assetSerializedBytes": end - self.start,
            "assetSerializedSha256": self.sha(self.start, end),
            "name": name,
            "header": {
                "dataByteCount": data_byte_count,
                "dataShortCount": data_short_count,
                "dataIntCount": data_int_count,
                "randomDataByteCount": random_byte_count,
                "randomDataIntCount": random_int_count,
                "randomDataShortCount": random_short_count,
                "numframes": numframes,
                "bLoop": b_loop,
                "bDelta": b_delta,
                "bDelta3D": b_delta3d,
                "bLeftHandGripIK": b_lh_grip,
                "streamedFileSize": streamed_file_size,
                "boneCount": bone_count,
                "namesCount": names_count,
                "notifyCount": notify_count,
                "assetType": asset_type,
                "isDefault": is_default,
                "indexCount": index_count,
                "framerate": framerate,
                "frequency": frequency,
                "primedLength": primed_length,
                "loopEntryTime": loop_entry_time,
                "pointers": {
                    "name": ptr_kind(name_ptr), "names": ptr_kind(names_ptr),
                    "dataByte": ptr_kind(data_byte_ptr), "dataShort": ptr_kind(data_short_ptr),
                    "dataInt": ptr_kind(data_int_ptr), "randomDataShort": ptr_kind(random_short_ptr),
                    "randomDataByte": ptr_kind(random_byte_ptr), "randomDataInt": ptr_kind(random_int_ptr),
                    "indices": ptr_kind(indices_ptr), "notify": ptr_kind(notify_ptr),
                    "deltaPart": ptr_kind(delta_ptr),
                },
            },
            "delta": delta,
            "sections": self.sections,
            "dependencies": self.dependencies,
            "blockers": self.blockers,
            "sourceRules": {
                "xanimPartsFixedBytes": 104,
                "namesCountField": "boneCount[PART_TYPE_ALL] / boneCount[9]",
                "indexWidthRule": "numframes < 256 => uint8 else uint16",
                "nativeAlignmentAddsSerializedPadding": False,
                "flexibleDynamicArraysExtendFromInlineMemberOffset": True,
                "constantDeltaTrans16BytesRetailProven": True,
                "constantDeltaQuat2EightBytesRetailProven": True,
                "constantDeltaFullQuat12BytesRetailProven": False,
            },
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--asset-start", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--expect-end", type=lambda s: int(s, 0))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    result = XAnimWalker(data, args.asset_start).walk()
    result["expandedBytes"] = len(data)
    result["expandedSha256"] = hashlib.sha256(data).hexdigest()
    if args.expect_end is not None:
        result["expectedEnd"] = args.expect_end
        result["expectedEndMatches"] = result["assetSerializedEnd"] == args.expect_end
        if not result["expectedEndMatches"]:
            raise SystemExit(f"ended {result['assetSerializedEnd']}, expected {args.expect_end}")
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
