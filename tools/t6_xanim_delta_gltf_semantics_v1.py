#!/usr/bin/env python3
"""Map retail-proven T6 XAnim deltaPart tracks to exact glTF interpolation.

Retail T6 linearly interpolates stored delta quaternion components, then the
rotation is used as a quaternion. glTF LINEAR rotation uses spherical
interpolation, so sparse LINEAR quaternion keys are not the same path.

For dynamic delta rotations this module emits CUBICSPLINE values/tangents whose
unnormalized cubic polynomial is a positive scalar multiple of the native T6
component-wise linear quaternion for every point in each segment. glTF requires
CUBICSPLINE rotation results to be normalized before application, making the
resulting rotation path exactly the normalized T6 component-linear path while
keeping every stored key value unit length.
"""
from __future__ import annotations

import math

ENGINE_QUAT_SCALE = 1.0 / 32767.0


class DeltaGltfError(RuntimeError):
    pass


def duration_seconds(header: dict) -> float:
    fps = float(header.get("framerate", 0.0))
    numframes = int(header.get("numframes", 0))
    if not math.isfinite(fps) or fps <= 0.0:
        raise DeltaGltfError(f"invalid framerate {fps}")
    if numframes < 0:
        raise DeltaGltfError(f"invalid numframes {numframes}")
    return numframes / fps


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _unit(v: list[float]) -> list[float]:
    n = _norm(v)
    if not math.isfinite(n) or n <= 1e-12:
        raise DeltaGltfError(f"invalid quaternion norm {n}")
    return [x / n for x in v]


def _strictly_increasing(times: list[float], label: str) -> None:
    if any(not math.isfinite(t) for t in times):
        raise DeltaGltfError(f"{label}: nonfinite time")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise DeltaGltfError(f"{label}: times are not strictly increasing: {times}")


def _extend_domain(times: list[float], rows: list[list[float]], duration: float, label: str):
    if len(times) != len(rows) or not times:
        raise DeltaGltfError(f"{label}: time/value mismatch")
    _strictly_increasing(times, label)
    eps = 1e-7
    if times[0] < -eps:
        raise DeltaGltfError(f"{label}: negative first time {times[0]}")
    if times[-1] > duration + eps:
        raise DeltaGltfError(f"{label}: last key {times[-1]} exceeds duration {duration}")
    out_t = list(times)
    out_r = [list(r) for r in rows]
    if out_t[0] > eps:
        out_t.insert(0, 0.0)
        out_r.insert(0, list(out_r[0]))
    elif abs(out_t[0]) <= eps:
        out_t[0] = 0.0
    if duration > 0.0 and out_t[-1] < duration - eps:
        out_t.append(duration)
        out_r.append(list(out_r[-1]))
    elif duration > 0.0 and abs(out_t[-1] - duration) <= eps:
        out_t[-1] = duration
    _strictly_increasing(out_t, label)
    return out_t, out_r


def delta_translation_sampler(delta: dict, header: dict) -> dict | None:
    track = (delta or {}).get("trans")
    if not track:
        return None
    duration = duration_seconds(header)
    mode = track.get("mode")
    if mode == "constant":
        value = [float(x) for x in track.get("value", [])]
        if len(value) != 3 or not all(math.isfinite(x) for x in value):
            raise DeltaGltfError("constant delta translation must be finite VEC3")
        times = [0.0, duration] if duration > 0.0 else [0.0]
        values = [list(value) for _ in times]
        return {"times": times, "values": values, "interpolation": "LINEAR", "sourceMode": "constant"}
    if mode != "dynamic":
        raise DeltaGltfError(f"unknown delta translation mode {mode!r}")
    indices = [int(x) for x in track.get("indices", [])]
    values = [[float(x) for x in row] for row in track.get("decodedFrames", [])]
    if len(indices) != len(values) or not indices:
        raise DeltaGltfError("dynamic delta translation index/frame mismatch")
    if any(len(row) != 3 or not all(math.isfinite(x) for x in row) for row in values):
        raise DeltaGltfError("dynamic delta translation contains malformed VEC3")
    fps = float(header["framerate"])
    times = [i / fps for i in indices]
    times, values = _extend_domain(times, values, duration, "delta translation")
    return {
        "times": times,
        "values": values,
        "interpolation": "LINEAR",
        "sourceMode": "small" if track.get("smallTrans") else "full",
    }


def _rotation_source(delta: dict, header: dict):
    q2 = (delta or {}).get("quat2")
    q3 = (delta or {}).get("quat")
    if q2 and q3:
        b2 = bool(header.get("bDelta"))
        b3 = bool(header.get("bDelta3D"))
        if b2 and not b3:
            return q2, True, "quat2"
        if b3 and not b2:
            return q3, False, "quat"
        raise DeltaGltfError("both quat2 and quat are present without an unambiguous bDelta/bDelta3D selector")
    if q2:
        return q2, True, "quat2"
    if q3:
        return q3, False, "quat"
    return None


def _engine_quat(raw: list[int], half: bool) -> list[float]:
    need = 2 if half else 4
    if len(raw) != need:
        raise DeltaGltfError(f"delta quaternion expected {need} int16 components, got {len(raw)}")
    if any(int(v) < -32768 or int(v) > 32767 for v in raw):
        raise DeltaGltfError("delta quaternion int16 out of range")
    scaled = [int(v) * ENGINE_QUAT_SCALE for v in raw]
    return [0.0, 0.0, scaled[0], scaled[1]] if half else scaled


def _segment_min_norm(a: list[float], b: list[float]) -> float:
    d = [y - x for x, y in zip(a, b)]
    dd = sum(x * x for x in d)
    if dd <= 1e-30:
        return _norm(a)
    t = -sum(x * y for x, y in zip(a, d)) / dd
    t = min(1.0, max(0.0, t))
    return _norm([x + t * y for x, y in zip(a, d)])


def _exact_segment_tangents(raw0: list[float], raw1: list[float], dt: float):
    if not math.isfinite(dt) or dt <= 0.0:
        raise DeltaGltfError(f"invalid quaternion segment duration {dt}")
    n0 = _norm(raw0)
    n1 = _norm(raw1)
    if n0 <= 1e-12 or n1 <= 1e-12:
        raise DeltaGltfError("zero endpoint delta quaternion")
    if _segment_min_norm(raw0, raw1) <= 1e-10:
        raise DeltaGltfError("native component-linear delta quaternion crosses zero and cannot define a rotation")
    s0 = 1.0 / n0
    s1 = 1.0 / n1
    ds = s1 - s0
    d = [b - a for a, b in zip(raw0, raw1)]
    # p(u)=(s0+(s1-s0)u)*(raw0+u*(raw1-raw0)). p normalized is exactly
    # normalize(lerp(raw0,raw1,u)); p(0/1) are unit quaternions.
    m0_du = [ds * a + s0 * dv for a, dv in zip(raw0, d)]
    m1_du = [ds * b + s1 * dv for b, dv in zip(raw1, d)]
    return [x / dt for x in m0_du], [x / dt for x in m1_du]


def delta_rotation_sampler(delta: dict, header: dict) -> dict | None:
    picked = _rotation_source(delta or {}, header)
    if picked is None:
        return None
    track, half, typ = picked
    duration = duration_seconds(header)
    mode = track.get("mode")
    if mode == "constant":
        raw_rows = [_engine_quat([int(x) for x in track.get("rawInt16", [])], half)]
        times = [0.0, duration] if duration > 0.0 else [0.0]
        value = _unit(raw_rows[0])
        return {
            "times": times,
            "values": [list(value) for _ in times],
            "interpolation": "LINEAR",
            "sourceType": typ,
            "sourceMode": "constant",
            "exactRetailComponentLinear": True,
        }
    if mode != "dynamic":
        raise DeltaGltfError(f"unknown delta rotation mode {mode!r}")
    indices = [int(x) for x in track.get("indices", [])]
    raw_int = [[int(x) for x in row] for row in track.get("rawInt16Frames", [])]
    if len(indices) != len(raw_int) or not indices:
        raise DeltaGltfError("dynamic delta rotation index/frame mismatch")
    raw_rows = [_engine_quat(row, half) for row in raw_int]
    fps = float(header["framerate"])
    times = [i / fps for i in indices]
    times, raw_rows = _extend_domain(times, raw_rows, duration, "delta rotation")
    values = [_unit(row) for row in raw_rows]
    in_tan = [[0.0] * 4 for _ in values]
    out_tan = [[0.0] * 4 for _ in values]
    for i in range(len(values) - 1):
        out_tan[i], in_tan[i + 1] = _exact_segment_tangents(raw_rows[i], raw_rows[i + 1], times[i + 1] - times[i])
    cubic_rows = []
    for i in range(len(values)):
        cubic_rows.extend([in_tan[i], values[i], out_tan[i]])
    return {
        "times": times,
        "values": values,
        "cubicRows": cubic_rows,
        "inTangents": in_tan,
        "outTangents": out_tan,
        "interpolation": "CUBICSPLINE",
        "sourceType": typ,
        "sourceMode": "dynamic",
        "exactRetailComponentLinear": True,
    }
