#!/usr/bin/env python3
"""Retail-root-translation-closed T6 skinned XModel + XAnim glTF exporter v7.

v7 preserves v6's strict native deltaPart semantics and closes the last ordinary
bone-track translation binding rule from direct retail DObj skeleton proof:

- ROOT ordinary animated translation = decoded XAnim translation directly.
- NON-ROOT ordinary animated translation =
    XModel bind-local translation + decoded XAnim translation delta.

The dedicated __T6_DELTA_ROOT__ wrapper remains the separate XAnimParts.deltaPart
root-motion path and is not folded into ordinary bone-track translation.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
from pathlib import Path

from t6_xanim_gltf_export_v3 import ExportError, export as export_v3, validate as validate_v3
from t6_xanim_skinned_gltf_export_v4 import _empty_xanim, validate_skin_rows
from t6_xanim_skinned_gltf_export_v5 import _append_f32
from t6_xanim_skinned_gltf_export_v6 import _replace_delta_channels, _validate_v5

_BUFFER_URI_PREFIX = "data:application/octet-stream;base64,"
_DELTA_PROOF_MANIFEST = "manifests/xanim/T6_RETAIL_XANIM_DELTA_PROOF_V2.json"
_ROOT_PROOF_MANIFEST = "manifests/xanim/T6_RETAIL_XANIM_ROOT_TRANSLATION_PROOF_V1.json"
_RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"


def ordinary_translation_values(track: dict, bone: dict):
    """Return (values, composition_kind) for one ordinary XAnim translation track."""
    trans = track.get("trans") or {}
    typ = trans.get("type")
    if not typ or typ == "NO_TRANS":
        return None, None

    if typ in ("SMALL_TRANS", "FULL_TRANS"):
        decoded = trans.get("decodedFrames")
    elif typ == "TRANS_NO_SIZE":
        decoded = [trans.get("constant")]
    else:
        decoded = None

    if not decoded or any(row is None for row in decoded):
        raise ExportError(f"{bone['name']}: unsupported translation {typ}")

    delta = [[float(row[k]) for k in range(3)] for row in decoded]
    if bone.get("parentIndex") is None:
        return delta, "rootRawXAnim"

    bind = [float(v) for v in bone.get("localTranslation", [0.0, 0.0, 0.0])]
    return (
        [[bind[k] + row[k] for k in range(3)] for row in delta],
        "nonRootBindPlusDelta",
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
    xanim = copy.deepcopy(
        xanim_doc if animated else _empty_xanim(mesh_doc["identity"]["name"])
    )

    gltf = export_v3(mesh_doc, skeleton_doc, xanim, lod)
    validate_v3(gltf)
    uri = gltf["buffers"][0]["uri"]
    if not uri.startswith(_BUFFER_URI_PREFIX):
        raise ExportError("v7 requires embedded base64 buffer")
    raw = bytearray(base64.b64decode(uri[len(_BUFFER_URI_PREFIX):]))

    root_direct = 0
    nonroot_corrected = 0
    bones = skeleton_doc["skeleton"]["bones"]
    by_name = {b["name"]: b for b in bones}
    tracks = {t["name"]: t for t in xanim.get("boneTracks", xanim.get("tracks", []))}

    if animated:
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

            values, kind = ordinary_translation_values(track, bone)
            if values is None:
                continue
            sampler = gltf["animations"][0]["samplers"][channel["sampler"]]
            old = gltf["accessors"][sampler["output"]]
            if int(old["count"]) != len(values):
                raise ExportError(
                    f"{name}: translated key count mismatch {old['count']} != {len(values)}"
                )
            if kind == "rootRawXAnim":
                accessor_name = f"{name}:translation:rootRawXAnim"
                composition = "XAnim translation directly (root; no compact XModel.trans entry)"
                root_direct += 1
            else:
                accessor_name = f"{name}:translation:bindPlusDelta"
                composition = "XModel localTranslation + XAnim translation delta"
                nonroot_corrected += 1
            sampler["output"] = _append_f32(
                gltf, raw, values, "VEC3", accessor_name
            )
            channel.setdefault("extras", {}).update({
                "t6Composition": composition,
                "t6RootTranslationProofManifest": _ROOT_PROOF_MANIFEST,
                "t6RetailExeSha256": _RETAIL_SHA256,
            })

        delta_stats = _replace_delta_channels(gltf, raw, xanim)
    else:
        delta_stats = {
            "rotation": False,
            "translation": False,
            "durationSeconds": 0.0,
            "nativeDynamicDomainRequired": True,
        }
        gltf.pop("animations", None)

    gltf["asset"]["generator"] = "bo2-t6-assets t6_xanim_skinned_gltf_export_v7.py"
    extras = gltf.setdefault("extras", {}).setdefault("T6", {})
    extras.update({
        "skinValidation": skin,
        "translationCompositionCorrectedChannels": root_direct + nonroot_corrected,
        "ordinaryRootTranslationChannels": root_direct,
        "ordinaryNonRootBindPlusDeltaChannels": nonroot_corrected,
        "rootTranslationPolicy": (
            "retail-byte-proven: ordinary roots use raw decoded XAnim translation; "
            "non-roots use XModel bind-local translation + XAnim translation delta"
        ),
        "rootTranslationProofManifest": _ROOT_PROOF_MANIFEST,
        "deltaPartPolicy": (
            "retail-byte-proven deltaPart root wrapper; dynamic tracks require exact native "
            "0..numframes domain"
        ),
        "deltaEndpointPolicy": "stored native keys only; no fabricated/clamped endpoints",
        "deltaPartProofManifest": _DELTA_PROOF_MANIFEST,
        "retailExeSha256": _RETAIL_SHA256,
        "deltaRotationExactGltfEncoding": "CUBICSPLINE normalized component-linear path",
        "deltaChannelsRewritten": delta_stats,
        "meshFormat": mesh_doc["format"],
        "skeletonFormat": skeleton_doc["format"],
    })
    if animated and gltf.get("animations"):
        anim_extras = gltf["animations"][0].setdefault("extras", {}).setdefault("T6", {})
        anim_extras.update({
            "translationCompositionCorrectedChannels": root_direct + nonroot_corrected,
            "ordinaryRootTranslationChannels": root_direct,
            "ordinaryNonRootBindPlusDeltaChannels": nonroot_corrected,
            "rootTranslationPolicy": extras["rootTranslationPolicy"],
            "rootTranslationProofManifest": _ROOT_PROOF_MANIFEST,
            "deltaPartPolicy": extras["deltaPartPolicy"],
            "deltaEndpointPolicy": extras["deltaEndpointPolicy"],
            "deltaPartProofManifest": _DELTA_PROOF_MANIFEST,
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
        "animationChannels": (
            len(gltf.get("animations", [{}])[0].get("channels", []))
            if gltf.get("animations") else 0
        ),
        "translationCompositionCorrectedChannels": (
            gltf["extras"]["T6"]["translationCompositionCorrectedChannels"]
        ),
        "ordinaryRootTranslationChannels": gltf["extras"]["T6"]["ordinaryRootTranslationChannels"],
        "ordinaryNonRootBindPlusDeltaChannels": (
            gltf["extras"]["T6"]["ordinaryNonRootBindPlusDeltaChannels"]
        ),
        "deltaChannelsRewritten": gltf["extras"]["T6"]["deltaChannelsRewritten"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
