#!/usr/bin/env python3
"""Portable T6 textured world glTF/GLB v3 with canonical shader recipes.

v3 is intentionally a wrapper around v2. v1/v2 remain unchanged for checkpoint
stability. v3 adds exactly one new responsibility: after v2 has exported exact
material texture dependencies, attach independently recovered generated-world
shader recipes at:

    material.extras.T6.generatedShaderRecipeV1

The join is exact material name only and defaults fail-closed: every generated
'*' material must have exactly one recipe and every supplied recipe must match
an exported generated material.
"""
from __future__ import annotations

from pathlib import Path

from t6_generated_shader_recipe_contract_v1 import attach_recipes
from t6_world_textured_gltf_export_v2 import (
    TexturedExportError,
    export_textured as export_v2,
    validate_textured,
)


def export_textured(
    world: dict,
    material_manifest: dict,
    texture_stage_manifest: dict,
    generated_shader_recipe_manifest: dict,
    *,
    stage_root: Path,
    material_manifest_sha256: str | None = None,
    allow_missing_preview_textures: bool = False,
    allow_missing_dependency_textures: bool = False,
    require_all_generated_shader_recipes: bool = True,
    reject_unused_shader_recipes: bool = True,
) -> tuple[dict, bytes]:
    gltf, raw = export_v2(
        world,
        material_manifest,
        texture_stage_manifest,
        stage_root=stage_root,
        material_manifest_sha256=material_manifest_sha256,
        allow_missing_preview_textures=allow_missing_preview_textures,
        allow_missing_dependency_textures=allow_missing_dependency_textures,
    )

    stats = attach_recipes(
        gltf,
        generated_shader_recipe_manifest,
        require_all_generated_materials=require_all_generated_shader_recipes,
        reject_unused_recipes=reject_unused_shader_recipes,
    )
    gltf["extras"]["T6"]["exportStats"].update(
        {
            "generatedShaderRecipeMaterialCount": stats["generatedMaterialCount"],
            "attachedGeneratedShaderRecipeCount": stats["attachedRecipeCount"],
            "missingGeneratedShaderRecipeCount": len(stats["missingGeneratedMaterials"]),
            "unusedGeneratedShaderRecipeCount": len(stats["unusedRecipeMaterials"]),
        }
    )
    validate_textured(gltf, raw)
    return gltf, raw
