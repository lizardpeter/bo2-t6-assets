#!/usr/bin/env python3
"""Source-closed T6 XModel mesh + skin + optional XAnim glTF exporter v4.

This is the generalized successor to:
- t6_xmodel_mesh_normalize_v1.py (rigid + 1/2/3/4-influence vertsBlend)
- t6_xanim_gltf_export_v3.py (skinned mesh glTF)
- t6_xanim_rigid_gltf_export_v3.py (retail-proven non-root translation semantics)

v4 deliberately fails closed on:
- unweighted vertices,
- bound XAnim deltaPart,
- animated root-bone translation.

For animated non-root bones, T6 XAnim translation is a delta and glTF keys are:
    XModel bind-local translation + decoded XAnim translation delta

With no --xanim, v4 exports a bind-pose skinned model with no animation object.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import math
import struct
from pathlib import Path

from t6_xanim_gltf_export_v3 import export as export_v3, validate as validate_v3, ExportError
from t6_xanim_rigid_gltf_export_v3 import trans_values

_BUFFER_URI_PREFIX = "data:application/octet-stream;base64,"


def _append_f32_vec3(gltf: dict, raw: bytearray, rows: list[list[float]], name: str) -> int:
    if any(len(r) != 3 for r in rows):
        raise ExportError(f"{name}: malformed VEC3")
    vals = [float(v) for row in rows for v in row]
    if not all(math.isfinite(v) for v in vals):
        raise ExportError(f"{name}: nonfinite VEC3")
    while len(raw) % 4:
        raw.append(0)
    offset = len(raw)
    payload = struct.pack("<" + "f" * len(vals), *vals)
    raw.extend(payload)
    view_index = len(gltf["bufferViews"])
    gltf["bufferViews"].append({
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(payload),
        "name": name,
    })
    acc = {
        "bufferView": view_index,
        "componentType": 5126,
        "count": len(rows),
        "type": "VEC3",
        "name": name,
    }
    if rows:
        acc["min"] = [min(row[k] for row in rows) for k in range(3)]
        acc["max"] = [max(row[k] for row in rows) for k in range(3)]
    accessor_index = len(gltf["accessors"])
    gltf["accessors"].append(acc)
    return accessor_index


def _selected_surfaces(mesh_doc: dict, lod: int) -> tuple[dict, list[dict]]:
    lods = mesh_doc.get("xmodel", {}).get("lods", [])
    lod_meta = next((x for x in lods if int(x["index"]) == int(lod)), None)
    if lod_meta is None:
        raise ExportError(f"LOD{lod} unavailable")
    first = int(lod_meta["surfIndex"])
    count = int(lod_meta["numSurfs"])
    surfaces = mesh_doc.get("surfaces", [])
    if first < 0 or count < 0 or first + count > len(surfaces):
        raise ExportError(f"LOD{lod} surface span outside normalized mesh")
    return lod_meta, surfaces[first:first + count]


def validate_skin_rows(mesh_doc: dict, skeleton_doc: dict, lod: int = 0) -> dict:
    """Validate normalized T6 JOINTS_0/WEIGHTS_0 and return a compact census."""
    bones = skeleton_doc.get("skeleton", {}).get("bones", [])
    bone_count = len(bones)
    if bone_count <= 0:
        raise ExportError("empty skeleton")
    _, surfaces = _selected_surfaces(mesh_doc, lod)

    totals = {
        "surfaces": len(surfaces),
        "vertices": 0,
        "triangles": 0,
        "rigidVertices": 0,
        "blendedVertices": 0,
        "unweightedVertices": 0,
        "influenceHistogram": {"1": 0, "2": 0, "3": 0, "4": 0},
    }
    max_sum_error = 0.0
    min_positive_weight = 1.0
    max_positive_weight = 0.0

    for surface in surfaces:
        vertices = surface.get("vertices", [])
        joints = surface.get("joints0", [])
        weights = surface.get("weights0", [])
        triangles = surface.get("triangles", [])
        if not (len(vertices) == len(joints) == len(weights)):
            raise ExportError(
                f"surf{surface.get('index')}: vertices/joints0/weights0 length mismatch "
                f"{len(vertices)}/{len(joints)}/{len(weights)}"
            )

        rigid = sum(int(r.get("vertCount", 0)) for r in surface.get("rigidVertLists", []))
        blend_counts = [int(v) for v in surface.get("blendCounts", [0, 0, 0, 0])]
        if len(blend_counts) != 4 or any(v < 0 for v in blend_counts):
            raise ExportError(f"surf{surface.get('index')}: invalid blendCounts {blend_counts}")
        blended = sum(blend_counts)
        unweighted = int(surface.get("unweightedVertexCount", len(vertices) - rigid - blended))
        if rigid + blended + unweighted != len(vertices):
            raise ExportError(
                f"surf{surface.get('index')}: weight census does not cover vertices "
                f"{rigid}+{blended}+{unweighted}!={len(vertices)}"
            )
        if unweighted:
            raise ExportError(
                f"surf{surface.get('index')}: {unweighted} unweighted vertices; "
                "v4 fails closed instead of inventing a skin binding"
            )

        expected_hist = [rigid + blend_counts[0], blend_counts[1], blend_counts[2], blend_counts[3]]
        observed_hist = [0, 0, 0, 0]
        for vi, (jrow, wrow) in enumerate(zip(joints, weights)):
            if len(jrow) != 4 or len(wrow) != 4:
                raise ExportError(f"surf{surface.get('index')} vertex {vi}: JOINTS/WEIGHTS must be VEC4")
            positives = 0
            total = 0.0
            for joint, weight in zip(jrow, wrow):
                joint = int(joint)
                weight = float(weight)
                if not math.isfinite(weight):
                    raise ExportError(f"surf{surface.get('index')} vertex {vi}: nonfinite weight")
                if weight < -1e-6:
                    raise ExportError(f"surf{surface.get('index')} vertex {vi}: negative weight {weight}")
                if weight > 1e-8:
                    if joint < 0 or joint >= bone_count:
                        raise ExportError(
                            f"surf{surface.get('index')} vertex {vi}: joint {joint} outside {bone_count}"
                        )
                    positives += 1
                    min_positive_weight = min(min_positive_weight, weight)
                    max_positive_weight = max(max_positive_weight, weight)
                total += weight
            err = abs(total - 1.0)
            max_sum_error = max(max_sum_error, err)
            if err > 1e-5:
                raise ExportError(
                    f"surf{surface.get('index')} vertex {vi}: nonunit skin weights {wrow} sum={total}"
                )
            if positives < 1 or positives > 4:
                raise ExportError(
                    f"surf{surface.get('index')} vertex {vi}: invalid positive influence count {positives}"
                )
            observed_hist[positives - 1] += 1

        if observed_hist != expected_hist:
            raise ExportError(
                f"surf{surface.get('index')}: influence histogram {observed_hist} "
                f"!= serializer census {expected_hist}"
            )

        totals["vertices"] += len(vertices)
        totals["triangles"] += len(triangles)
        totals["rigidVertices"] += rigid
        totals["blendedVertices"] += blended
        totals["unweightedVertices"] += unweighted
        for i, count in enumerate(observed_hist, start=1):
            totals["influenceHistogram"][str(i)] += count

    totals["maxWeightSumError"] = max_sum_error
    totals["minPositiveWeight"] = min_positive_weight if totals["vertices"] else None
    totals["maxPositiveWeight"] = max_positive_weight if totals["vertices"] else None
    totals["allVerticesWeighted"] = totals["unweightedVertices"] == 0
    return totals


def _empty_xanim(model_name: str) -> dict:
    return {
        "format": "t6-xanim-normalized-v1-synthetic-bind-pose",
        "name": model_name + "_bind_pose",
        "header": {"framerate": 30.0},
        "boneTracks": [],
        "delta": {},
        "notifies": [],
    }


def export(mesh_doc: dict, skeleton_doc: dict, xanim_doc: dict | None = None, lod: int = 0) -> dict:
    if mesh_doc.get("format") != "t6-xmodel-mesh-normalized-v1":
        raise ExportError(f"unsupported mesh format {mesh_doc.get('format')!r}")
    if not str(skeleton_doc.get("format", "")).startswith("t6-xmodel-skeleton-normalized-v2"):
        raise ExportError(f"unsupported skeleton format {skeleton_doc.get('format')!r}")
    if mesh_doc.get("identity", {}).get("name") != skeleton_doc.get("identity", {}).get("name"):
        raise ExportError("mesh/skeleton identity mismatch")

    skin = validate_skin_rows(mesh_doc, skeleton_doc, lod)
    animated = xanim_doc is not None
    xanim = copy.deepcopy(xanim_doc if animated else _empty_xanim(mesh_doc["identity"]["name"]))

    delta = xanim.get("delta") or {}
    if any(delta.get(k) for k in ("trans", "quat2", "quat")):
        raise ExportError("v4 rejects bound XAnim deltaPart until its model-binding path is source-closed")

    gltf = export_v3(mesh_doc, skeleton_doc, xanim, lod)
    uri = gltf["buffers"][0]["uri"]
    if not uri.startswith(_BUFFER_URI_PREFIX):
        raise ExportError("v4 requires embedded base64 buffer")
    raw = bytearray(base64.b64decode(uri[len(_BUFFER_URI_PREFIX):]))

    corrected = 0
    bones = skeleton_doc["skeleton"]["bones"]
    by_name = {b["name"]: b for b in bones}
    tracks = {t["name"]: t for t in xanim.get("boneTracks", xanim.get("tracks", []))}

    if animated:
        for channel in gltf["animations"][0]["channels"]:
            if channel["target"]["path"] != "translation":
                continue
            name = channel.get("extras", {}).get("trackName")
            if name == "__T6_DELTA_ROOT__":
                raise ExportError("unexpected delta root after deltaPart rejection")
            bone = by_name.get(name)
            track = tracks.get(name)
            if bone is None or track is None:
                raise ExportError(f"cannot bind translation channel {name!r}")
            values = trans_values(track, bone)
            if values is None:
                continue
            sampler = gltf["animations"][0]["samplers"][channel["sampler"]]
            old = gltf["accessors"][sampler["output"]]
            if int(old["count"]) != len(values):
                raise ExportError(
                    f"{name}: translated key count mismatch {old['count']} != {len(values)}"
                )
            sampler["output"] = _append_f32_vec3(
                gltf, raw, values, f"{name}:translation:bindPlusDelta"
            )
            channel.setdefault("extras", {})["t6Composition"] = (
                "XModel localTranslation + XAnim translation delta"
            )
            corrected += 1
    else:
        gltf.pop("animations", None)

    gltf["asset"]["generator"] = "bo2-t6-assets t6_xanim_skinned_gltf_export_v4.py"
    extras = gltf.setdefault("extras", {}).setdefault("T6", {})
    extras.update({
        "skinValidation": skin,
        "translationCompositionCorrectedChannels": corrected,
        "rootTranslationPolicy": "reject animated root translation until separately source-closed",
        "deltaPartPolicy": "reject bound deltaPart until separately source-closed",
        "meshFormat": mesh_doc["format"],
        "skeletonFormat": skeleton_doc["format"],
    })
    if animated and gltf.get("animations"):
        anim_extras = gltf["animations"][0].setdefault("extras", {}).setdefault("T6", {})
        anim_extras["translationCompositionCorrectedChannels"] = corrected
        anim_extras["rootTranslationPolicy"] = extras["rootTranslationPolicy"]
        anim_extras["deltaPartPolicy"] = extras["deltaPartPolicy"]

    gltf["buffers"][0] = {
        "byteLength": len(raw),
        "uri": _BUFFER_URI_PREFIX + base64.b64encode(raw).decode("ascii"),
    }
    validate_v3(gltf)
    return gltf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh_json", type=Path)
    ap.add_argument("skeleton_json", type=Path)
    ap.add_argument("output_gltf", type=Path)
    ap.add_argument("--xanim", type=Path)
    ap.add_argument("--lod", type=int, default=0)
    args = ap.parse_args()

    mesh = json.loads(args.mesh_json.read_text(encoding="utf-8"))
    skeleton = json.loads(args.skeleton_json.read_text(encoding="utf-8"))
    xanim = json.loads(args.xanim.read_text(encoding="utf-8")) if args.xanim else None
    gltf = export(mesh, skeleton, xanim, args.lod)
    text = json.dumps(gltf, indent=2, sort_keys=True) + "\n"
    args.output_gltf.write_text(text, encoding="utf-8")

    skin = gltf["extras"]["T6"]["skinValidation"]
    print(json.dumps({
        "out": str(args.output_gltf),
        "bytes": len(text.encode("utf-8")),
        "vertices": skin["vertices"],
        "triangles": skin["triangles"],
        "rigidVertices": skin["rigidVertices"],
        "blendedVertices": skin["blendedVertices"],
        "influenceHistogram": skin["influenceHistogram"],
        "joints": len(gltf["skins"][0]["joints"]),
        "animationChannels": len(gltf.get("animations", [{}])[0].get("channels", []))
            if gltf.get("animations") else 0,
        "translationCompositionCorrectedChannels":
            gltf["extras"]["T6"]["translationCompositionCorrectedChannels"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
