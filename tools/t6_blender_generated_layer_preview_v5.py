#!/usr/bin/env python3
"""Blender generated-layer preview v5: production-attribute trust boundary.

v4 executes exact serialized vN DAGs. v5 keeps that renderer behavior unchanged
and hardens what may enter it:

* the input glTF/GLB must carry ``t6-world-generated-attribute-contract-v1``;
* every generated primitive must therefore expose `_T6_LAYER_WEIGHTS` rather
  than ambiguous legacy COLOR_0;
* logical `_T6_NORMAL_TRANSFORM_N` accessors are the reordered normalized
  renderer form, while `*_RAW` preserves original stored bytes;
* height DAG, constant and leaf payloads must agree on pixel-shader SHA and
  generated Material archive identity.

This is a provenance revision, not a new lighting approximation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import t6_blender_generated_layer_preview_v1 as v1
import t6_blender_generated_layer_preview_v4 as v4
import t6_blender_height_dag_nodes_v1 as height_nodes
from t6_world_generated_attribute_contract_v1 import FORMAT as ATTRIBUTE_FORMAT


bpy = v1.bpy
BlenderLayerPreviewError = v1.BlenderLayerPreviewError


def _root_attribute_preflight(input_path: Path) -> dict:
    try:
        document = v1._read_gltf_json(input_path)
    except Exception as exc:
        raise BlenderLayerPreviewError(
            f"cannot inspect production generated attribute contract: {exc}"
        ) from exc
    contract = document.get("extras", {}).get("T6", {}).get(
        "generatedAttributeContract"
    )
    if not isinstance(contract, dict) or contract.get("format") != ATTRIBUTE_FORMAT:
        raise BlenderLayerPreviewError(
            f"input lacks authoritative {ATTRIBUTE_FORMAT}; refuse legacy/ambiguous generated attributes"
        )
    stats = contract.get("stats")
    if not isinstance(stats, dict):
        raise BlenderLayerPreviewError("generated attribute contract lacks stats")
    generated = int(stats.get("generatedPrimitiveCount", -1))
    retyped = int(stats.get("generatedColorRetypeCount", -2))
    if generated < 0 or generated != retyped:
        raise BlenderLayerPreviewError(
            f"generated attribute contract layer-weight accounting mismatch {generated}/{retyped}"
        )
    return contract


def _strict_height_identity_preflight(material: str, technique: str, recipe: dict, layer: int):
    plan = v4._height_identity_preflight(material, technique, recipe, layer)
    height = recipe[height_nodes.HEIGHT_DAG_KEY]
    constants = recipe[height_nodes.HEIGHT_CONSTANT_KEY]
    leaves = recipe[height_nodes.HEIGHT_LEAF_KEY]
    shader_sha = str(height.get("pixelShaderSha256") or "")
    if not shader_sha:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: height DAG lacks pixel-shader SHA"
        )
    if str(constants.get("dxbcSha256") or "") != shader_sha:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: constant DXBC SHA disagrees with height DAG"
        )
    if str(leaves.get("pixelShaderSha256") or "") != shader_sha:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: leaf-binding pixel-shader SHA disagrees with height DAG"
        )
    constant_archive = str(constants.get("materialArchiveSha256") or "")
    leaf_archive = str(leaves.get("materialArchiveSha256") or "")
    if not constant_archive or constant_archive != leaf_archive:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: constant/leaf Material archive identity disagrees"
        )
    if str(leaves.get("constantBindingsKey") or "") != height_nodes.HEIGHT_CONSTANT_KEY:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: leaf payload does not bind canonical constant contract"
        )
    return plan


def apply_preview(
    input_path: Path,
    output_blend: Path,
    *,
    recipes: Path | None = None,
    strict: bool = False,
) -> dict:
    contract = _root_attribute_preflight(input_path)
    old_preflight = v4._height_identity_preflight
    v4._height_identity_preflight = _strict_height_identity_preflight
    try:
        result = v4.apply_preview(
            input_path, output_blend, recipes=recipes, strict=strict
        )
    finally:
        v4._height_identity_preflight = old_preflight

    result["format"] = "t6-blender-generated-layer-preview-v5"
    result["attributeContract"] = ATTRIBUTE_FORMAT
    result["attributeContractSha256"] = contract.get("contractSha256")
    result["attributeContractStats"] = contract.get("stats")
    result["provenancePolicy"] = (
        "requires production normalized generated attributes and cross-consistent "
        "height shader/DXBC/leaf/Material-archive identities"
    )
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
    result = apply_preview(
        args.input, args.output_blend, recipes=args.recipes, strict=args.strict
    )
    print(json.dumps({
        "out": result["output"],
        "generatedMaterialCount": result["generatedMaterialCount"],
        "rebuiltMaterialCount": result["rebuiltMaterialCount"],
        "heightDagCompiledLayerCount": result["heightDagCompiledLayerCount"],
        "attributeContract": result["attributeContract"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
