#!/usr/bin/env python3
"""Attach exact paired-VS layered-normal basis proof to canonical T6 recipes.

This is the recipe/artifact trust-boundary companion to
`t6_generated_layered_normal_vs_basis_probe_v2.py`.

Only generated recipes that actually contain secondary normal-bearing layers are
augmented.  A profile is accepted only when the canonical recipe's exact paired
VS and PS SHA-256 identities match the v2 proof and all three physical basis
roles are closed:

    base = world NORMAL0 / PS TEXCOORD1
    X    = world TANGENT0 / PS TEXCOORD3
    Y    = cross(normal,tangent) * TANGENT0.w / PS TEXCOORD2

The resulting attachment is deliberately compact and renderer-facing.  It does
not add a normal-map sample decode equation and it does not guess transform-slot
ownership; v14/recovery-v6 already carries `normalTransformBindingsV1` for that.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_generated_layered_normal_playback_v1 import (
    BASIS_PROOF_FORMAT,
    LayeredNormalPlaybackError,
    resolve_exact_basis_profile,
)
from t6_generated_shader_recipe_contract_v1 import validate_manifest


FORMAT = "t6-generated-layered-normal-basis-recipe-v1"
ATTACHMENT_KEY = "layeredNormalBasisV1"
NORMAL_BINDING_KEY = "normalTransformBindingsV1"
CANONICAL_RECIPE_KEY = "generatedShaderRecipeV1"


class LayeredNormalBasisAttachError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _secondary_normal_layers(recipe: dict) -> list[int]:
    program = recipe.get("layerProgram")
    if not isinstance(program, list):
        raise LayeredNormalBasisAttachError(
            f"{recipe.get('material')!r}: canonical recipe lacks layerProgram"
        )
    layers = sorted(
        int(step["layerIndex"])
        for step in program
        if bool(step.get("hasNormal"))
    )
    if len(layers) != len(set(layers)):
        raise LayeredNormalBasisAttachError(
            f"{recipe.get('material')!r}: duplicate secondary normal layer"
        )
    return layers


def _normal_binding_crosscheck(recipe: dict, expected_layers: list[int]) -> dict:
    binding = recipe.get(NORMAL_BINDING_KEY)
    if not expected_layers:
        if binding is not None:
            rows = binding.get("secondaryNormalBindings", []) if isinstance(binding, dict) else None
            if rows not in ([], None):
                raise LayeredNormalBasisAttachError(
                    f"{recipe.get('material')!r}: normal binding exists for a recipe with no secondary normals"
                )
        return {}
    if not isinstance(binding, dict):
        raise LayeredNormalBasisAttachError(
            f"{recipe.get('material')!r}: secondary normals require v14 normalTransformBindingsV1"
        )
    rows = binding.get("secondaryNormalBindings")
    if not isinstance(rows, list):
        raise LayeredNormalBasisAttachError(
            f"{recipe.get('material')!r}: normal transform binding has no secondaryNormalBindings"
        )
    bound_layers = sorted(int(row["layerIndex"]) for row in rows)
    if bound_layers != expected_layers:
        raise LayeredNormalBasisAttachError(
            f"{recipe.get('material')!r}: transform binding layers {bound_layers} != recipe normal layers {expected_layers}"
        )
    for row in rows:
        mode = str(row.get("mode") or "")
        if mode not in ("direct", "transform2x2"):
            raise LayeredNormalBasisAttachError(
                f"{recipe.get('material')!r}: unsupported normal transform mode {mode!r}"
            )
        if mode == "direct":
            if row.get("transformSlot") is not None or row.get("attribute") is not None:
                raise LayeredNormalBasisAttachError(
                    f"{recipe.get('material')!r}: direct normal layer carries a transform attribute"
                )
        else:
            slot = int(row.get("transformSlot", -1))
            expected_attribute = f"_T6_NORMAL_TRANSFORM_{slot}"
            if slot not in (0, 1) or str(row.get("attribute") or "") != expected_attribute:
                raise LayeredNormalBasisAttachError(
                    f"{recipe.get('material')!r}: malformed transform2x2 binding {row}"
                )
    return binding


def build_attachment(recipe: dict, basis_proof: dict) -> dict | None:
    layers = _secondary_normal_layers(recipe)
    _normal_binding_crosscheck(recipe, layers)
    if not layers:
        return None
    try:
        profile = resolve_exact_basis_profile(recipe, basis_proof)
    except LayeredNormalPlaybackError as exc:
        raise LayeredNormalBasisAttachError(
            f"{recipe.get('material')!r}: exact paired-VS normal basis rejected: {exc}"
        ) from exc

    roles = copy.deepcopy(profile["directRoleMatches"])
    algebra = copy.deepcopy(profile["binormalAlgebra"])
    payload = {
        "format": FORMAT,
        "material": str(recipe.get("material") or ""),
        "techniqueSet": str(recipe.get("techniqueSet") or ""),
        "vertexShaderSha256": str(profile["vertexShaderSha256"]),
        "pixelShaderSha256": str(profile["pixelShaderSha256"]),
        "secondaryNormalLayers": layers,
        "basis": {
            "base": "world NORMAL0 -> paired VS -> PS TEXCOORD1.xyz",
            "x": "world TANGENT0 -> paired VS -> PS TEXCOORD3.xyz",
            "y": "cross(worldNormal,worldTangent)*TANGENT0.w -> paired VS -> PS TEXCOORD2.xyz",
        },
        "directRoleMatches": roles,
        "binormalAlgebra": algebra,
        "sourceBasisProofFormat": BASIS_PROOF_FORMAT,
        "sourceBasisProfilesSha256": str(
            basis_proof.get("summary", {}).get("profilesV2Sha256") or ""
        ),
        "proofBoundary": (
            "exact canonical paired VS/PS identity + v2 direct NORMAL0/TANGENT0 output roles + exact "
            "TC2 cross(normal,tangent)*TANGENT0.w algebra; normal sample decode remains separate"
        ),
    }
    if not payload["material"] or not payload["techniqueSet"]:
        raise LayeredNormalBasisAttachError("canonical recipe has empty material/TechniqueSet")
    if not payload["sourceBasisProfilesSha256"]:
        raise LayeredNormalBasisAttachError("v2 basis proof lacks profilesV2Sha256")
    payload["attachmentSha256"] = _jhash({
        "material": payload["material"],
        "techniqueSet": payload["techniqueSet"],
        "vertexShaderSha256": payload["vertexShaderSha256"],
        "pixelShaderSha256": payload["pixelShaderSha256"],
        "secondaryNormalLayers": layers,
        "directRoleMatches": roles,
        "binormalAlgebra": algebra,
        "sourceBasisProfilesSha256": payload["sourceBasisProfilesSha256"],
    })
    return payload


def attach_manifest(recipe_manifest: dict, basis_proof: dict) -> tuple[dict, dict]:
    if basis_proof.get("format") != BASIS_PROOF_FORMAT:
        raise LayeredNormalBasisAttachError(
            f"unsupported basis proof {basis_proof.get('format')!r}"
        )
    if not bool(basis_proof.get("summary", {}).get("allThreeBasisRolesExact")):
        raise LayeredNormalBasisAttachError(
            "basis proof does not close all three physical roles across its target population"
        )
    out = copy.deepcopy(recipe_manifest)
    validated = validate_manifest(out)
    normal_material_count = 0
    attachment_hashes = []
    for material, recipe in validated.items():
        attachment = build_attachment(recipe, basis_proof)
        if attachment is None:
            recipe.pop(ATTACHMENT_KEY, None)
            continue
        normal_material_count += 1
        recipe[ATTACHMENT_KEY] = attachment
        attachment_hashes.append(attachment["attachmentSha256"])

    # validate_manifest returns the same row objects from `out`; assert that the
    # attachment survived and no material identity was silently remapped.
    checked = validate_manifest(out)
    for material, recipe in checked.items():
        layers = _secondary_normal_layers(recipe)
        attachment = recipe.get(ATTACHMENT_KEY)
        if layers:
            if not isinstance(attachment, dict) or attachment.get("material") != material:
                raise LayeredNormalBasisAttachError(
                    f"{material!r}: basis attachment missing after canonical validation"
                )
        elif attachment is not None:
            raise LayeredNormalBasisAttachError(
                f"{material!r}: non-normal recipe unexpectedly retained a basis attachment"
            )

    stats = {
        "generatedRecipeCount": len(checked),
        "secondaryNormalRecipeCount": normal_material_count,
        "attachedBasisCount": len(attachment_hashes),
        "allSecondaryNormalRecipesAttached": normal_material_count == len(attachment_hashes),
        "uniqueAttachmentCount": len(set(attachment_hashes)),
        "attachmentSetSha256": _jhash(sorted(attachment_hashes)),
        "sourceBasisProfilesSha256": str(basis_proof["summary"]["profilesV2Sha256"]),
    }
    if not stats["allSecondaryNormalRecipesAttached"]:
        raise LayeredNormalBasisAttachError("secondary normal basis attachment accounting mismatch")
    return out, stats


def attach_gltf(document: dict, basis_proof: dict) -> dict:
    """Attach exact basis profiles to recipes already embedded in a v14+ glTF."""
    if basis_proof.get("format") != BASIS_PROOF_FORMAT:
        raise LayeredNormalBasisAttachError(
            f"unsupported basis proof {basis_proof.get('format')!r}"
        )
    if not bool(basis_proof.get("summary", {}).get("allThreeBasisRolesExact")):
        raise LayeredNormalBasisAttachError("basis proof is not globally exact")
    materials = document.get("materials")
    if not isinstance(materials, list):
        raise LayeredNormalBasisAttachError("glTF has no materials list")
    generated = normal = attached = 0
    hashes = []
    for gltf_material in materials:
        name = str(gltf_material.get("name") or "")
        if not name.startswith("*"):
            continue
        generated += 1
        t6 = gltf_material.get("extras", {}).get("T6", {})
        recipe = t6.get(CANONICAL_RECIPE_KEY)
        if not isinstance(recipe, dict):
            raise LayeredNormalBasisAttachError(
                f"generated glTF material {name!r} lacks canonical {CANONICAL_RECIPE_KEY}"
            )
        if str(recipe.get("material") or "") != name:
            raise LayeredNormalBasisAttachError(
                f"generated glTF material {name!r} recipe identity disagrees"
            )
        layers = _secondary_normal_layers(recipe)
        attachment = build_attachment(recipe, basis_proof)
        if layers:
            normal += 1
            if attachment is None:
                raise LayeredNormalBasisAttachError(f"{name!r}: basis attachment unexpectedly null")
            recipe[ATTACHMENT_KEY] = attachment
            attached += 1
            hashes.append(attachment["attachmentSha256"])
        else:
            recipe.pop(ATTACHMENT_KEY, None)
    stats = {
        "generatedMaterialCount": generated,
        "secondaryNormalMaterialCount": normal,
        "attachedBasisCount": attached,
        "allSecondaryNormalMaterialsAttached": attached == normal,
        "uniqueAttachmentCount": len(set(hashes)),
        "attachmentSetSha256": _jhash(sorted(hashes)),
        "sourceBasisProfilesSha256": str(basis_proof["summary"]["profilesV2Sha256"]),
    }
    document.setdefault("extras", {}).setdefault("T6", {})["layeredNormalBasisAttachment"] = {
        "format": FORMAT,
        "stats": stats,
        "policy": (
            "exact paired-VS/PS basis profile attached only to canonical generated recipes with secondary normals"
        ),
    }
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--basis-proof", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    recipes = json.loads(args.recipes.read_text(encoding="utf-8"))
    proof = json.loads(args.basis_proof.read_text(encoding="utf-8"))
    out, stats = attach_manifest(recipes, proof)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(stats, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
