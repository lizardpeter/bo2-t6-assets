#!/usr/bin/env python3
"""Attach exact retained generated layered-specular state to a Nuketown GLB.

This is deliberately *not* a generic PBR conversion.  The retained slot-4 proof
closes only the ordered T6 XYZW state:

    blend:     prev + (layer - prev) * exactRgbWeight
    threshold: select(exactRgbThresholdCondition, layer, prev)

and the no-base-spec baseline:

    RGB = (0.2, 0.2, 0.2)
    W   = base color alpha for x0 techniques, otherwise 0

The attachment binds every sN layer to the exact already-embedded material
texture dependency and explicitly states that its factor/condition is the SAME
layer scalar already used by the generated RGB compositor.  It does not map X/Y/Z/W
to metallic, roughness, F0 or any other renderer convention.

Proof scope is intentionally source-gated to the retained mp_nuketown_2020
population until a per-shader membership registry is serialized for broader
maps.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_generated_shader_recipe_contract_v1 import validate_recipe
from t6_generated_world_shader_semantics_v1 import (
    layer_weight_class,
    parse_generated_layer_tokens,
    technique_uses_x0_specular_fallback,
)

FORMAT = "t6-generated-layered-specular-state-v1"
ROOT_KEY = "generatedLayeredSpecularState"
RECIPE_KEY = "generatedSpecularStateV1"
MAP = "mp_nuketown_2020"
PROOF_FORMAT = "t6-retail-layered-specular-compositor-v1"
PROOF_RELATIVE = Path("manifests/render/T6_RETAIL_LAYERED_SPECULAR_COMPOSITOR_V1.json")


class GeneratedSpecularStateError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _proof_path() -> Path:
    return Path(__file__).resolve().parents[1] / PROOF_RELATIVE


def load_proof(path: Path | None = None) -> dict:
    target = _proof_path() if path is None else Path(path)
    try:
        proof = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GeneratedSpecularStateError(f"cannot read retained specular proof {target}: {exc}") from exc
    if proof.get("format") != PROOF_FORMAT:
        raise GeneratedSpecularStateError(
            f"unexpected retained specular proof {proof.get('format')!r}"
        )
    summary = proof.get("summary")
    if not isinstance(summary, dict):
        raise GeneratedSpecularStateError("retained specular proof has no summary")
    if int(summary.get("recurrenceFailureCount", -1)) != 0:
        raise GeneratedSpecularStateError("retained specular proof contains recurrence failures")
    if int(summary.get("sameRgbWeightDagMismatchCount", -1)) != 0:
        raise GeneratedSpecularStateError("retained specular proof disagrees with RGB layer weights")
    if int(summary.get("xyzwRecurrenceCheckCount", 0)) <= 0:
        raise GeneratedSpecularStateError("retained specular proof has no XYZW checks")
    recurrence = proof.get("recurrence")
    if not isinstance(recurrence, dict):
        raise GeneratedSpecularStateError("retained specular proof has no recurrence contract")
    if "prevSpecRGBA + (layerSpecRGBA - prevSpecRGBA)" not in str(recurrence.get("b") or ""):
        raise GeneratedSpecularStateError("retained specular blend recurrence changed")
    if "select(" not in str(recurrence.get("t") or ""):
        raise GeneratedSpecularStateError("retained specular threshold recurrence changed")
    return proof


def _dependencies(t6: dict) -> list[dict]:
    rows = t6.get("embeddedDependencyTextures")
    if isinstance(rows, list):
        return rows
    graph = t6.get("materialDependencyGraph")
    if isinstance(graph, dict):
        out = []
        for layer in graph.get("layers", []):
            if not isinstance(layer, dict):
                continue
            layer_index = int(layer.get("layerIndex", 0))
            for dep in layer.get("textures", []):
                if not isinstance(dep, dict):
                    continue
                out.append({
                    "layerIndex": layer_index,
                    "layer": layer.get("layer"),
                    "role": dep.get("role"),
                    "semantic": dep.get("semantic"),
                    "sourceTexture": dep.get("sourceTexture"),
                    "generatedTextureIndex": dep.get("textureIndex"),
                    "gfxImageAsset": dep.get("gfxImageAsset"),
                })
        return out
    return []


def _role_dependency(deps: list[dict], layer: int, role: str) -> dict | None:
    matches = [
        row for row in deps
        if int(row.get("layerIndex", -1)) == int(layer)
        and str(row.get("semantic") or row.get("role") or "") == role
    ]
    if len(matches) > 1:
        raise GeneratedSpecularStateError(
            f"layer {layer}: ambiguous exact {role} dependencies ({len(matches)})"
        )
    return matches[0] if matches else None


def _dependency_identity(dep: dict, *, layer: int, role: str) -> dict:
    source = str(dep.get("sourceTexture") or "")
    if not source:
        raise GeneratedSpecularStateError(
            f"layer {layer}: exact {role} dependency has empty sourceTexture"
        )
    out = {
        "layerIndex": int(layer),
        "role": role,
        "sourceTexture": source,
    }
    for key in (
        "gltfTextureIndex", "generatedTextureIndex", "gfxImageAsset",
        "gfxImage", "semantic", "materialArgument",
    ):
        if dep.get(key) is not None:
            out[key] = copy.deepcopy(dep[key])
    return out


def build_attachment(recipe: dict, deps: list[dict], proof: dict) -> dict | None:
    canonical = validate_recipe(recipe)
    material = str(canonical["material"])
    technique = str(canonical["techniqueSet"])
    tokens = parse_generated_layer_tokens(technique)
    spec_tokens = [token for token in tokens if token.has_specular]
    if not spec_tokens:
        return None

    proof_summary = proof["summary"]
    base_spec_dep = _role_dependency(deps, 0, "specularMap")
    if base_spec_dep is not None:
        baseline = {
            "mode": "explicit_specular",
            "dependency": _dependency_identity(base_spec_dep, layer=0, role="specularMap"),
            "state": "sample exact base specularMap RGBA",
        }
    else:
        use_color_alpha = technique_uses_x0_specular_fallback(technique)
        baseline = {
            "mode": "retail_fallback",
            "rgb": [0.2, 0.2, 0.2],
            "alphaMode": "baseColorAlpha" if use_color_alpha else "constantZero",
        }
        if use_color_alpha:
            color = _role_dependency(deps, 0, "colorMap")
            if color is None:
                raise GeneratedSpecularStateError(
                    f"{material!r}: x0 specular fallback requires exact base colorMap alpha"
                )
            baseline["alphaDependency"] = _dependency_identity(
                color, layer=0, role="colorMap"
            )
            baseline["alphaChannel"] = "a"
        else:
            baseline["alphaValue"] = 0.0

    steps = []
    for token in spec_tokens:
        if token.operation not in ("blend", "threshold"):
            raise GeneratedSpecularStateError(
                f"{material!r} layer {token.layer}: retained specular proof does not cover "
                f"operator {token.operation!r}"
            )
        dep = _role_dependency(deps, token.layer, "specularMap")
        if dep is None:
            raise GeneratedSpecularStateError(
                f"{material!r} layer {token.layer}: s{token.layer} lacks exact specularMap dependency"
            )
        factor_kind = "exactRgbThresholdCondition" if token.operation == "threshold" else "exactRgbWeight"
        steps.append({
            "layerIndex": int(token.layer),
            "operator": "t" if token.operation == "threshold" else "b",
            "operation": token.operation,
            "weightClass": layer_weight_class(token),
            "dependency": _dependency_identity(dep, layer=token.layer, role="specularMap"),
            "factorBinding": {
                "kind": factor_kind,
                "layerIndex": int(token.layer),
                "source": "same exact generated RGB compositor factor/condition",
            },
            "equation": (
                "prevSpecRGBA + (layerSpecRGBA - prevSpecRGBA) * exactRgbWeight"
                if token.operation == "blend"
                else "select(exactRgbThresholdCondition, layerSpecRGBA, prevSpecRGBA)"
            ),
        })

    payload = {
        "format": FORMAT,
        "map": MAP,
        "material": material,
        "techniqueSet": technique,
        "pixelShaderArchetype": canonical.get("pixelShaderArchetype"),
        "baseline": baseline,
        "steps": steps,
        "secondarySpecularLayerCount": len(steps),
        "sourceProof": str(PROOF_RELATIVE),
        "sourceProofShaderSetSha256": proof.get("sourceSlot4ShaderSetSha256"),
        "sourceProofRowsSha256": proof_summary.get("rowsSha256"),
        "sourceProofXyzwCheckCount": int(proof_summary["xyzwRecurrenceCheckCount"]),
        "stateSemantics": "retail generated specular XYZW; physical channel interpretation intentionally unassigned",
        "proofBoundary": (
            "Nuketown exact generated recipe + exact embedded specular dependencies + retained zero-failure "
            "slot-4 XYZW recurrence. Factor/threshold is shared with the exact RGB compositor. No generic "
            "metallic/roughness/F0 interpretation is asserted."
        ),
    }
    payload["attachmentSha256"] = _jhash(payload)
    return payload


def apply_contract(
    document: dict,
    raw: bytes,
    *,
    map_name: str,
    proof_path: Path | None = None,
) -> tuple[dict, bytes, dict]:
    if str(map_name) != MAP:
        raise GeneratedSpecularStateError(
            f"generated specular state v1 is source-gated to {MAP!r}, got {map_name!r}"
        )
    proof = load_proof(proof_path)
    materials = document.get("materials")
    if not isinstance(materials, list):
        raise GeneratedSpecularStateError("glTF has no materials list")
    root_t6 = document.setdefault("extras", {}).setdefault("T6", {})
    if ROOT_KEY in root_t6:
        raise GeneratedSpecularStateError("generated layered specular state is already attached")

    generated = 0
    layered_spec_materials = 0
    secondary_layers = 0
    explicit_base = fallback_alpha = fallback_zero = 0
    hashes = []

    for material in materials:
        name = str(material.get("name") or "")
        if not name.startswith("*"):
            continue
        generated += 1
        t6 = material.setdefault("extras", {}).setdefault("T6", {})
        recipe = t6.get("generatedShaderRecipeV1")
        if not isinstance(recipe, dict):
            raise GeneratedSpecularStateError(
                f"generated material {name!r} lacks canonical generatedShaderRecipeV1"
            )
        if recipe.get(RECIPE_KEY) is not None:
            raise GeneratedSpecularStateError(
                f"generated material {name!r} already carries {RECIPE_KEY}"
            )
        attachment = build_attachment(recipe, _dependencies(t6), proof)
        if attachment is None:
            continue
        if attachment["material"] != name:
            raise GeneratedSpecularStateError(
                f"generated material {name!r}: canonical specular attachment identity disagrees"
            )
        recipe[RECIPE_KEY] = attachment
        layered_spec_materials += 1
        secondary_layers += int(attachment["secondarySpecularLayerCount"])
        mode = attachment["baseline"]["mode"]
        if mode == "explicit_specular":
            explicit_base += 1
        elif attachment["baseline"].get("alphaMode") == "baseColorAlpha":
            fallback_alpha += 1
        else:
            fallback_zero += 1
        hashes.append(attachment["attachmentSha256"])

    stats = {
        "generatedMaterialCount": generated,
        "layeredSpecularMaterialCount": layered_spec_materials,
        "secondarySpecularLayerCount": secondary_layers,
        "explicitBaseSpecularMaterialCount": explicit_base,
        "fallbackBaseColorAlphaMaterialCount": fallback_alpha,
        "fallbackZeroAlphaMaterialCount": fallback_zero,
        "attachedStateCount": len(hashes),
        "uniqueStateAttachmentCount": len(set(hashes)),
        "attachmentSetSha256": _jhash(sorted(hashes)),
        "binByteIdentical": True,
    }
    contract = {
        "format": FORMAT,
        "map": MAP,
        "recipeKey": f"material.extras.T6.generatedShaderRecipeV1.{RECIPE_KEY}",
        "stats": stats,
        "sourceProof": str(PROOF_RELATIVE),
        "sourceProofShaderSetSha256": proof.get("sourceSlot4ShaderSetSha256"),
        "policy": (
            "preserve exact generated specular XYZW state and exact texture/factor ownership; physical "
            "channel interpretation remains unassigned until downstream lighting proof closes it"
        ),
    }
    contract["contractSha256"] = _jhash(contract)
    root_t6[ROOT_KEY] = contract
    return document, raw, stats
