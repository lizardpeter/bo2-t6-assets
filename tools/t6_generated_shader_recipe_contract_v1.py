#!/usr/bin/env python3
"""Canonical serialized contract for recovered T6 generated-world shader recipes.

This is intentionally separate from generated material-name parsing. A compound
name proves layer/component identity; it does NOT prove the retail TechniqueSet
or pixel-shader archetype. The recipe contract only accepts those identities
when they were recovered independently from retail evidence.

Canonical glTF location:

    material.extras.T6.generatedShaderRecipeV1

Manifest format:

    t6-generated-world-shader-recipe-manifest-v1

The contract is deliberately renderer-neutral. Blender, Tour/wgpu and future
exporters may consume it, but none may reinterpret its fields as generic PBR
without a separately proven mapping.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
from typing import Iterable

from t6_generated_world_shader_semantics_v1 import (
    layer_weight_class,
    parse_generated_layer_tokens,
)


FORMAT = "t6-generated-world-shader-recipe-manifest-v1"
EXTRA_KEY = "generatedShaderRecipeV1"


class GeneratedShaderRecipeError(RuntimeError):
    pass


def _nonempty(value, field: str) -> str:
    text = str(value or "")
    if not text:
        raise GeneratedShaderRecipeError(f"empty {field}")
    return text


def canonical_layer_program(technique_set: str) -> list[dict]:
    """Derive the renderer-facing layer program from an exact TechniqueSet.

    This derives only syntax whose semantics are already source-closed. It does
    not invent a height DAG for vN or a downstream PBR interpretation.
    """
    tokens = parse_generated_layer_tokens(technique_set)
    return [
        {
            "layerIndex": token.layer,
            "operation": token.operation,
            "weightClass": layer_weight_class(token),
            "hasNormal": token.has_normal,
            "hasSpecular": token.has_specular,
            "xVariant": token.x_variant,
            "heightVariant": token.height_variant,
        }
        for token in tokens
    ]


def validate_recipe(recipe: dict, *, expected_material: str | None = None) -> dict:
    material = _nonempty(recipe.get("material"), "material")
    if expected_material is not None and material != expected_material:
        raise GeneratedShaderRecipeError(
            f"recipe material {material!r} != expected {expected_material!r}"
        )
    if not material.startswith("*"):
        raise GeneratedShaderRecipeError(
            f"generated shader recipe material must be a compound '*' material: {material!r}"
        )

    technique = _nonempty(recipe.get("techniqueSet"), f"{material} techniqueSet")
    pixel_shader = _nonempty(
        recipe.get("pixelShaderArchetype"), f"{material} pixelShaderArchetype"
    )

    program = canonical_layer_program(technique)
    if not program:
        raise GeneratedShaderRecipeError(
            f"{material!r} TechniqueSet has no generated secondary-layer program"
        )

    supplied = recipe.get("layerProgram")
    if supplied is not None and supplied != program:
        raise GeneratedShaderRecipeError(
            f"{material!r} serialized layerProgram disagrees with exact TechniqueSet grammar"
        )

    formats = recipe.get("worldVertFormats", [])
    if not isinstance(formats, list) or not formats:
        raise GeneratedShaderRecipeError(
            f"{material!r} must record at least one observed worldVertFormat"
        )
    normalized_formats = sorted({int(v) for v in formats})
    if any(v < 0 for v in normalized_formats):
        raise GeneratedShaderRecipeError(f"{material!r} has negative worldVertFormat")

    proof = recipe.get("proof")
    if not isinstance(proof, dict) or not proof:
        raise GeneratedShaderRecipeError(
            f"{material!r} must carry non-empty retail proof metadata"
        )

    out = copy.deepcopy(recipe)
    out["material"] = material
    out["techniqueSet"] = technique
    out["pixelShaderArchetype"] = pixel_shader
    out["worldVertFormats"] = normalized_formats
    out["layerProgram"] = program
    out["contract"] = "source-closed generated layer program; downstream lighting remains separate"
    return out


def validate_manifest(manifest: dict) -> dict[str, dict]:
    if manifest.get("format") != FORMAT:
        raise GeneratedShaderRecipeError(
            f"unsupported generated shader recipe manifest {manifest.get('format')!r}"
        )
    rows = manifest.get("materials")
    if not isinstance(rows, list):
        raise GeneratedShaderRecipeError("recipe manifest materials must be a list")

    by_name: dict[str, dict] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise GeneratedShaderRecipeError("recipe manifest row is not an object")
        row = validate_recipe(raw)
        name = row["material"]
        if name in by_name:
            raise GeneratedShaderRecipeError(f"duplicate generated shader recipe {name!r}")
        by_name[name] = row
    return by_name


def attach_recipes(
    gltf: dict,
    manifest: dict,
    *,
    require_all_generated_materials: bool = True,
    reject_unused_recipes: bool = True,
) -> dict:
    """Attach canonical recipes by exact material-name join, fail-closed."""
    recipe_by_name = validate_manifest(manifest)
    used: set[str] = set()
    missing: list[str] = []
    generated_count = 0

    for material in gltf.get("materials", []):
        name = str(material.get("name") or "")
        if not name.startswith("*"):
            continue
        generated_count += 1
        recipe = recipe_by_name.get(name)
        if recipe is None:
            missing.append(name)
            continue
        t6 = material.setdefault("extras", {}).setdefault("T6", {})
        if EXTRA_KEY in t6:
            raise GeneratedShaderRecipeError(
                f"{name!r} already contains {EXTRA_KEY}; refusing ambiguous overwrite"
            )
        t6[EXTRA_KEY] = copy.deepcopy(recipe)
        t6["generatedShaderRecipeJoin"] = "exact material-name match"
        used.add(name)

    unused = sorted(set(recipe_by_name) - used)
    if require_all_generated_materials and missing:
        raise GeneratedShaderRecipeError(
            f"missing recipes for {len(missing)} generated materials; first={missing[0]!r}"
        )
    if reject_unused_recipes and unused:
        raise GeneratedShaderRecipeError(
            f"{len(unused)} recipe rows did not match output materials; first={unused[0]!r}"
        )

    root = gltf.setdefault("extras", {}).setdefault("T6", {})
    root["generatedShaderRecipes"] = {
        "format": FORMAT,
        "extraKey": f"material.extras.T6.{EXTRA_KEY}",
        "generatedMaterialCount": generated_count,
        "attachedRecipeCount": len(used),
        "missingGeneratedMaterials": missing,
        "unusedRecipeMaterials": unused,
        "joinPolicy": "exact material name only; no generated-name/TechniqueSet inference",
    }
    return {
        "generatedMaterialCount": generated_count,
        "attachedRecipeCount": len(used),
        "missingGeneratedMaterials": missing,
        "unusedRecipeMaterials": unused,
    }
