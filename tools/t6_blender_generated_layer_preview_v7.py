#!/usr/bin/env python3
"""Blender generated-layer preview v7: explicit custom-basis axis conversion.

v7 preserves v6's complete generated diffuse/vN/layered-normal graph and changes
only one importer boundary: v20 `_T6_WORLD_NORMAL/_T6_WORLD_TANGENT/
_T6_WORLD_BINORMAL` are application attributes containing glTF-space numeric
vectors, so v7 explicitly maps `(x,y,z)->(x,-z,y)` before Blender OBJECT->WORLD.

This avoids depending on whether a Blender glTF importer version applies the
built-in NORMAL/TANGENT semantic coordinate conversion to arbitrary underscore
custom attributes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import t6_blender_generated_layer_preview_v6 as v6
import t6_blender_generated_normal_nodes_v2 as normal_v2

bpy = v6.bpy
BlenderLayerPreviewError = v6.BlenderLayerPreviewError


def apply_preview(
    input_path: Path,
    output_blend: Path,
    *,
    recipes: Path | None = None,
    strict: bool = False,
) -> dict:
    old_reconstruct = v6.normal_nodes.reconstruct_world_normal
    v6.normal_nodes.reconstruct_world_normal = normal_v2.reconstruct_world_normal
    try:
        result = v6.apply_preview(
            input_path, output_blend, recipes=recipes, strict=strict
        )
    finally:
        v6.normal_nodes.reconstruct_world_normal = old_reconstruct

    result["format"] = "t6-blender-generated-layer-preview-v7"
    result["normalBasisCoordinateSpace"] = "glTF custom attribute vectors"
    result["normalBasisGltfToBlender"] = [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ]
    result["normalBasisCoordinatePolicy"] = (
        "explicit (x,y,z)_gltf -> (x,-z,y)_BlenderObject before OBJECT->WORLD; "
        "do not depend on importer semantic conversion of custom underscore attributes"
    )
    result["proofBoundary"] = (
        result.get("proofBoundary", "")
        + " Custom N/T/B application attributes are explicitly converted from glTF Y-up to Blender Z-up axes."
    ).strip()
    report = output_blend.with_suffix(output_blend.suffix + ".t6_preview.json")
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _argv() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1:]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    p.add_argument("output_blend", type=Path)
    p.add_argument("--recipes", type=Path)
    p.add_argument("--strict", action="store_true")
    a = p.parse_args(_argv())
    result = apply_preview(a.input, a.output_blend, recipes=a.recipes, strict=a.strict)
    print(json.dumps({
        "out": result["output"],
        "generatedMaterialCount": result["generatedMaterialCount"],
        "rebuiltMaterialCount": result["rebuiltMaterialCount"],
        "normalPlaybackMaterialCount": result["normalPlaybackMaterialCount"],
        "normalPlaybackLayerCount": result["normalPlaybackLayerCount"],
        "normalBasisCoordinatePolicy": result["normalBasisCoordinatePolicy"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
