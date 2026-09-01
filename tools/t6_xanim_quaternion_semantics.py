#!/usr/bin/env python3
"""Expand lossless T6 XAnim int16 quaternions into standard xyzw form.

T6 PART_TYPE_HALF_QUAT / HALF_QUAT_NO_SIZE and XAnimDeltaPartQuat2 represent
2-component rotations in the Z/W plane. The engine-family runtime expands these
as [0, 0, z, w] and scales int16 components by 1/32767.

The tool preserves raw values. It adds:
- engineXYZW*: direct engine-space floats, without renormalization.
- unitXYZW*: normalized xyzw values suitable for standard formats such as glTF.

For full quaternions all four stored components map directly to xyzw.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

ENGINE_QUAT_SCALE = 1.0 / 32767.0


class QuaternionSemanticError(RuntimeError):
    pass


def engine_half_xyzw(raw: Iterable[int]) -> list[float]:
    vals = list(raw)
    if len(vals) != 2:
        raise QuaternionSemanticError(f"half quaternion requires 2 int16 values, got {len(vals)}")
    z, w = vals
    return [0.0, 0.0, z * ENGINE_QUAT_SCALE, w * ENGINE_QUAT_SCALE]


def engine_full_xyzw(raw: Iterable[int]) -> list[float]:
    vals = list(raw)
    if len(vals) != 4:
        raise QuaternionSemanticError(f"full quaternion requires 4 int16 values, got {len(vals)}")
    return [v * ENGINE_QUAT_SCALE for v in vals]


def quat_norm(q: Iterable[float]) -> float:
    vals = list(q)
    if len(vals) != 4:
        raise QuaternionSemanticError("xyzw quaternion must have 4 values")
    return math.sqrt(sum(v * v for v in vals))


def unit_xyzw(q: Iterable[float]) -> list[float]:
    vals = list(q)
    n = quat_norm(vals)
    if not math.isfinite(n) or n <= 0.0:
        raise QuaternionSemanticError(f"cannot normalize quaternion with norm {n}")
    return [v / n for v in vals]


def hemisphere_continuous(frames: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for q in frames:
        q = list(q)
        if out and sum(a * b for a, b in zip(out[-1], q)) < 0.0:
            q = [-v for v in q]
        out.append(q)
    return out


def expand_frames(raw_frames: list[list[int]], half: bool) -> dict:
    engine = [(engine_half_xyzw(f) if half else engine_full_xyzw(f)) for f in raw_frames]
    unit = hemisphere_continuous([unit_xyzw(q) for q in engine])
    norms = [quat_norm(q) for q in engine]
    return {
        "engineXYZWFrames": engine,
        "unitXYZWFrames": unit,
        "engineNormMin": min(norms) if norms else None,
        "engineNormMax": max(norms) if norms else None,
        "engineMaxAbsNormError": max((abs(n - 1.0) for n in norms), default=0.0),
    }


def augment_quat_track(q: dict | None) -> None:
    if not q:
        return
    typ = q.get("type")
    raw = q.get("rawInt16Frames")
    if not raw:
        return
    if typ in ("HALF_QUAT", "HALF_QUAT_NO_SIZE"):
        q.update(expand_frames(raw, half=True))
        q["componentMapping"] = "raw[0]->z, raw[1]->w; x=y=0"
        q["engineScale"] = ENGINE_QUAT_SCALE
    elif typ in ("FULL_QUAT", "FULL_QUAT_NO_SIZE"):
        q.update(expand_frames(raw, half=False))
        q["componentMapping"] = "raw[0..3]->x,y,z,w"
        q["engineScale"] = ENGINE_QUAT_SCALE


def augment_delta(delta: dict | None) -> None:
    if not delta:
        return
    q2 = delta.get("quat2")
    if q2:
        if q2.get("mode") == "constant":
            raw = [q2["rawInt16"]]
        else:
            raw = q2.get("rawInt16Frames", [])
        q2.update(expand_frames(raw, half=True))
        q2["componentMapping"] = "raw[0]->z, raw[1]->w; x=y=0"
        q2["engineScale"] = ENGINE_QUAT_SCALE
    q = delta.get("quat")
    if q:
        if q.get("mode") == "constant":
            raw = [q["rawInt16"]]
        else:
            raw = q.get("rawInt16Frames", [])
        q.update(expand_frames(raw, half=False))
        q["componentMapping"] = "raw[0..3]->x,y,z,w"
        q["engineScale"] = ENGINE_QUAT_SCALE


def augment_normalized_xanim(doc: dict) -> dict:
    tracks = doc.get("boneTracks")
    if tracks is None:
        tracks = doc.get("tracks", [])
    for track in tracks:
        augment_quat_track(track.get("quat"))
    augment_delta(doc.get("delta"))
    doc.setdefault("quaternionSemantics", {})
    doc["quaternionSemantics"].update({
        "engineScale": ENGINE_QUAT_SCALE,
        "halfQuatXYZW": [0, 0, "raw0/32767", "raw1/32767"],
        "standardExport": "unitXYZWFrames",
        "losslessSource": "rawInt16Frames",
    })
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json", type=Path)
    ap.add_argument("output_json", type=Path)
    args = ap.parse_args()
    doc = json.loads(args.input_json.read_text(encoding="utf-8"))
    augment_normalized_xanim(doc)
    args.output_json.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
