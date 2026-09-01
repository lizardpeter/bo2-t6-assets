#!/usr/bin/env python3
"""Export normalized T6 XModel skeleton + XAnim tracks as self-contained glTF 2.0.

Inputs:
- t6-xmodel-skeleton-normalized-v2 JSON
- t6-xanim-normalized-v1 JSON

The exporter validates bone name/ScriptString binding, expands T6 quaternion
semantics, and emits standard glTF animation channels. Native T6 local values
remain unchanged under a single conversion wrapper:
  - rotate -90 degrees about X: T6 Z-up -> glTF Y-up
  - uniform scale 0.0254: T6 inches -> meters

Lossless source JSON remains authoritative; glTF extras retain source identity,
track type, notifies, delta metadata, and source hashes.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import struct
from pathlib import Path
from typing import Iterable

from t6_xanim_quaternion_semantics import augment_normalized_xanim, unit_xyzw

T6_UNIT_TO_METERS = 0.0254
SQRT_HALF = math.sqrt(0.5)
T6_ZUP_TO_GLTF_YUP_XYZW = [-SQRT_HALF, 0.0, 0.0, SQRT_HALF]


class ExportError(RuntimeError):
    pass


class BufferBuilder:
    def __init__(self):
        self.data = bytearray()
        self.views: list[dict] = []
        self.accessors: list[dict] = []

    def _align4(self):
        while len(self.data) % 4:
            self.data.append(0)

    def add_f32(self, values: list[list[float]] | list[float], *, type_name: str, name: str) -> int:
        self._align4()
        offset = len(self.data)
        if type_name == "SCALAR":
            flat = [float(x) for x in values]  # type: ignore[arg-type]
            count = len(flat)
            comps = 1
        else:
            comps = {"VEC3": 3, "VEC4": 4}[type_name]
            rows = values  # type: ignore[assignment]
            flat = [float(v) for row in rows for v in row]  # type: ignore[union-attr]
            count = len(rows)  # type: ignore[arg-type]
            if any(len(row) != comps for row in rows):  # type: ignore[union-attr]
                raise ExportError(f"{name}: malformed {type_name}")
        if not all(math.isfinite(v) for v in flat):
            raise ExportError(f"{name}: non-finite float")
        self.data.extend(struct.pack("<" + "f" * len(flat), *flat))
        view = len(self.views)
        self.views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(flat) * 4, "name": name})
        acc: dict = {"bufferView": view, "componentType": 5126, "count": count, "type": type_name, "name": name}
        if type_name == "SCALAR" and flat:
            acc["min"] = [min(flat)]
            acc["max"] = [max(flat)]
        index = len(self.accessors)
        self.accessors.append(acc)
        return index


def normalized_bind_quat(raw: Iterable[float]) -> list[float]:
    vals = list(raw)
    if len(vals) != 4:
        raise ExportError("bind quaternion must have four components")
    return unit_xyzw(vals)


def strictly_increasing(values: list[int], label: str):
    if any(b <= a for a, b in zip(values, values[1:])):
        raise ExportError(f"{label}: keyframe indices are not strictly increasing: {values}")


def key_times(indices: list[int], framerate: float, label: str) -> list[float]:
    if framerate <= 0 or not math.isfinite(framerate):
        raise ExportError(f"{label}: invalid framerate {framerate}")
    strictly_increasing(indices, label)
    return [i / framerate for i in indices]


def track_rotation(q: dict, fps: float, label: str):
    typ = q.get("type")
    if typ == "NO_QUAT" or not q:
        return None
    frames = q.get("unitXYZWFrames")
    if not frames:
        raise ExportError(f"{label}: quaternion semantic expansion missing")
    if typ in ("HALF_QUAT", "FULL_QUAT"):
        indices = list(q.get("indices", []))
        if len(indices) != len(frames):
            raise ExportError(f"{label}: quaternion index/frame mismatch")
        times = key_times(indices, fps, label)
    elif typ in ("HALF_QUAT_NO_SIZE", "FULL_QUAT_NO_SIZE"):
        if len(frames) != 1:
            raise ExportError(f"{label}: constant quaternion has {len(frames)} frames")
        times = [0.0]
    else:
        raise ExportError(f"{label}: unknown quaternion type {typ}")
    return times, frames, typ


def track_translation(t: dict, fps: float, label: str):
    typ = t.get("type")
    if typ == "NO_TRANS" or not t:
        return None
    if typ in ("SMALL_TRANS", "FULL_TRANS"):
        frames = t.get("decodedFrames")
        indices = list(t.get("indices", []))
        if not frames or len(indices) != len(frames):
            raise ExportError(f"{label}: translation index/frame mismatch")
        times = key_times(indices, fps, label)
    elif typ == "TRANS_NO_SIZE":
        frames = [t.get("constant")]
        if frames[0] is None:
            raise ExportError(f"{label}: missing constant translation")
        times = [0.0]
    else:
        raise ExportError(f"{label}: unknown translation type {typ}")
    return times, frames, typ


def delta_rotation(delta: dict, fps: float):
    q = delta.get("quat2") or delta.get("quat")
    if not q:
        return None
    frames = q.get("unitXYZWFrames")
    if not frames:
        raise ExportError("delta rotation semantic expansion missing")
    if q.get("mode") == "constant":
        return [0.0], frames, ("quat2" if delta.get("quat2") else "quat")
    indices = list(q.get("indices", []))
    if len(indices) != len(frames):
        raise ExportError("delta quaternion index/frame mismatch")
    return key_times(indices, fps, "delta rotation"), frames, ("quat2" if delta.get("quat2") else "quat")


def delta_translation(delta: dict, fps: float):
    t = delta.get("trans")
    if not t:
        return None
    if t.get("mode") == "constant":
        return [0.0], [t["value"]], "constant"
    frames = t.get("decodedFrames")
    indices = list(t.get("indices", []))
    if not frames or len(indices) != len(frames):
        raise ExportError("delta translation index/frame mismatch")
    return key_times(indices, fps, "delta translation"), frames, ("small" if t.get("smallTrans") else "full")


def export_gltf(skeleton_doc: dict, xanim_doc: dict) -> dict:
    augment_normalized_xanim(xanim_doc)
    bones = skeleton_doc["skeleton"]["bones"]
    tracks = xanim_doc.get("boneTracks", xanim_doc.get("tracks", []))
    if not bones:
        raise ExportError("skeleton has no bones")
    name_to_index: dict[str, int] = {}
    for b in bones:
        name = b.get("name")
        if not name:
            raise ExportError(f"skeleton bone {b.get('index')} has no name")
        if name in name_to_index:
            raise ExportError(f"duplicate skeleton bone name {name}")
        name_to_index[name] = int(b["index"])

    track_names = set()
    bindings = []
    for t in tracks:
        name = t.get("name")
        if not name or name in track_names:
            raise ExportError(f"invalid/duplicate animation track name {name}")
        track_names.add(name)
        if name not in name_to_index:
            raise ExportError(f"animation track {name} does not exist in skeleton")
        bi = name_to_index[name]
        bone = bones[bi]
        tsid = t.get("scriptString")
        bsid = bone.get("scriptStringId")
        if tsid is not None and bsid is not None and int(tsid) != int(bsid):
            raise ExportError(f"ScriptString mismatch for {name}: anim {tsid} != model {bsid}")
        bindings.append({"trackName": name, "boneIndex": bi, "scriptString": tsid})

    nodes: list[dict] = []
    for b in bones:
        node = {
            "name": b["name"],
            "translation": [float(v) for v in b.get("localTranslation", [0.0, 0.0, 0.0])],
            "rotation": normalized_bind_quat(b.get("localRotation", [0.0, 0.0, 0.0, 1.0])),
            "extras": {"t6BoneIndex": b["index"], "scriptStringId": b.get("scriptStringId"), "partClassificationRaw": b.get("partClassificationRaw")},
        }
        nodes.append(node)
    roots = []
    children_by_parent: dict[int, list[int]] = {}
    for b in bones:
        i = int(b["index"])
        p = b.get("parentIndex")
        if p is None:
            roots.append(i)
        else:
            children_by_parent.setdefault(int(p), []).append(i)
    for p, ch in children_by_parent.items():
        nodes[p]["children"] = ch

    fps = float(xanim_doc["header"]["framerate"])
    delta = xanim_doc.get("delta") or {}
    has_delta = bool(delta.get("trans") or delta.get("quat2") or delta.get("quat"))
    delta_node = None
    if has_delta:
        delta_node = len(nodes)
        nodes.append({"name": "__T6_DELTA_ROOT__", "translation": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0, 1.0], "children": roots, "extras": {"t6DeltaRoot": True}})
        converted_roots = [delta_node]
    else:
        converted_roots = roots
    wrapper = len(nodes)
    nodes.append({
        "name": "__T6_WORLD_TO_GLTF__",
        "rotation": T6_ZUP_TO_GLTF_YUP_XYZW,
        "scale": [T6_UNIT_TO_METERS, T6_UNIT_TO_METERS, T6_UNIT_TO_METERS],
        "children": converted_roots,
        "extras": {"t6UnitMeters": T6_UNIT_TO_METERS, "axisConversion": "rotate -90deg X: T6 Z-up -> glTF Y-up"},
    })

    buf = BufferBuilder()
    samplers: list[dict] = []
    channels: list[dict] = []

    def add_channel(node_index: int, path: str, times: list[float], values: list[list[float]], type_name: str, extras: dict):
        if not times or len(times) != len(values):
            raise ExportError(f"{extras}: empty or mismatched channel")
        ia = buf.add_f32(times, type_name="SCALAR", name=f"{extras.get('trackName', 'delta')}:{path}:time")
        oa = buf.add_f32(values, type_name=type_name, name=f"{extras.get('trackName', 'delta')}:{path}:value")
        si = len(samplers)
        samplers.append({"input": ia, "output": oa, "interpolation": "LINEAR"})
        channels.append({"sampler": si, "target": {"node": node_index, "path": path}, "extras": extras})

    for t in tracks:
        bi = name_to_index[t["name"]]
        qr = track_rotation(t.get("quat") or {}, fps, f"{t['name']} rotation")
        if qr:
            times, values, typ = qr
            add_channel(bi, "rotation", times, values, "VEC4", {"trackName": t["name"], "t6TrackType": typ, "scriptString": t.get("scriptString")})
        tr = track_translation(t.get("trans") or {}, fps, f"{t['name']} translation")
        if tr:
            times, values, typ = tr
            add_channel(bi, "translation", times, values, "VEC3", {"trackName": t["name"], "t6TrackType": typ, "scriptString": t.get("scriptString")})

    if delta_node is not None:
        qr = delta_rotation(delta, fps)
        if qr:
            times, values, typ = qr
            add_channel(delta_node, "rotation", times, values, "VEC4", {"trackName": "__T6_DELTA_ROOT__", "t6DeltaType": typ})
        tr = delta_translation(delta, fps)
        if tr:
            times, values, typ = tr
            add_channel(delta_node, "translation", times, values, "VEC3", {"trackName": "__T6_DELTA_ROOT__", "t6DeltaType": typ})

    duration = max((a.get("max", [0.0])[0] for a in buf.accessors if a["type"] == "SCALAR"), default=0.0)
    t6_extras = {
        "skeletonIdentity": skeleton_doc.get("identity"),
        "skeletonSource": skeleton_doc.get("source"),
        "xanimName": xanim_doc.get("name"),
        "xanimAssetFixedStart": xanim_doc.get("assetFixedStart"),
        "xanimSerializedEnd": xanim_doc.get("assetSerializedEnd"),
        "xanimSerializedSha256": xanim_doc.get("assetSerializedSha256"),
        "numframes": xanim_doc["header"].get("numframes"),
        "framerate": fps,
        "looped": bool(xanim_doc["header"].get("bLoop", False)),
        "durationSeconds": duration,
        "notifies": xanim_doc.get("notifies", []),
        "binding": {"trackCount": len(tracks), "boundTrackCount": len(bindings), "bindings": bindings},
        "losslessSidecars": ["t6-xmodel-skeleton-normalized-v2", "t6-xanim-normalized-v1"],
    }
    gltf = {
        "asset": {"version": "2.0", "generator": "bo2-t6-assets t6_xanim_gltf_export.py"},
        "scene": 0,
        "scenes": [{"name": xanim_doc.get("name", "T6 Animation"), "nodes": [wrapper]}],
        "nodes": nodes,
        "animations": [{"name": xanim_doc.get("name", "T6 Animation"), "samplers": samplers, "channels": channels, "extras": {"T6": t6_extras}}],
        "bufferViews": buf.views,
        "accessors": buf.accessors,
        "buffers": [{"byteLength": len(buf.data), "uri": "data:application/octet-stream;base64," + base64.b64encode(buf.data).decode("ascii")}],
        "extras": {"T6": {"coordinateSystem": "native bone/track values under conversion wrapper", "unitToMeters": T6_UNIT_TO_METERS}},
    }
    return gltf


def validate_gltf(gltf: dict):
    if gltf.get("asset", {}).get("version") != "2.0":
        raise ExportError("not glTF 2.0")
    nodes = gltf.get("nodes", [])
    for anim in gltf.get("animations", []):
        samplers = anim["samplers"]
        for ch in anim["channels"]:
            if ch["sampler"] >= len(samplers):
                raise ExportError("animation sampler index out of bounds")
            ni = ch["target"]["node"]
            if ni >= len(nodes):
                raise ExportError("animation target node out of bounds")
            s = samplers[ch["sampler"]]
            if s["input"] >= len(gltf["accessors"]) or s["output"] >= len(gltf["accessors"]):
                raise ExportError("animation accessor out of bounds")
            ia = gltf["accessors"][s["input"]]
            oa = gltf["accessors"][s["output"]]
            if ia["count"] != oa["count"]:
                raise ExportError("sampler input/output count mismatch")
    raw = base64.b64decode(gltf["buffers"][0]["uri"].split(",", 1)[1])
    if len(raw) != gltf["buffers"][0]["byteLength"]:
        raise ExportError("embedded buffer length mismatch")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json", type=Path)
    ap.add_argument("xanim_json", type=Path)
    ap.add_argument("output_gltf", type=Path)
    args = ap.parse_args()
    skeleton = json.loads(args.skeleton_json.read_text(encoding="utf-8"))
    xanim = json.loads(args.xanim_json.read_text(encoding="utf-8"))
    gltf = export_gltf(skeleton, xanim)
    validate_gltf(gltf)
    args.output_gltf.write_text(json.dumps(gltf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(args.output_gltf),
        "nodes": len(gltf["nodes"]),
        "channels": len(gltf["animations"][0]["channels"]),
        "samplers": len(gltf["animations"][0]["samplers"]),
        "durationSeconds": gltf["animations"][0]["extras"]["T6"]["durationSeconds"],
        "boundTracks": gltf["animations"][0]["extras"]["T6"]["binding"]["boundTrackCount"],
        "embeddedBufferBytes": gltf["buffers"][0]["byteLength"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
