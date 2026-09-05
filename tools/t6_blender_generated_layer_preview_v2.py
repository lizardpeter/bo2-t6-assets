#!/usr/bin/env python3
"""Blender compatibility wrapper for the T6 generated-layer preview v1.

v2 preserves v1's fail-closed shader semantics and only hardens the Blender
node API boundary. Current Blender releases expose Separate Color while older
releases may expose Separate RGB. This wrapper accepts either without changing
any T6 layer equation, weight source, texture identity or proof boundary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import t6_blender_generated_layer_preview_v1 as v1

bpy = v1.bpy
BlenderLayerPreviewError = v1.BlenderLayerPreviewError


def _weight_attribute(nodes):
    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "_T6_LAYER_WEIGHTS"
    attr.label = "T6 exact layer controls"
    if attr.outputs.get("Color") is None:
        raise BlenderLayerPreviewError("Blender Attribute node has no Color output")

    try:
        sep = nodes.new("ShaderNodeSeparateColor")
        if hasattr(sep, "mode"):
            sep.mode = "RGB"
        sep.label = "T6 G/B controls (Separate Color)"
    except Exception:
        try:
            sep = nodes.new("ShaderNodeSeparateRGB")
            sep.label = "T6 G/B controls (legacy Separate RGB)"
        except Exception as exc:
            raise BlenderLayerPreviewError(
                "Blender exposes neither Separate Color nor legacy Separate RGB"
            ) from exc
    return attr, sep


def _socket(collection, *names):
    for name in names:
        item = collection.get(name)
        if item is not None:
            return item
    return None


def _vertex_weight_socket(nodes, links, attr, sep, layer: int):
    channel = v1.WEIGHT_OUTPUT.get(layer)
    if channel is None:
        raise BlenderLayerPreviewError(f"unsupported generated layer index {layer}")

    sep_input = _socket(sep.inputs, "Color", "Image")
    if sep_input is None:
        raise BlenderLayerPreviewError("Separate Color/RGB node has no color input")
    # A repeated identical link is harmless in Blender, but avoid creating it
    # more than once when a three/four-layer material requests several weights.
    if not sep_input.is_linked:
        links.new(attr.outputs["Color"], sep_input)

    if channel == "G":
        output = _socket(sep.outputs, "Green", "G")
    elif channel == "B":
        output = _socket(sep.outputs, "Blue", "B")
    else:
        output = attr.outputs.get("Alpha")
    if output is None:
        raise BlenderLayerPreviewError(f"cannot resolve Blender socket for T6 layer channel {channel}")
    return output


def apply_preview(input_path: Path, output_blend: Path, *, recipes: Path | None = None, strict: bool = False) -> dict:
    # v1's builder resolves these helpers as module globals, so replacing only
    # the Blender API shims leaves every recovered T6 equation unchanged.
    v1._weight_attribute = _weight_attribute
    v1._vertex_weight_socket = _vertex_weight_socket
    result = v1.apply_preview(input_path, output_blend, recipes=recipes, strict=strict)
    result["format"] = "t6-blender-generated-layer-preview-v2"
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
        "blenderCompatibility": result["blenderCompatibility"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
