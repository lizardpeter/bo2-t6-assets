#!/usr/bin/env python3
"""Attach a retained uniform normal-map sample decode to canonical T6 recipes.

This is intentionally the final recipe gate before renderer normal playback.  A
secondary-normal recipe must already carry:

* `normalTransformShaderBindingsV1` with v15 cross-proof agreement;
* `layeredNormalBasisV1` with exact paired-VS N/T/B roles;
* exact canonical pixel-shader identity.

The supplied decode proof must come from
`t6_generated_normal_sample_decode_probe_v1`, must have zero affine failures and
one uniform affine decode, and must contain exactly one matching shader row for
the recipe TechniqueSet/PS identity.  No fallback `2*x-1` assumption exists.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from t6_generated_shader_recipe_contract_v1 import validate_recipe

PROOF_FORMAT = "t6-generated-normal-sample-decode-probe-v1"
FORMAT = "t6-generated-normal-sample-decode-recipe-v1"
ATTACHMENT_KEY = "normalSampleDecodeV1"
TRANSFORM_KEY = "normalTransformShaderBindingsV1"
BASIS_KEY = "layeredNormalBasisV1"
CANONICAL_RECIPE_KEY = "generatedShaderRecipeV1"


class NormalSampleDecodeAttachError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _layers(recipe: dict) -> list[int]:
    program = recipe.get("layerProgram")
    if not isinstance(program, list):
        raise NormalSampleDecodeAttachError(f"{recipe.get('material')!r}: missing layerProgram")
    return sorted(int(row["layerIndex"]) for row in program if bool(row.get("hasNormal")))


def _proof_preflight(proof: dict) -> dict:
    if proof.get("format") != PROOF_FORMAT:
        raise NormalSampleDecodeAttachError(
            f"unsupported normal sample decode proof {proof.get('format')!r}"
        )
    summary = proof.get("summary")
    uniform = proof.get("uniformDecode")
    if not isinstance(summary, dict) or not isinstance(uniform, dict):
        raise NormalSampleDecodeAttachError("decode proof lacks summary/uniformDecode")
    if int(summary.get("affineDecodeFailureCount", -1)) != 0:
        raise NormalSampleDecodeAttachError("decode proof contains affine failures")
    if not bool(summary.get("uniformAffineDecode")) or int(summary.get("uniqueAffineDecodeCount", -1)) != 1:
        raise NormalSampleDecodeAttachError("decode proof does not establish one uniform affine decode")
    if int(summary.get("normalLayerCount", 0)) <= 0 or int(summary.get("channelDecodeObservationCount", 0)) <= 0:
        raise NormalSampleDecodeAttachError("decode proof target population is empty")
    for key in ("scale", "offset", "scaleFloat32Bits", "offsetFloat32Bits"):
        if key not in uniform:
            raise NormalSampleDecodeAttachError(f"uniform decode lacks {key}")
    if not str(summary.get("rowsSha256") or ""):
        raise NormalSampleDecodeAttachError("decode proof lacks rowsSha256")
    return uniform


def _recipe_prerequisites(recipe: dict, expected_layers: list[int]) -> None:
    transform = recipe.get(TRANSFORM_KEY)
    if not isinstance(transform, dict) or not bool(transform.get("crossProofAgreement")):
        raise NormalSampleDecodeAttachError(
            f"{recipe.get('material')!r}: v15 dual-proof normal transform binding is absent"
        )
    transform_rows = transform.get("secondaryNormalBindings")
    if not isinstance(transform_rows, list) or sorted(int(r["layerIndex"]) for r in transform_rows) != expected_layers:
        raise NormalSampleDecodeAttachError(
            f"{recipe.get('material')!r}: v15 transform layers do not match recipe normals"
        )
    basis = recipe.get(BASIS_KEY)
    if not isinstance(basis, dict) or basis.get("format") != "t6-generated-layered-normal-basis-recipe-v1":
        raise NormalSampleDecodeAttachError(
            f"{recipe.get('material')!r}: v16 exact layered normal basis is absent"
        )
    if sorted(int(v) for v in basis.get("secondaryNormalLayers", [])) != expected_layers:
        raise NormalSampleDecodeAttachError(
            f"{recipe.get('material')!r}: v16 basis layers do not match recipe normals"
        )


def _shader_row(recipe: dict, proof: dict, expected_layers: list[int]) -> dict:
    technique = str(recipe.get("techniqueSet") or "")
    matches = [row for row in proof.get("rows", []) if str(row.get("techniqueSet") or "") == technique]
    if len(matches) != 1:
        raise NormalSampleDecodeAttachError(
            f"{technique!r}: decode proof matched {len(matches)} shader rows"
        )
    row = matches[0]
    expected_ps = str(recipe.get("pixelShaderArchetype") or "")
    if expected_ps != "sha256:" + str(row.get("sha256") or ""):
        raise NormalSampleDecodeAttachError(
            f"{technique!r}: decode proof pixel shader differs from canonical recipe"
        )
    layer_rows = row.get("normalLayers")
    if not isinstance(layer_rows, list) or sorted(int(v["layerIndex"]) for v in layer_rows) != expected_layers:
        raise NormalSampleDecodeAttachError(
            f"{technique!r}: decode proof normal layers do not match canonical recipe"
        )
    return row


def build_attachment(recipe: dict, proof: dict) -> dict | None:
    uniform = _proof_preflight(proof)
    canonical = validate_recipe(recipe)
    layers = _layers(canonical)
    if not layers:
        return None
    _recipe_prerequisites(recipe, layers)
    row = _shader_row(canonical, proof, layers)

    scale_bits = str(uniform["scaleFloat32Bits"])
    offset_bits = str(uniform["offsetFloat32Bits"])
    layer_evidence = []
    for layer_row in row["normalLayers"]:
        evidence = {"layerIndex": int(layer_row["layerIndex"]), "channels": {}}
        decode = layer_row.get("decode")
        if not isinstance(decode, dict):
            raise NormalSampleDecodeAttachError(
                f"{canonical['material']!r} layer {layer_row.get('layerIndex')}: decode evidence missing"
            )
        for channel in ("x", "y"):
            item = decode.get(channel)
            if not isinstance(item, dict):
                raise NormalSampleDecodeAttachError(
                    f"{canonical['material']!r}: decode evidence lacks {channel}"
                )
            if str(item.get("scaleFloat32Bits") or "") != scale_bits or str(item.get("offsetFloat32Bits") or "") != offset_bits:
                raise NormalSampleDecodeAttachError(
                    f"{canonical['material']!r}: per-layer decode disagrees with uniform proof"
                )
            evidence["channels"][channel] = {
                "boundarySha256": str(item.get("boundarySha256") or ""),
                "scaleFloat32Bits": scale_bits,
                "offsetFloat32Bits": offset_bits,
            }
        layer_evidence.append(evidence)

    basis = recipe[BASIS_KEY]
    transform = recipe[TRANSFORM_KEY]
    payload = {
        "format": FORMAT,
        "material": canonical["material"],
        "techniqueSet": canonical["techniqueSet"],
        "pixelShaderSha256": row["sha256"],
        "secondaryNormalLayers": layers,
        "decode": {
            "equation": "decodedChannel = sampledChannel * scale + offset",
            "scale": uniform["scale"],
            "offset": uniform["offset"],
            "scaleFloat32Bits": scale_bits,
            "offsetFloat32Bits": offset_bits,
        },
        "layerEvidence": layer_evidence,
        "sourceDecodeProofFormat": PROOF_FORMAT,
        "sourceDecodeRowsSha256": str(proof["summary"]["rowsSha256"]),
        "basisAttachmentSha256": str(basis.get("attachmentSha256") or ""),
        "transformBindingSha256": str(transform.get("bindingSha256") or ""),
        "playbackReady": True,
        "proofBoundary": (
            "retained per-layer normal sample X/Y affine decode + v15 dual-proof transform ownership + v16 exact paired-VS N/T/B basis; "
            "Blender/Tour arithmetic rounding and downstream lighting remain renderer concerns"
        ),
    }
    if not payload["basisAttachmentSha256"]:
        raise NormalSampleDecodeAttachError(
            f"{canonical['material']!r}: basis attachment lacks deterministic identity"
        )
    # Empty transform hash is permitted for direct-only synthetic fixtures, but
    # real transformed v15 rows carry one. The crossProofAgreement/layer mapping
    # above remains mandatory either way.
    payload["attachmentSha256"] = _jhash({
        "material": payload["material"],
        "pixelShaderSha256": payload["pixelShaderSha256"],
        "secondaryNormalLayers": layers,
        "decode": payload["decode"],
        "layerEvidence": layer_evidence,
        "basisAttachmentSha256": payload["basisAttachmentSha256"],
        "transformBindingSha256": payload["transformBindingSha256"],
    })
    return payload


def attach_gltf(document: dict, proof: dict) -> dict:
    _proof_preflight(proof)
    materials = document.get("materials")
    if not isinstance(materials, list):
        raise NormalSampleDecodeAttachError("glTF has no materials list")
    generated = normal = attached = 0
    hashes = []
    for material in materials:
        name = str(material.get("name") or "")
        if not name.startswith("*"):
            continue
        generated += 1
        recipe = material.get("extras", {}).get("T6", {}).get(CANONICAL_RECIPE_KEY)
        if not isinstance(recipe, dict):
            raise NormalSampleDecodeAttachError(f"{name!r}: canonical generated recipe missing")
        canonical = validate_recipe(recipe, expected_material=name)
        layers = _layers(canonical)
        if not layers:
            recipe.pop(ATTACHMENT_KEY, None)
            continue
        normal += 1
        payload = build_attachment(recipe, proof)
        if payload is None:
            raise NormalSampleDecodeAttachError(f"{name!r}: playback attachment unexpectedly null")
        recipe[ATTACHMENT_KEY] = payload
        attached += 1
        hashes.append(payload["attachmentSha256"])
    stats = {
        "generatedMaterialCount": generated,
        "secondaryNormalMaterialCount": normal,
        "playbackReadyMaterialCount": attached,
        "allSecondaryNormalMaterialsPlaybackReady": normal == attached,
        "uniquePlaybackAttachmentCount": len(set(hashes)),
        "playbackAttachmentSetSha256": _jhash(sorted(hashes)),
        "sourceDecodeRowsSha256": str(proof["summary"]["rowsSha256"]),
        "uniformDecode": copy.deepcopy(proof["uniformDecode"]),
    }
    if normal != attached:
        raise NormalSampleDecodeAttachError("normal sample decode attachment accounting mismatch")
    document.setdefault("extras", {}).setdefault("T6", {})["generatedLayeredNormalPlayback"] = {
        "format": FORMAT,
        "stats": stats,
        "policy": "playback-ready only after v15 transform + v16 basis + retained uniform sample decode all agree",
    }
    return stats
