#!/usr/bin/env python3
"""Retail-delta-aware generalized T6 skinned XModel + XAnim glTF exporter v5.

v5 keeps v4's generalized rigid/blended skin validation and retail-proven
non-root translation composition, and closes the separate XAnim deltaPart path:

- deltaPart is represented by the existing __T6_DELTA_ROOT__ wrapper;
- delta translation uses decoded T6 keys with glTF LINEAR interpolation;
- dynamic delta rotation uses exact CUBICSPLINE coefficients from
  t6_xanim_delta_gltf_semantics_v1 so normalized glTF playback follows T6's
  component-wise linear stored-quaternion path rather than glTF SLERP;
- delta channels are extended to numframes/framerate so sparse terminal keys do
  not shorten pure-delta animations.

Ordinary animated ROOT-BONE translation remains fail-closed. The retail proof
for deltaPart does not establish that separate model/bind-pose composition.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import math
import struct
from pathlib import Path

from t6_xanim_delta_gltf_semantics_v1 import (
    DeltaGltfError,
    delta_rotation_sampler,
    delta_translation_sampler,
    duration_seconds,
)
from t6_xanim_gltf_export_v3 import ExportError, export as export_v3, validate as validate_v3
from t6_xanim_rigid_gltf_export_v3 import trans_values
from t6_xanim_skinned_gltf_export_v4 import _empty_xanim, validate_skin_rows

_BUFFER_URI_PREFIX = "data:application/octet-stream;base64,"
_PROOF_MANIFEST = "manifests/xanim/T6_RETAIL_XANIM_DELTA_PROOF_V1.json"
_PROOF_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"


def _append_f32(gltf: dict, raw: bytearray, rows, typ: str, name: str) -> int:
    comps = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[typ]
    if typ == "SCALAR":
        rr = [[float(x)] for x in rows]
    else:
        rr = [[float(x) for x in row] for row in rows]
    if any(len(row) != comps for row in rr):
        raise ExportError(f"{name}: malformed {typ}")
    flat = [x for row in rr for x in row]
    if not all(math.isfinite(x) for x in flat):
        raise ExportError(f"{name}: nonfinite values")
    while len(raw) % 4:
        raw.append(0)
    offset = len(raw)
    payload = struct.pack("<" + "f" * len(flat), *flat)
    raw.extend(payload)
    view = len(gltf["bufferViews"])
    gltf["bufferViews"].append({
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(payload),
        "name": name,
    })
    acc = {
        "bufferView": view,
        "componentType": 5126,
        "count": len(rr),
        "type": typ,
        "name": name,
    }
    if typ == "SCALAR" and rr:
        vals = [r[0] for r in rr]
        acc["min"] = [min(vals)]
        acc["max"] = [max(vals)]
    elif typ == "VEC3" and rr:
        acc["min"] = [min(r[k] for r in rr) for k in range(3)]
        acc["max"] = [max(r[k] for r in rr) for k in range(3)]
    index = len(gltf["accessors"])
    gltf["accessors"].append(acc)
    return index


def _find_delta_channel(gltf: dict, path: str) -> dict | None:
    if not gltf.get("animations"):
        return None
    found = [
        ch for ch in gltf["animations"][0]["channels"]
        if ch.get("target", {}).get("path") == path
        and ch.get("extras", {}).get("trackName") == "__T6_DELTA_ROOT__"
    ]
    if len(found) > 1:
        raise ExportError(f"multiple delta-root {path} channels")
    return found[0] if found else None


def _replace_delta_channels(gltf: dict, raw: bytearray, xanim: dict) -> dict:
    delta = xanim.get("delta") or {}
    if not any(delta.get(k) for k in ("trans", "quat2", "quat")):
        return {"rotation": False, "translation": False, "durationSeconds": duration_seconds(xanim["header"])}

    anim = gltf["animations"][0]
    header = xanim["header"]
    duration = duration_seconds(header)
    stats = {"rotation": False, "translation": False, "durationSeconds": duration}

    try:
        rot = delta_rotation_sampler(delta, header)
        trans = delta_translation_sampler(delta, header)
    except DeltaGltfError as exc:
        raise ExportError(f"deltaPart glTF mapping failed: {exc}") from exc

    rot_ch = _find_delta_channel(gltf, "rotation")
    if rot is None:
        if rot_ch is not None:
            raise ExportError("v3 produced a delta rotation channel without a retail delta rotation track")
    else:
        if rot_ch is None:
            raise ExportError("retail delta rotation track exists but v3 produced no delta-root rotation channel")
        sampler = anim["samplers"][rot_ch["sampler"]]
        sampler["input"] = _append_f32(gltf, raw, rot["times"], "SCALAR", "delta:rotation:retailTime")
        if rot["interpolation"] == "CUBICSPLINE":
            sampler["output"] = _append_f32(gltf, raw, rot["cubicRows"], "VEC4", "delta:rotation:retailCubic")
        else:
            sampler["output"] = _append_f32(gltf, raw, rot["values"], "VEC4", "delta:rotation:retailValue")
        sampler["interpolation"] = rot["interpolation"]
        rot_ch.setdefault("extras", {}).update({
            "t6RetailDeltaEvaluator": "XAnim_CalcDeltaForTime" if rot["sourceType"] == "quat2" else "XAnim_CalcDelta3DForTime",
            "t6RetailInterpolation": "component-linear stored int16 quaternion; normalized for glTF rotation",
            "t6GltfEncoding": rot["interpolation"],
            "t6ExactRetailComponentLinear": bool(rot["exactRetailComponentLinear"]),
            "t6ProofManifest": _PROOF_MANIFEST,
        })
        stats["rotation"] = True

    trans_ch = _find_delta_channel(gltf, "translation")
    if trans is None:
        if trans_ch is not None:
            raise ExportError("v3 produced a delta translation channel without a retail delta translation track")
    else:
        if trans_ch is None:
            raise ExportError("retail delta translation track exists but v3 produced no delta-root translation channel")
        sampler = anim["samplers"][trans_ch["sampler"]]
        sampler["input"] = _append_f32(gltf, raw, trans["times"], "SCALAR", "delta:translation:retailTime")
        sampler["output"] = _append_f32(gltf, raw, trans["values"], "VEC3", "delta:translation:retailValue")
        sampler["interpolation"] = "LINEAR"
        trans_ch.setdefault("extras", {}).update({
            "t6RetailDeltaEvaluator": "XAnim_CalcPosDelta_byte/ushort + XAnim_CalcPosDeltaEntire",
            "t6RetailInterpolation": "decoded translation linear interpolation",
            "t6ProofManifest": _PROOF_MANIFEST,
        })
        stats["translation"] = True

    anim.setdefault("extras", {}).setdefault("T6", {})["durationSeconds"] = duration
    return stats


def _validate_v5(gltf: dict) -> None:
    if gltf.get("asset", {}).get("version") != "2.0":
        raise ExportError("not glTF 2.0")
    raw = base64.b64decode(gltf["buffers"][0]["uri"].split(",", 1)[1])
    if len(raw) != gltf["buffers"][0]["byteLength"]:
        raise ExportError("buffer length mismatch")
    for skin in gltf.get("skins", []):
        ibm = skin["inverseBindMatrices"]
        if ibm >= len(gltf["accessors"]):
            raise ExportError("skin IBM accessor invalid")
        if gltf["accessors"][ibm]["count"] != len(skin["joints"]):
            raise ExportError("IBM/joint count mismatch")
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            for ai in list(prim["attributes"].values()) + [prim["indices"]]:
                if ai >= len(gltf["accessors"]):
                    raise ExportError("primitive accessor invalid")
    for anim in gltf.get("animations", []):
        for ch in anim["channels"]:
            sampler = anim["samplers"][ch["sampler"]]
            ia = gltf["accessors"][sampler["input"]]
            oa = gltf["accessors"][sampler["output"]]
            expected = ia["count"] * (3 if sampler.get("interpolation") == "CUBICSPLINE" else 1)
            if oa["count"] != expected:
                raise ExportError(
                    f"animation sampler count mismatch {oa['count']} != {expected} for {sampler.get('interpolation')}"
                )


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

    gltf = export_v3(mesh_doc, skeleton_doc, xanim, lod)
    # v3 is internally valid before v5 replaces delta samplers with CUBICSPLINE.
    validate_v3(gltf)
    uri = gltf["buffers"][0]["uri"]
    if not uri.startswith(_BUFFER_URI_PREFIX):
        raise ExportError("v5 requires embedded base64 buffer")
    raw = bytearray(base64.b64decode(uri[len(_BUFFER_URI_PREFIX):]))

    corrected = 0
    bones = skeleton_doc["skeleton"]["bones"]
    by_name = {b["name"]: b for b in bones}
    tracks = {t["name"]: t for t in xanim.get("boneTracks", xanim.get("tracks", []))}

    if animated:
        # Ordinary animated bone translations keep v4's source-closed policy.
        # deltaPart translation is a separate wrapper channel and is skipped here.
        for channel in gltf["animations"][0]["channels"]:
            if channel["target"]["path"] != "translation":
                continue
            name = channel.get("extras", {}).get("trackName")
            if name == "__T6_DELTA_ROOT__":
                continue
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
                raise ExportError(f"{name}: translated key count mismatch {old['count']} != {len(values)}")
            sampler["output"] = _append_f32(gltf, raw, values, "VEC3", f"{name}:translation:bindPlusDelta")
            channel.setdefault("extras", {})["t6Composition"] = "XModel localTranslation + XAnim translation delta"
            corrected += 1

        delta_stats = _replace_delta_channels(gltf, raw, xanim)
    else:
        delta_stats = {"rotation": False, "translation": False, "durationSeconds": 0.0}
        gltf.pop("animations", None)

    gltf["asset"]["generator"] = "bo2-t6-assets t6_xanim_skinned_gltf_export_v5.py"
    extras = gltf.setdefault("extras", {}).setdefault("T6", {})
    extras.update({
        "skinValidation": skin,
        "translationCompositionCorrectedChannels": corrected,
        "rootTranslationPolicy": "reject ordinary animated root-bone translation until separately source-closed",
        "deltaPartPolicy": "retail-byte-proven deltaPart root wrapper",
        "deltaPartProofManifest": _PROOF_MANIFEST,
        "deltaPartRetailExeSha256": _PROOF_SHA256,
        "deltaRotationExactGltfEncoding": "CUBICSPLINE normalized component-linear path",
        "deltaChannelsRewritten": delta_stats,
        "meshFormat": mesh_doc["format"],
        "skeletonFormat": skeleton_doc["format"],
    })
    if animated and gltf.get("animations"):
        anim_extras = gltf["animations"][0].setdefault("extras", {}).setdefault("T6", {})
        anim_extras.update({
            "translationCompositionCorrectedChannels": corrected,
            "rootTranslationPolicy": extras["rootTranslationPolicy"],
            "deltaPartPolicy": extras["deltaPartPolicy"],
            "deltaPartProofManifest": _PROOF_MANIFEST,
            "deltaChannelsRewritten": delta_stats,
        })

    gltf["buffers"][0] = {
        "byteLength": len(raw),
        "uri": _BUFFER_URI_PREFIX + base64.b64encode(raw).decode("ascii"),
    }
    _validate_v5(gltf)
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
        "animationChannels": len(gltf.get("animations", [{}])[0].get("channels", [])) if gltf.get("animations") else 0,
        "translationCompositionCorrectedChannels": gltf["extras"]["T6"]["translationCompositionCorrectedChannels"],
        "deltaChannelsRewritten": gltf["extras"]["T6"]["deltaChannelsRewritten"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
