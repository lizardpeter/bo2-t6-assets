#!/usr/bin/env python3
"""Retail-proven T6 XAnim deltaPart -> exact glTF semantics v2.

v2 corrects the permissive endpoint policy in v1. Retail T6's
XAnim_GetTimeIndex requires each evaluated frame to be bracketed by two stored
indices; native dynamic delta tracks serialize size+1 keys over the complete
0..numframes domain. v2 therefore never invents/clamps endpoint keys:

- dynamic indices must start at 0 and end at numframes;
- indices must be strictly increasing and in range;
- key times are exactly index / framerate;
- optional XAnimParts.frequency must equal framerate / numframes (or 0 when
  numframes==0), while animation duration remains numframes / framerate;
- constant delta tracks remain constant over the whole animation because the
  retail During and Entire evaluators both return the same stored frame0.

Dynamic quaternion interpolation remains v1's exact glTF CUBICSPLINE mapping:
T6 linearly interpolates stored int16 quaternion components. The emitted cubic
is a positive scalar multiple of that component-linear vector at every point;
glTF's required quaternion normalization therefore produces exactly the native
rotation path rather than SLERP.
"""
from __future__ import annotations

import math

ENGINE_QUAT_SCALE = 1.0 / 32767.0


class DeltaGltfError(RuntimeError):
    pass


def timing_info(header: dict) -> dict:
    try:
        numframes = int(header.get("numframes", 0))
        fps = float(header.get("framerate", 0.0))
    except (TypeError, ValueError) as exc:
        raise DeltaGltfError("invalid XAnim timing fields") from exc
    if numframes < 0:
        raise DeltaGltfError(f"invalid numframes {numframes}")
    if not math.isfinite(fps) or fps <= 0.0:
        raise DeltaGltfError(f"invalid framerate {fps}")
    duration = numframes / fps
    expected_frequency = fps / numframes if numframes else 0.0
    if "frequency" in header and header.get("frequency") is not None:
        try:
            frequency = float(header["frequency"])
        except (TypeError, ValueError) as exc:
            raise DeltaGltfError("invalid frequency") from exc
        if not math.isfinite(frequency):
            raise DeltaGltfError(f"invalid frequency {frequency}")
        if not math.isclose(frequency, expected_frequency, rel_tol=5e-5, abs_tol=1e-7):
            raise DeltaGltfError(
                f"frequency {frequency} != framerate/numframes {expected_frequency}"
            )
    return {
        "numframes": numframes,
        "framerate": fps,
        "durationSeconds": duration,
        "frequency": expected_frequency,
        "indexWidthBytes": 1 if numframes < 256 else 2,
    }


def duration_seconds(header: dict) -> float:
    return float(timing_info(header)["durationSeconds"])


def _native_dynamic_domain(indices: list[int], header: dict, label: str) -> dict:
    timing = timing_info(header)
    numframes = int(timing["numframes"])
    if numframes <= 0:
        raise DeltaGltfError(f"{label}: dynamic track requires numframes > 0")
    if len(indices) < 2:
        raise DeltaGltfError(f"{label}: dynamic track requires at least two keys")
    if any(isinstance(v, bool) for v in indices):
        raise DeltaGltfError(f"{label}: boolean frame index")
    if indices[0] != 0:
        raise DeltaGltfError(
            f"{label}: first native key must be frame 0, got {indices[0]}"
        )
    if indices[-1] != numframes:
        raise DeltaGltfError(
            f"{label}: final native key must be numframes {numframes}, got {indices[-1]}"
        )
    if any(v < 0 or v > numframes for v in indices):
        raise DeltaGltfError(f"{label}: frame index outside 0..{numframes}: {indices}")
    if any(b <= a for a, b in zip(indices, indices[1:])):
        raise DeltaGltfError(f"{label}: frame indices are not strictly increasing: {indices}")
    return timing


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _unit(v: list[float]) -> list[float]:
    n = _norm(v)
    if not math.isfinite(n) or n <= 1e-12:
        raise DeltaGltfError(f"invalid quaternion norm {n}")
    return [x / n for x in v]


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
        raise DeltaGltfError(
            "both quat2 and quat are present without an unambiguous bDelta/bDelta3D selector"
        )
    if q2:
        return q2, True, "quat2"
    if q3:
        return q3, False, "quat"
    return None


def _engine_quat(raw: list[int], half: bool) -> list[float]:
    need = 2 if half else 4
    if len(raw) != need:
        raise DeltaGltfError(
            f"delta quaternion expected {need} int16 components, got {len(raw)}"
        )
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
    n0, n1 = _norm(raw0), _norm(raw1)
    if n0 <= 1e-12 or n1 <= 1e-12:
        raise DeltaGltfError("zero endpoint delta quaternion")
    if _segment_min_norm(raw0, raw1) <= 1e-10:
        raise DeltaGltfError(
            "native component-linear delta quaternion crosses zero and cannot define a rotation"
        )
    s0, s1 = 1.0 / n0, 1.0 / n1
    ds = s1 - s0
    d = [b - a for a, b in zip(raw0, raw1)]
    m0_du = [ds * a + s0 * dv for a, dv in zip(raw0, d)]
    m1_du = [ds * b + s1 * dv for b, dv in zip(raw1, d)]
    return [x / dt for x in m0_du], [x / dt for x in m1_du]


def delta_translation_sampler(delta: dict, header: dict) -> dict | None:
    track = (delta or {}).get("trans")
    if not track:
        return None
    timing = timing_info(header)
    duration = float(timing["durationSeconds"])
    mode = track.get("mode")
    if mode == "constant":
        value = [float(x) for x in track.get("value", [])]
        if len(value) != 3 or not all(math.isfinite(x) for x in value):
            raise DeltaGltfError("constant delta translation must be finite VEC3")
        times = [0.0, duration] if duration > 0.0 else [0.0]
        return {
            "times": times,
            "values": [list(value) for _ in times],
            "interpolation": "LINEAR",
            "sourceMode": "constant",
            "nativeDomainValidated": True,
            "indexWidthBytes": timing["indexWidthBytes"],
        }
    if mode != "dynamic":
        raise DeltaGltfError(f"unknown delta translation mode {mode!r}")
    try:
        indices = [int(x) for x in track.get("indices", [])]
    except (TypeError, ValueError) as exc:
        raise DeltaGltfError("dynamic delta translation has invalid indices") from exc
    values = [[float(x) for x in row] for row in track.get("decodedFrames", [])]
    if len(indices) != len(values):
        raise DeltaGltfError("dynamic delta translation index/frame mismatch")
    if any(len(row) != 3 or not all(math.isfinite(x) for x in row) for row in values):
        raise DeltaGltfError("dynamic delta translation contains malformed VEC3")
    timing = _native_dynamic_domain(indices, header, "delta translation")
    fps = float(timing["framerate"])
    return {
        "times": [i / fps for i in indices],
        "values": values,
        "interpolation": "LINEAR",
        "sourceMode": "small" if track.get("smallTrans") else "full",
        "nativeDomainValidated": True,
        "indexWidthBytes": timing["indexWidthBytes"],
    }


def delta_rotation_sampler(delta: dict, header: dict) -> dict | None:
    picked = _rotation_source(delta or {}, header)
    if picked is None:
        return None
    track, half, typ = picked
    timing = timing_info(header)
    duration = float(timing["durationSeconds"])
    mode = track.get("mode")
    if mode == "constant":
        raw = _engine_quat([int(x) for x in track.get("rawInt16", [])], half)
        value = _unit(raw)
        times = [0.0, duration] if duration > 0.0 else [0.0]
        return {
            "times": times,
            "values": [list(value) for _ in times],
            "interpolation": "LINEAR",
            "sourceType": typ,
            "sourceMode": "constant",
            "exactRetailComponentLinear": True,
            "nativeDomainValidated": True,
            "indexWidthBytes": timing["indexWidthBytes"],
        }
    if mode != "dynamic":
        raise DeltaGltfError(f"unknown delta rotation mode {mode!r}")
    try:
        indices = [int(x) for x in track.get("indices", [])]
        raw_int = [[int(x) for x in row] for row in track.get("rawInt16Frames", [])]
    except (TypeError, ValueError) as exc:
        raise DeltaGltfError("dynamic delta rotation has invalid data") from exc
    if len(indices) != len(raw_int):
        raise DeltaGltfError("dynamic delta rotation index/frame mismatch")
    timing = _native_dynamic_domain(indices, header, "delta rotation")
    raw_rows = [_engine_quat(row, half) for row in raw_int]
    fps = float(timing["framerate"])
    times = [i / fps for i in indices]
    values = [_unit(row) for row in raw_rows]
    in_tan = [[0.0] * 4 for _ in values]
    out_tan = [[0.0] * 4 for _ in values]
    for i in range(len(values) - 1):
        out_tan[i], in_tan[i + 1] = _exact_segment_tangents(
            raw_rows[i], raw_rows[i + 1], times[i + 1] - times[i]
        )
    cubic_rows: list[list[float]] = []
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
        "nativeDomainValidated": True,
        "indexWidthBytes": timing["indexWidthBytes"],
    }
