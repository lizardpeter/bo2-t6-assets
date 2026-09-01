#!/usr/bin/env python3
"""Source-closed T6 compiled XAnim v19 non-empty delta subsection codec.

Authority: pinned OpenAssetTools 7d027e8f89118196713e955b0e11f8404149c54d:
- ObjWriting/XAnim/CompiledXAnimWriter.cpp
- ObjLoading/XAnim/CompiledXAnimLoader.cpp
- ObjCommon/XAnim/BinaryXAnimCommon.h

This is the *compiled interchange* delta representation, not the raw T6
XAnimDeltaPart zone layout. It consumes lossless fields from
`t6-xanim-normalized-v1` and implements exactly the OAT v19 delta grammar:

  delta quaternion count
    0: absent
    1: omitted-component compressed constant
   >1: optional byte/u16 indices + omitted-component frames
  delta translation count
    0: absent
    1: constant 3xf32
   >1: optional byte/u16 indices + smallTrans + mins + rawSize + raw frames

Indices are omitted only for sequential full coverage of numframes+1 keys.
Translation rawSize/quantizedFrames are preserved directly; no float
re-quantization is performed. Quaternion compression is round-trip checked as a
rotation and fails closed if the omitted-component form cannot represent the
input track within the stated tolerance.
"""
from __future__ import annotations

import math
import struct

from t6_xanim_delta_gltf_semantics_v2 import DeltaGltfError, timing_info

RADIUS_SQ = 0x3FFF0001  # 32767^2
HALF_TRANS_SIZE_SCALE = 0.003921568859368563
FULL_TRANS_SIZE_SCALE = 0.00001525902189314365
ROTATION_DOT_TOLERANCE = 2e-7


class CompiledDeltaError(RuntimeError):
    pass


def _i16(v) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < -32768 or v > 32767:
        raise CompiledDeltaError(f"invalid int16 {v!r}")
    return v


def _u16(v) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0 or v > 65535:
        raise CompiledDeltaError(f"invalid uint16 {v!r}")
    return v


def _indices(track: dict, header: dict, label: str) -> tuple[list[int], dict]:
    raw = track.get("indices", [])
    if not isinstance(raw, list) or any(isinstance(v, bool) or not isinstance(v, int) for v in raw):
        raise CompiledDeltaError(f"{label}: indices must be JSON integers")
    inds = [_u16(v) for v in raw]
    try:
        timing = timing_info(header)
    except DeltaGltfError as exc:
        raise CompiledDeltaError(str(exc)) from exc
    n = int(timing["numframes"])
    if n <= 0:
        raise CompiledDeltaError(f"{label}: dynamic track requires numframes > 0")
    if len(inds) < 2 or inds[0] != 0 or inds[-1] != n:
        raise CompiledDeltaError(f"{label}: native dynamic indices must span 0..{n}: {inds}")
    if any(b <= a for a, b in zip(inds, inds[1:])):
        raise CompiledDeltaError(f"{label}: indices not strictly increasing: {inds}")
    return inds, timing


def _write_indices(out: bytearray, inds: list[int], num_loop_frames: int, use_byte: bool) -> None:
    if len(inds) >= num_loop_frames:
        if inds != list(range(num_loop_frames)):
            raise CompiledDeltaError("full-coverage indices are not sequential")
        return
    if use_byte:
        if any(v > 255 for v in inds):
            raise CompiledDeltaError("byte index out of range")
        out.extend(bytes(inds))
    else:
        out.extend(struct.pack("<" + "H" * len(inds), *inds))


def _read_indices(data: bytes, pos: int, count: int, num_loop_frames: int, use_byte: bool):
    if count >= num_loop_frames:
        return list(range(count)), pos
    if use_byte:
        end = pos + count
        if end > len(data):
            raise CompiledDeltaError("truncated byte indices")
        return list(data[pos:end]), end
    end = pos + count * 2
    if end > len(data):
        raise CompiledDeltaError("truncated ushort indices")
    return list(struct.unpack_from("<" + "H" * count, data, pos)), end


def _omitted_component(stored: list[int]) -> int:
    temp = RADIUS_SQ - sum(v * v for v in stored)
    if temp <= 0:
        return 0
    return int(math.floor(math.sqrt(float(temp)) + 0.5))


def _quat_dot(a: list[int], b: list[int]) -> int:
    return sum(x * y for x, y in zip(a, b))


def _rotation_equivalent(a: list[int], b: list[int]) -> bool:
    na = math.sqrt(sum(float(x) * x for x in a))
    nb = math.sqrt(sum(float(x) * x for x in b))
    if na <= 0 or nb <= 0:
        return False
    dot = abs(sum(float(x) * y for x, y in zip(a, b)) / (na * nb))
    return 1.0 - min(1.0, dot) <= ROTATION_DOT_TOLERANCE


def _encode_quat_frames(frames: list[list[int]], components: int) -> tuple[list[int], list[list[int]]]:
    if not frames:
        raise CompiledDeltaError("quaternion track has no frames")
    stored_components = components - 1
    stored: list[int] = []
    decoded: list[list[int]] = []
    for i, raw in enumerate(frames):
        if not isinstance(raw, list) or len(raw) != components:
            raise CompiledDeltaError(f"quaternion frame {i} expected {components} components")
        frame = [_i16(v) for v in raw]
        omitted_negative = frame[-1] < 0
        continuity_negated = False
        if i > 0 and omitted_negative:
            continuity_negated = _quat_dot(frames[i - 1], frame) > 0
        sign = -1 if continuity_negated else 1
        row = [_i16(frame[j] * sign) for j in range(stored_components)]
        stored.extend(row)
        reconstructed = row + [_omitted_component(row)]
        if i > 0 and _quat_dot(decoded[-1], reconstructed) < 0:
            reconstructed = [-v for v in reconstructed]
        if not _rotation_equivalent(frame, reconstructed):
            raise CompiledDeltaError(
                f"quaternion frame {i} is not representable by v19 omitted-component encoding: "
                f"raw={frame} reconstructed={reconstructed}"
            )
        decoded.append(reconstructed)
    return stored, decoded


def _decode_quat_frames(data: bytes, pos: int, count: int, components: int):
    stored_components = components - 1
    frames: list[list[int]] = []
    for i in range(count):
        end = pos + stored_components * 2
        if end > len(data):
            raise CompiledDeltaError("truncated quaternion frame")
        row = list(struct.unpack_from("<" + "h" * stored_components, data, pos))
        pos = end
        q = row + [_omitted_component(row)]
        if i > 0 and _quat_dot(frames[-1], q) < 0:
            q = [-v for v in q]
        frames.append(q)
    return frames, pos


def encode_delta_section(delta: dict | None, header: dict) -> bytes:
    delta = delta or {}
    try:
        timing = timing_info(header)
    except DeltaGltfError as exc:
        raise CompiledDeltaError(str(exc)) from exc
    n = int(timing["numframes"])
    num_loop_frames = n + 1
    use_byte = n < 256
    has_3d = bool(header.get("bDelta3D"))
    has_2d = bool(header.get("bDelta"))
    q2, q3 = delta.get("quat2"), delta.get("quat")
    if q2 and q3:
        raise CompiledDeltaError("compiled v19 delta must select either quat2 or quat, not both")
    if q3 and not has_3d:
        raise CompiledDeltaError("quat3D present but header.bDelta3D is false")
    if q2 and has_3d:
        raise CompiledDeltaError("quat2 present while header.bDelta3D selects 3D delta")
    if q2 and not has_2d:
        raise CompiledDeltaError("quat2 present but header.bDelta is false")

    out = bytearray()
    q = q3 if has_3d else q2
    components = 4 if has_3d else 2
    if not q:
        out.extend(struct.pack("<H", 0))
    elif q.get("mode") == "constant":
        raw = q.get("rawInt16")
        stored, _ = _encode_quat_frames([raw], components)
        out.extend(struct.pack("<H", 1))
        out.extend(struct.pack("<" + "h" * len(stored), *stored))
    elif q.get("mode") == "dynamic":
        inds, _ = _indices(q, header, "delta quaternion")
        frames = q.get("rawInt16Frames", [])
        if len(frames) != len(inds):
            raise CompiledDeltaError("delta quaternion index/frame mismatch")
        stored, _ = _encode_quat_frames(frames, components)
        out.extend(struct.pack("<H", len(inds)))
        _write_indices(out, inds, num_loop_frames, use_byte)
        out.extend(struct.pack("<" + "h" * len(stored), *stored))
    else:
        raise CompiledDeltaError(f"unknown delta quaternion mode {q.get('mode')!r}")

    t = delta.get("trans")
    if not t:
        out.extend(struct.pack("<H", 0))
    elif t.get("mode") == "constant":
        value = t.get("value", [])
        if not isinstance(value, list) or len(value) != 3:
            raise CompiledDeltaError("constant delta translation requires VEC3")
        vals = [float(v) for v in value]
        if not all(math.isfinite(v) for v in vals):
            raise CompiledDeltaError("nonfinite constant delta translation")
        out.extend(struct.pack("<H3f", 1, *vals))
    elif t.get("mode") == "dynamic":
        inds, _ = _indices(t, header, "delta translation")
        mins = [float(v) for v in t.get("mins", [])]
        raw_size = [float(v) for v in t.get("rawSize", [])]
        frames = t.get("quantizedFrames", [])
        if len(mins) != 3 or len(raw_size) != 3 or not all(math.isfinite(v) for v in mins + raw_size):
            raise CompiledDeltaError("dynamic delta translation missing finite mins/rawSize")
        if len(frames) != len(inds):
            raise CompiledDeltaError("delta translation index/frame mismatch")
        small = bool(t.get("smallTrans"))
        limit = 255 if small else 65535
        clean_frames = []
        for i, row in enumerate(frames):
            if not isinstance(row, list) or len(row) != 3:
                raise CompiledDeltaError(f"translation frame {i} is not VEC3")
            clean = []
            for v in row:
                if isinstance(v, bool) or not isinstance(v, int) or not (0 <= v <= limit):
                    raise CompiledDeltaError(f"translation quantized value {v!r} outside 0..{limit}")
                clean.append(v)
            clean_frames.append(clean)
        out.extend(struct.pack("<H", len(inds)))
        _write_indices(out, inds, num_loop_frames, use_byte)
        out.extend(struct.pack("<?3f3f", small, *mins, *raw_size))
        flat = [v for row in clean_frames for v in row]
        if small:
            out.extend(bytes(flat))
        else:
            out.extend(struct.pack("<" + "H" * len(flat), *flat))
    else:
        raise CompiledDeltaError(f"unknown delta translation mode {t.get('mode')!r}")
    return bytes(out)


def decode_delta_section(data: bytes, header: dict) -> dict:
    try:
        timing = timing_info(header)
    except DeltaGltfError as exc:
        raise CompiledDeltaError(str(exc)) from exc
    n = int(timing["numframes"])
    num_loop_frames = n + 1
    use_byte = n < 256
    has_3d = bool(header.get("bDelta3D"))
    components = 4 if has_3d else 2
    pos = 0
    if len(data) < 2:
        raise CompiledDeltaError("truncated delta quaternion count")
    qcount = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    q = None
    if qcount:
        inds = []
        if qcount > 1:
            inds, pos = _read_indices(data, pos, qcount, num_loop_frames, use_byte)
        frames, pos = _decode_quat_frames(data, pos, qcount, components)
        q = {
            "mode": "constant" if qcount == 1 else "dynamic",
            "rawInt16": frames[0] if qcount == 1 else None,
            "rawInt16Frames": frames if qcount > 1 else None,
            "indices": inds,
            "compiledStoredComponentCount": components - 1,
        }

    if pos + 2 > len(data):
        raise CompiledDeltaError("truncated delta translation count")
    tcount = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    trans = None
    if tcount == 1:
        if pos + 12 > len(data):
            raise CompiledDeltaError("truncated constant delta translation")
        trans = {"mode": "constant", "value": list(struct.unpack_from("<3f", data, pos))}
        pos += 12
    elif tcount > 1:
        inds, pos = _read_indices(data, pos, tcount, num_loop_frames, use_byte)
        need = 1 + 24
        if pos + need > len(data):
            raise CompiledDeltaError("truncated dynamic delta translation header")
        small = bool(data[pos])
        pos += 1
        mins = list(struct.unpack_from("<3f", data, pos)); pos += 12
        raw_size = list(struct.unpack_from("<3f", data, pos)); pos += 12
        value_count = tcount * 3
        if small:
            end = pos + value_count
            if end > len(data):
                raise CompiledDeltaError("truncated u8 delta translation frames")
            flat = list(data[pos:end]); pos = end
        else:
            end = pos + value_count * 2
            if end > len(data):
                raise CompiledDeltaError("truncated u16 delta translation frames")
            flat = list(struct.unpack_from("<" + "H" * value_count, data, pos)); pos = end
        frames = [flat[i:i+3] for i in range(0, len(flat), 3)]
        scale = HALF_TRANS_SIZE_SCALE if small else FULL_TRANS_SIZE_SCALE
        step = [v * scale for v in raw_size]
        decoded = [[mins[k] + row[k] * step[k] for k in range(3)] for row in frames]
        trans = {
            "mode": "dynamic",
            "smallTrans": small,
            "indices": inds,
            "mins": mins,
            "rawSize": raw_size,
            "quantizedFrames": frames,
            "decodedStep": step,
            "decodedFrames": decoded,
        }
    if pos != len(data):
        raise CompiledDeltaError(f"compiled delta subsection has {len(data)-pos} trailing bytes")
    return {
        "quat": q if has_3d else None,
        "quat2": q if not has_3d else None,
        "trans": trans,
        "bytes": len(data),
        "indexWidthBytes": 1 if use_byte else 2,
    }


def roundtrip_delta_section(delta: dict | None, header: dict) -> dict:
    payload = encode_delta_section(delta, header)
    decoded = decode_delta_section(payload, header)
    return {"payload": payload, "decoded": decoded}
