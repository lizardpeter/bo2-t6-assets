#!/usr/bin/env python3
"""Blender generated-layer preview v4: execute exact serialized T6 vN DAGs.

v4 preserves v3 canonical recipe provenance, v2 Blender node compatibility and
v1's exact encoded-domain generated diffuse compositor. The only semantic
extension is the previously refused ``vN`` height-weight path: v4 compiles the
forensic scalar DAG embedded by recipe recovery v4 into Blender Math nodes using
its exact per-Material constants and exact nonconstant leaf bindings.

This is still an authoring preview. The serialized retail equation/topology and
source values are preserved, but Blender's shader backend is not claimed to be
bit-identical to D3D11 floating-point execution. T6 normal/specular/lightmap/
reflection output remains outside Principled until its final composition is
source-closed and integrated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import t6_blender_generated_layer_preview_v1 as v1
import t6_blender_generated_layer_preview_v2 as v2
import t6_blender_generated_layer_preview_v3 as v3
import t6_blender_height_dag_nodes_v1 as height_nodes
from t6_generated_world_shader_semantics_v1 import layer_weight_class, parse_generated_layer_tokens


bpy = v1.bpy
BlenderLayerPreviewError = v1.BlenderLayerPreviewError


def _height_identity_preflight(material: str, technique: str, recipe: dict, layer: int):
    height = recipe.get(height_nodes.HEIGHT_DAG_KEY)
    constants = recipe.get(height_nodes.HEIGHT_CONSTANT_KEY)
    leaves = recipe.get(height_nodes.HEIGHT_LEAF_KEY)
    if not isinstance(height, dict) or not isinstance(constants, dict) or not isinstance(leaves, dict):
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: canonical recipe lacks complete vN DAG/constant/leaf contracts"
        )
    if str(height.get("techniqueSet") or "") != technique:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: height DAG TechniqueSet disagrees with canonical recipe"
        )
    recipe_shader = str(recipe.get("pixelShaderArchetype") or "")
    dag_shader = str(height.get("pixelShaderSha256") or "")
    if recipe_shader != f"sha256:{dag_shader}":
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: height DAG pixel-shader SHA disagrees with canonical recipe"
        )
    for label, payload in (("constant", constants), ("leaf", leaves)):
        payload_material = payload.get("material")
        if payload_material is not None and str(payload_material) != material:
            raise BlenderLayerPreviewError(
                f"{material!r} layer {layer}: height {label} payload belongs to {payload_material!r}"
            )
        payload_technique = payload.get("techniqueSet")
        if payload_technique is not None and str(payload_technique) != technique:
            raise BlenderLayerPreviewError(
                f"{material!r} layer {layer}: height {label} TechniqueSet disagrees"
            )
        payload_shader = payload.get("pixelShaderArchetype")
        if payload_shader is not None and str(payload_shader) != recipe_shader:
            raise BlenderLayerPreviewError(
                f"{material!r} layer {layer}: height {label} pixel-shader identity disagrees"
            )
    try:
        return height_nodes.prepare_height_dag_plan(recipe, layer)
    except height_nodes.BlenderHeightDagError as exc:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {layer}: exact vN recipe preflight failed: {exc}"
        ) from exc


def _height_factor(nodes, links, *, material: str, technique: str, recipe: dict, token, color_tex, attr, sep):
    plan = _height_identity_preflight(material, technique, recipe, token.layer)
    vertex = v2._vertex_weight_socket(nodes, links, attr, sep, token.layer)
    alpha = color_tex.outputs.get("Alpha")
    if alpha is None:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {token.layer}: Blender image texture has no Alpha output"
        )
    sample_sockets = {key: alpha for key in plan.sample_leaves}
    try:
        factor = height_nodes.compile_height_dag(
            nodes,
            links,
            plan,
            vertex_socket=vertex,
            sample_sockets=sample_sockets,
        )
    except height_nodes.BlenderHeightDagError as exc:
        raise BlenderLayerPreviewError(
            f"{material!r} layer {token.layer}: exact vN Blender compilation failed: {exc}"
        ) from exc
    return factor, plan


def _build_material_v4(blender_material, gltf_material: dict, technique: str, recipe: dict | None, image_cache: dict) -> dict:
    t6 = gltf_material.get("extras", {}).get("T6", {})
    deps = v1._embedded_dependencies(t6)
    tokens = parse_generated_layer_tokens(technique)
    if not tokens:
        raise BlenderLayerPreviewError("TechniqueSet contains no secondary generated layers")

    material_name = str(gltf_material.get("name") or blender_material.name)
    base_dep = v1._role_dependency(deps, 0, "colorMap")
    base_source = v1._source(
        base_dep, material=material_name, layer=0, role="colorMap", required=True
    )

    layer_sources: dict[int, str] = {}
    height_plans: dict[int, object] = {}
    for token in tokens:
        dep = v1._role_dependency(deps, token.layer, "colorMap")
        layer_sources[token.layer] = v1._source(
            dep,
            material=material_name,
            layer=token.layer,
            role="colorMap",
            required=True,
        )
        if token.height_variant:
            if recipe is None:
                raise BlenderLayerPreviewError(
                    f"{material_name!r} uses v{token.layer} but has no canonical generated shader recipe"
                )
            height_plans[token.layer] = _height_identity_preflight(
                material_name, technique, recipe, token.layer
            )

    blender_material.use_nodes = True
    tree = blender_material.node_tree
    nodes, links = tree.nodes, tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1100, 0)
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (850, 0)
    principled.label = "Blender lighting preview ONLY"
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    base_tex = v1._wire_tex(nodes, links, base_source, "colorMap", 0, image_cache)
    base_tex.location = (-1400, 300)
    composed = base_tex.outputs["Color"]

    attr, sep = v2._weight_attribute(nodes)
    attr.location = (-1400, -450)
    sep.location = (-1200, -450)

    layer_nodes = []
    height_dag_rows = []
    for order, token in enumerate(tokens):
        tex = v1._wire_tex(
            nodes, links, layer_sources[token.layer], "colorMap", token.layer, image_cache
        )
        tex.location = (-1120 + order * 55, 250 - token.layer * 190)
        cls = layer_weight_class(token)
        if cls == "height":
            if recipe is None:
                raise BlenderLayerPreviewError(
                    f"{material_name!r} layer {token.layer}: missing canonical recipe for vN"
                )
            factor, plan = _height_factor(
                nodes,
                links,
                material=material_name,
                technique=technique,
                recipe=recipe,
                token=token,
                color_tex=tex,
                attr=attr,
                sep=sep,
            )
            height_dag_rows.append({
                "layer": token.layer,
                "forensicDagSha256": plan.forensic_sha256,
                "rawVertexInputs": list(plan.vertex_leaf_names),
                "normalizedWeightComponent": plan.raw_vertex_component,
                "sampleLeaves": [list(key) for key in plan.sample_leaves],
                "constantLeafCount": len(plan.constant_values),
            })
        else:
            factor = v1._exact_weight(nodes, links, token, tex, attr, sep)

        composed = v1._compose(
            nodes,
            links,
            composed,
            tex.outputs["Color"],
            factor,
            token.operation,
            token.layer,
        )
        layer_nodes.append({
            "layer": token.layer,
            "operation": token.operation,
            "weightClass": cls,
            "hasNormal": token.has_normal,
            "hasSpecular": token.has_specular,
            "heightDagCompiled": cls == "height",
        })

    linear_preview = v1._square_rgb(nodes, links, composed)
    links.new(linear_preview, principled.inputs["Base Color"])

    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.5

    spec_sources = []
    normal_sources = []
    for layer in range(4):
        spec = v1._role_dependency(deps, layer, "specularMap")
        normal = v1._role_dependency(deps, layer, "normalMap")
        if spec is not None:
            spec_sources.append({
                "layer": layer,
                "sourceTexture": v1._source(
                    spec,
                    material=material_name,
                    layer=layer,
                    role="specularMap",
                    required=False,
                ),
            })
        if normal is not None:
            normal_sources.append({
                "layer": layer,
                "sourceTexture": v1._source(
                    normal,
                    material=material_name,
                    layer=layer,
                    role="normalMap",
                    required=False,
                ),
            })

    blender_material["T6_preview_status"] = (
        "exact generated diffuse through RGB-square including serialized vN DAG; Blender downstream lighting"
    )
    blender_material["T6_technique_set"] = technique
    blender_material["T6_layer_steps_json"] = json.dumps(layer_nodes, sort_keys=True)
    blender_material["T6_height_dags_json"] = json.dumps(height_dag_rows, sort_keys=True)
    blender_material["T6_layered_specular_dependencies_json"] = json.dumps(spec_sources, sort_keys=True)
    blender_material["T6_layered_normal_dependencies_json"] = json.dumps(normal_sources, sort_keys=True)
    blender_material["T6_preview_proof_boundary"] = (
        "exact source-backed A/B/M/T encoded-domain compositor including shader-specific vN DAG topology, "
        "exact per-Material constants, exact normalized layer-weight/sample bindings and explicit RGB square; "
        "Blender math backend rounding is not claimed bit-identical to retail D3D11; Principled lighting is "
        "preview-only and T6 specular/normal/lightmap/reflection are not silently PBR-remapped"
    )
    return {
        "layers": layer_nodes,
        "heightDagCount": len(height_dag_rows),
        "heightDags": height_dag_rows,
        "specularDependencies": len(spec_sources),
        "normalDependencies": len(normal_sources),
    }


def apply_preview(
    input_path: Path,
    output_blend: Path,
    *,
    recipes: Path | None = None,
    strict: bool = False,
) -> dict:
    old = {
        "recipe_map": v1._recipe_map,
        "material_technique": v1._material_technique,
        "weight_attribute": v1._weight_attribute,
        "vertex_weight_socket": v1._vertex_weight_socket,
        "build_material": v1._build_material,
    }
    v1._recipe_map = v3._recipe_map
    v1._material_technique = v3._material_technique
    v1._weight_attribute = v2._weight_attribute
    v1._vertex_weight_socket = v2._vertex_weight_socket
    v1._build_material = _build_material_v4
    try:
        result = v1.apply_preview(
            input_path, output_blend, recipes=recipes, strict=strict
        )
    finally:
        v1._recipe_map = old["recipe_map"]
        v1._material_technique = old["material_technique"]
        v1._weight_attribute = old["weight_attribute"]
        v1._vertex_weight_socket = old["vertex_weight_socket"]
        v1._build_material = old["build_material"]

    height_count = sum(int(row.get("heightDagCount", 0)) for row in result.get("rebuilt", []))
    height_materials = sum(
        1 for row in result.get("rebuilt", []) if int(row.get("heightDagCount", 0)) > 0
    )
    result["format"] = "t6-blender-generated-layer-preview-v4"
    result["recipeContract"] = "material.extras.T6.generatedShaderRecipeV1"
    result["heightDagCompiledMaterialCount"] = height_materials
    result["heightDagCompiledLayerCount"] = height_count
    result["heightDagPolicy"] = (
        "serialized forensic DAG + exact per-Material constants + exact normalized input/sample bindings; "
        "no generic vN height formula"
    )
    result["blenderCompatibility"] = "Separate Color (current) or Separate RGB (legacy)"
    result["proofBoundary"] = (
        "Exact generated diffuse source graph including vN serialized DAG equations and RGB square. "
        "Blender shader arithmetic may not be bit-identical to D3D11. Principled remains preview-only; "
        "retail normal/specular/lightmap/reflection final composition remains separate."
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
        "skippedMaterialCount": result["skippedMaterialCount"],
        "heightDagCompiledMaterialCount": result["heightDagCompiledMaterialCount"],
        "heightDagCompiledLayerCount": result["heightDagCompiledLayerCount"],
        "recipeContract": result["recipeContract"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
