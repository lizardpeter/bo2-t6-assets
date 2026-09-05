#!/usr/bin/env python3
"""Canonical-recipe Blender/Tour generated-layer preview adapter v3.

v1 introduced the source-backed generated diffuse preview. v2 hardened current
Blender node compatibility. v3 hardens provenance: automatic material recipes
come only from the canonical repository contract:

    material.extras.T6.generatedShaderRecipeV1

An optional external manifest must likewise use
`t6-generated-world-shader-recipe-manifest-v1`. Historical/guessed recipe key
names are deliberately not searched.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import t6_blender_generated_layer_preview_v1 as v1
import t6_blender_generated_layer_preview_v2 as v2
from t6_generated_shader_recipe_contract_v1 import (
    EXTRA_KEY,
    GeneratedShaderRecipeError,
    validate_manifest,
    validate_recipe,
)

bpy = v1.bpy
BlenderLayerPreviewError = v1.BlenderLayerPreviewError


def _recipe_map(sidecar: Path | None) -> dict[str, dict]:
    if sidecar is None:
        return {}
    try:
        doc = json.loads(sidecar.read_text(encoding="utf-8"))
        return validate_manifest(doc)
    except (OSError, ValueError, GeneratedShaderRecipeError) as exc:
        raise BlenderLayerPreviewError(f"invalid canonical generated shader recipe manifest: {exc}") from exc


def _material_technique(name: str, t6: dict, sidecars: dict[str, dict]) -> tuple[str | None, dict | None]:
    sidecar = sidecars.get(name)
    embedded = t6.get(EXTRA_KEY)

    if sidecar is not None and embedded is not None:
        try:
            embedded_valid = validate_recipe(embedded, expected_material=name)
        except GeneratedShaderRecipeError as exc:
            raise BlenderLayerPreviewError(f"{name!r} embedded canonical recipe is invalid: {exc}") from exc
        if sidecar != embedded_valid:
            raise BlenderLayerPreviewError(
                f"{name!r} canonical sidecar and embedded recipe disagree; refusing precedence guess"
            )
        return str(sidecar["techniqueSet"]), sidecar

    if sidecar is not None:
        return str(sidecar["techniqueSet"]), sidecar

    if embedded is not None:
        try:
            row = validate_recipe(embedded, expected_material=name)
        except GeneratedShaderRecipeError as exc:
            raise BlenderLayerPreviewError(f"{name!r} embedded canonical recipe is invalid: {exc}") from exc
        return str(row["techniqueSet"]), row

    return None, None


def apply_preview(input_path: Path, output_blend: Path, *, recipes: Path | None = None, strict: bool = False) -> dict:
    # Patch v1's module-global provenance hooks and v2's current-Blender node
    # compatibility hooks. No recovered T6 equation is changed here.
    v1._recipe_map = _recipe_map
    v1._material_technique = _material_technique
    v1._weight_attribute = v2._weight_attribute
    v1._vertex_weight_socket = v2._vertex_weight_socket

    result = v1.apply_preview(input_path, output_blend, recipes=recipes, strict=strict)
    result["format"] = "t6-blender-generated-layer-preview-v3"
    result["recipeContract"] = f"material.extras.T6.{EXTRA_KEY}"
    result["recipePolicy"] = (
        "canonical embedded recipe or identical canonical sidecar only; no historical-key search"
    )
    result["blenderCompatibility"] = "Separate Color (current) or Separate RGB (legacy)"
    report = output_blend.with_suffix(output_blend.suffix + ".t6_preview.json")
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _argv() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_blend", type=Path)
    parser.add_argument("--recipes", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(_argv())
    result = apply_preview(args.input, args.output_blend, recipes=args.recipes, strict=args.strict)
    print(json.dumps({
        "out": result["output"],
        "generatedMaterialCount": result["generatedMaterialCount"],
        "rebuiltMaterialCount": result["rebuiltMaterialCount"],
        "skippedMaterialCount": result["skippedMaterialCount"],
        "recipeContract": result["recipeContract"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
