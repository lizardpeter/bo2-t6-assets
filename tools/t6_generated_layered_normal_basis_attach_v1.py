#!/usr/bin/env python3
"""Attach exact paired-VS layered-normal basis proof to canonical T6 recipes.

Only recipes with secondary normal-bearing layers are augmented.  Accepted v2
profiles must match the recipe's exact paired VS/PS SHA-256 identities and close:
base=world NORMAL0/PS TC1, X=world TANGENT0/PS TC3, and
Y=cross(normal,tangent)*TANGENT0.w/PS TC2.  Normal-map sample decode remains a
separate proof boundary.  v14 recovery supplies transform-slot ownership.
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
from t6_generated_shader_recipe_contract_v1 import validate_manifest, validate_recipe

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
    layers = sorted(int(step["layerIndex"]) for step in program if bool(step.get("hasNormal")))
    if len(layers) != len(set(layers)):
        raise LayeredNormalBasisAttachError(
            f"{recipe.get('material')!r}: duplicate secondary normal layer"
        )
    return layers


def _normal_binding_crosscheck(recipe: dict, expected_layers: list[int]) -> None:
    binding = recipe.get(NORMAL_BINDING_KEY)
    if not expected_layers:
        if isinstance(binding, dict) and binding.get("secondaryNormalBindings") not in ([], None):
            raise LayeredNormalBasisAttachError(
                f"{recipe.get('material')!r}: normal binding exists for recipe with no secondary normals"
            )
        return
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
        if mode == "direct":
            if row.get("transformSlot") is not None or row.get("attribute") is not None:
                raise LayeredNormalBasisAttachError(
                    f"{recipe.get('material')!r}: direct normal layer carries transform metadata"
                )
        elif mode == "transform2x2":
            slot = int(row.get("transformSlot", -1))
            if slot not in (0, 1) or str(row.get("attribute") or "") != f"_T6_NORMAL_TRANSFORM_{slot}":
                raise LayeredNormalBasisAttachError(
                    f"{recipe.get('material')!r}: malformed transform2x2 binding {row}"
                )
        else:
            raise LayeredNormalBasisAttachError(
                f"{recipe.get('material')!r}: unsupported normal transform mode {mode!r}"
            )


def build_attachment(recipe: dict, basis_proof: dict) -> dict | None:
    canonical = validate_recipe(recipe)
    layers = _secondary_normal_layers(canonical)
    _normal_binding_crosscheck(canonical, layers)
    if not layers:
        return None
    try:
        profile = resolve_exact_basis_profile(canonical, basis_proof)
    except LayeredNormalPlaybackError as exc:
        raise LayeredNormalBasisAttachError(
            f"{canonical.get('material')!r}: exact paired-VS normal basis rejected: {exc}"
        ) from exc
    roles = copy.deepcopy(profile["directRoleMatches"])
    algebra = copy.deepcopy(profile["binormalAlgebra"])
    source_sha = str(basis_proof.get("summary", {}).get("profilesV2Sha256") or "")
    if not source_sha:
        raise LayeredNormalBasisAttachError("v2 basis proof lacks profilesV2Sha256")
    payload = {
        "format": FORMAT,
        "material": canonical["material"],
        "techniqueSet": canonical["techniqueSet"],
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
        "sourceBasisProfilesSha256": source_sha,
        "proofBoundary": (
            "exact canonical paired VS/PS identity + v2 direct NORMAL0/TANGENT0 roles + exact TC2 "
            "cross(normal,tangent)*TANGENT0.w algebra; normal sample decode remains separate"
        ),
    }
    payload["attachmentSha256"] = _jhash({
        "material": payload["material"],
        "techniqueSet": payload["techniqueSet"],
        "vertexShaderSha256": payload["vertexShaderSha256"],
        "pixelShaderSha256": payload["pixelShaderSha256"],
        "secondaryNormalLayers": layers,
        "directRoleMatches": roles,
        "binormalAlgebra": algebra,
        "sourceBasisProfilesSha256": source_sha,
    })
    return payload


def _validate_proof(basis_proof: dict) -> None:
    if basis_proof.get("format") != BASIS_PROOF_FORMAT:
        raise LayeredNormalBasisAttachError(
            f"unsupported basis proof {basis_proof.get('format')!r}"
        )
    if not bool(basis_proof.get("summary", {}).get("allThreeBasisRolesExact")):
        raise LayeredNormalBasisAttachError(
            "basis proof does not close all three physical roles across its target population"
        )


def attach_manifest(recipe_manifest: dict, basis_proof: dict) -> tuple[dict, dict]:
    _validate_proof(basis_proof)
    # First validate the input population, then attach to the actual serialized
    # rows. validate_manifest returns deep copies and therefore must not be used
    # as the mutation target.
    canonical = validate_manifest(recipe_manifest)
    out = copy.deepcopy(recipe_manifest)
    raw_rows = out.get("materials")
    if not isinstance(raw_rows, list):
        raise LayeredNormalBasisAttachError("recipe manifest materials must be a list")
    raw_by_name = {str(row.get("material") or ""): row for row in raw_rows if isinstance(row, dict)}
    if set(raw_by_name) != set(canonical):
        raise LayeredNormalBasisAttachError("serialized/canonical recipe material sets disagree")

    normal_material_count = 0
    attachment_hashes: list[str] = []
    for material, recipe in canonical.items():
        target = raw_by_name[material]
        attachment = build_attachment(recipe, basis_proof)
        if attachment is None:
            target.pop(ATTACHMENT_KEY, None)
            continue
        normal_material_count += 1
        target[ATTACHMENT_KEY] = attachment
        attachment_hashes.append(attachment["attachmentSha256"])

    # Revalidate serialized rows and prove the attachment is physically present
    # after canonicalization rather than only having existed on a temporary copy.
    checked = validate_manifest(out)
    serialized_again = {
        str(row.get("material") or ""): row for row in out["materials"] if isinstance(row, dict)
    }
    for material, canonical_row in checked.items():
        layers = _secondary_normal_layers(canonical_row)
        attachment = serialized_again[material].get(ATTACHMENT_KEY)
        if layers:
            if not isinstance(attachment, dict) or attachment.get("material") != material:
                raise LayeredNormalBasisAttachError(
                    f"{material!r}: basis attachment missing from serialized manifest"
                )
            rebuilt = build_attachment(canonical_row, basis_proof)
            if rebuilt != attachment:
                raise LayeredNormalBasisAttachError(
                    f"{material!r}: serialized basis attachment is not deterministic"
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
    _validate_proof(basis_proof)
    materials = document.get("materials")
    if not isinstance(materials, list):
        raise LayeredNormalBasisAttachError("glTF has no materials list")
    generated = normal = attached = 0
    hashes: list[str] = []
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
        canonical = validate_recipe(recipe, expected_material=name)
        layers = _secondary_normal_layers(canonical)
        attachment = build_attachment(canonical, basis_proof)
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
    if attached != normal:
        raise LayeredNormalBasisAttachError("glTF secondary-normal basis attachment accounting mismatch")
    document.setdefault("extras", {}).setdefault("T6", {})["layeredNormalBasisAttachment"] = {
        "format": FORMAT,
        "stats": stats,
        "policy": "exact paired-VS/PS basis profile attached only to generated recipes with secondary normals",
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
