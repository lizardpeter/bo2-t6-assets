#!/usr/bin/env python3
"""Blender generated-layer preview v6: execute source-closed layered normals.

v6 keeps v5's production provenance and v4's exact diffuse/vN execution, then
adds generated layered-normal playback for materials whose canonical recipe and
v20 GLB close every required boundary:

* exact base normal sample DAG or zero baseline (recovery v9);
* exact secondary normal sample DAGs;
* v15 dual-proof direct/2x2 transform ownership;
* the SAME exact RGB compositor factor socket used by diffuse;
* v16 paired-VS physical N/T/B basis proof;
* v20 separately interpolated exact N/T/B custom vertex attributes.

The final world normal is wired to Principled only as Blender's downstream
lighting consumer. T6 layered specular, lightmap and reflection composition are
still not replaced with generic PBR semantics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import t6_blender_generated_layer_preview_v1 as v1
import t6_blender_generated_layer_preview_v2 as v2
import t6_blender_generated_layer_preview_v4 as v4
import t6_blender_generated_layer_preview_v5 as v5
import t6_blender_generated_normal_nodes_v1 as normal_nodes
from t6_generated_world_shader_semantics_v1 import layer_weight_class, parse_generated_layer_tokens
from t6_world_generated_normal_basis_attributes_v2 import FORMAT as BASIS_ATTRIBUTE_V2_FORMAT

bpy = v1.bpy
BlenderLayerPreviewError = v1.BlenderLayerPreviewError


def _root_v20_preflight(input_path: Path) -> dict:
    try:
        document = v1._read_gltf_json(input_path)
    except Exception as exc:
        raise BlenderLayerPreviewError(f"cannot inspect v20 normal basis contract: {exc}") from exc
    t6 = document.get("extras", {}).get("T6", {})
    contract = t6.get("generatedNormalBasisAttributesV2")
    if not isinstance(contract, dict) or contract.get("format") != BASIS_ATTRIBUTE_V2_FORMAT:
        raise BlenderLayerPreviewError(
            f"input lacks authoritative {BASIS_ATTRIBUTE_V2_FORMAT}; refuse fragment-stage basis reconstruction"
        )
    stats = contract.get("stats")
    if not isinstance(stats, dict) or int(stats.get("generatedPrimitiveCount", -1)) <= 0:
        raise BlenderLayerPreviewError("v20 normal basis contract has invalid generated primitive accounting")

    materials = document.get("materials")
    if not isinstance(materials, list):
        raise BlenderLayerPreviewError("v20 GLB has no materials list")
    generated_primitives = 0
    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        primitives = mesh.get("primitives")
        if not isinstance(primitives, list):
            raise BlenderLayerPreviewError(f"mesh {mesh_index} has invalid primitives")
        for primitive_index, primitive in enumerate(primitives):
            try:
                material = materials[int(primitive["material"])]
            except Exception as exc:
                raise BlenderLayerPreviewError(
                    f"mesh {mesh_index} primitive {primitive_index} has invalid material"
                ) from exc
            name = str(material.get("name") or "")
            if not name.startswith("*"):
                continue
            generated_primitives += 1
            attrs = primitive.get("attributes")
            required = {
                "_T6_LAYER_WEIGHTS",
                "_T6_WORLD_NORMAL",
                "_T6_WORLD_TANGENT",
                "_T6_WORLD_BINORMAL",
            }
            if not isinstance(attrs, dict) or not required.issubset(attrs):
                raise BlenderLayerPreviewError(
                    f"{name!r}: generated primitive lacks v20 attributes {sorted(required - set(attrs or {}))}"
                )
            recipe = material.get("extras", {}).get("T6", {}).get("generatedShaderRecipeV1")
            if not isinstance(recipe, dict):
                raise BlenderLayerPreviewError(f"{name!r}: canonical generated recipe is absent")
            state = recipe.get(normal_nodes.NORMAL_STATE_KEY)
            basis = recipe.get(normal_nodes.BASIS_KEY)
            # Only recipes with exact paired-VS basis are eligible for normal
            # playback. For those, every transform2x2 attribute must physically
            # exist on every owner primitive.
            if isinstance(basis, dict) and isinstance(state, dict):
                for row in state.get("layers", []):
                    if str(row.get("transformMode") or "") != "transform2x2":
                        continue
                    attribute = str(row.get("normalTransformAttribute") or "")
                    if not attribute or attribute not in attrs:
                        raise BlenderLayerPreviewError(
                            f"{name!r}: exact normal transform attribute {attribute!r} is absent from owner primitive"
                        )
    if generated_primitives != int(stats.get("generatedPrimitiveCount", -1)):
        raise BlenderLayerPreviewError(
            f"v20 generated primitive accounting {generated_primitives} != contract {stats.get('generatedPrimitiveCount')}"
        )
    return contract


def _build_material_v6(blender_material, gltf_material: dict, technique: str, recipe: dict | None, image_cache: dict) -> dict:
    t6 = gltf_material.get("extras", {}).get("T6", {})
    deps = v1._embedded_dependencies(t6)
    tokens = parse_generated_layer_tokens(technique)
    if not tokens:
        raise BlenderLayerPreviewError("TechniqueSet contains no secondary generated layers")
    material_name = str(gltf_material.get("name") or blender_material.name)

    base_source = v1._source(
        v1._role_dependency(deps, 0, "colorMap"),
        material=material_name,
        layer=0,
        role="colorMap",
        required=True,
    )
    color_sources: dict[int, str] = {}
    height_plans: dict[int, object] = {}
    for token in tokens:
        color_sources[token.layer] = v1._source(
            v1._role_dependency(deps, token.layer, "colorMap"),
            material=material_name,
            layer=token.layer,
            role="colorMap",
            required=True,
        )
        if token.height_variant:
            if recipe is None:
                raise BlenderLayerPreviewError(
                    f"{material_name!r} uses v{token.layer} but lacks canonical recipe"
                )
            height_plans[token.layer] = v4._height_identity_preflight(
                material_name, technique, recipe, token.layer
            )

    normal_tokens = [token for token in tokens if token.has_normal]
    normal_plan = None
    normal_sources: dict[int, str] = {}
    if normal_tokens:
        if recipe is None:
            raise BlenderLayerPreviewError(
                f"{material_name!r}: secondary layered normals require canonical recipe"
            )
        try:
            normal_plan = normal_nodes.prepare_plan(
                recipe,
                technique_set=technique,
                normal_layers=[token.layer for token in normal_tokens],
            )
        except normal_nodes.BlenderGeneratedNormalError as exc:
            raise BlenderLayerPreviewError(
                f"{material_name!r}: exact layered-normal preflight failed: {exc}"
            ) from exc
        if normal_plan.baseline["mode"] == "explicit_normal":
            normal_sources[0] = v1._source(
                v1._role_dependency(deps, 0, "normalMap"),
                material=material_name,
                layer=0,
                role="normalMap",
                required=True,
            )
        for token in normal_tokens:
            normal_sources[token.layer] = v1._source(
                v1._role_dependency(deps, token.layer, "normalMap"),
                material=material_name,
                layer=token.layer,
                role="normalMap",
                required=True,
            )

    blender_material.use_nodes = True
    tree = blender_material.node_tree
    nodes, links = tree.nodes, tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1450, 0)
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (1200, 0)
    principled.label = "Blender downstream lighting ONLY"
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    base_tex = v1._wire_tex(nodes, links, base_source, "colorMap", 0, image_cache)
    base_tex.location = (-1500, 400)
    composed = base_tex.outputs["Color"]
    attr, sep = v2._weight_attribute(nodes)
    attr.location = (-1500, -450)
    sep.location = (-1300, -450)

    factor_by_layer: dict[int, object] = {}
    layer_nodes = []
    height_dag_rows = []
    for order, token in enumerate(tokens):
        tex = v1._wire_tex(
            nodes, links, color_sources[token.layer], "colorMap", token.layer, image_cache
        )
        tex.location = (-1200 + order * 55, 350 - token.layer * 180)
        cls = layer_weight_class(token)
        if cls == "height":
            if recipe is None:
                raise BlenderLayerPreviewError(
                    f"{material_name!r} layer {token.layer}: canonical height recipe absent"
                )
            factor, plan = v4._height_factor(
                nodes, links,
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
        factor_by_layer[token.layer] = factor
        composed = v1._compose(
            nodes, links, composed, tex.outputs["Color"], factor, token.operation, token.layer
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

    normal_rows = []
    normal_playback = False
    if normal_plan is not None:
        if normal_plan.baseline["mode"] == "zero":
            normal_xy = normal_nodes.zero_baseline(nodes)
            normal_rows.append({"layer": 0, "mode": "zero"})
        else:
            base_normal_tex = v1._wire_tex(
                nodes, links, normal_sources[0], "normalMap", 0, image_cache
            )
            base_normal_tex.location = (-1500, -850)
            try:
                normal_xy, row = normal_nodes.compile_decode_pair(
                    nodes, links, normal_plan.baseline, layer_index=0, texture_node=base_normal_tex
                )
            except normal_nodes.BlenderGeneratedNormalError as exc:
                raise BlenderLayerPreviewError(
                    f"{material_name!r}: base normal DAG compilation failed: {exc}"
                ) from exc
            normal_rows.append({**row, "mode": "explicit_normal"})

        token_by_layer = {token.layer: token for token in normal_tokens}
        for layer in sorted(normal_plan.layers):
            token = token_by_layer[layer]
            tex = v1._wire_tex(
                nodes, links, normal_sources[layer], "normalMap", layer, image_cache
            )
            tex.location = (-1000 + layer * 50, -850 - layer * 190)
            try:
                layer_xy, row = normal_nodes.compile_decode_pair(
                    nodes, links, normal_plan.layers[layer], layer_index=layer, texture_node=tex
                )
                layer_xy = normal_nodes.apply_transform(
                    nodes, links, layer_xy, normal_plan.layers[layer]
                )
                factor = factor_by_layer.get(layer)
                if factor is None:
                    raise normal_nodes.BlenderGeneratedNormalError(
                        f"layer {layer}: exact diffuse factor socket is absent"
                    )
                normal_xy = normal_nodes.compose_xy(
                    nodes, links, normal_xy, layer_xy, factor,
                    operation=token.operation,
                    layer_index=layer,
                )
            except normal_nodes.BlenderGeneratedNormalError as exc:
                raise BlenderLayerPreviewError(
                    f"{material_name!r} layer {layer}: layered-normal node build failed: {exc}"
                ) from exc
            normal_rows.append({
                **row,
                "operation": token.operation,
                "transformMode": normal_plan.layers[layer]["transformMode"],
                "normalTransformAttribute": normal_plan.layers[layer].get("normalTransformAttribute"),
                "usesExactDiffuseFactorSocket": True,
            })

        try:
            final_normal = normal_nodes.reconstruct_world_normal(nodes, links, normal_xy)
        except normal_nodes.BlenderGeneratedNormalError as exc:
            raise BlenderLayerPreviewError(
                f"{material_name!r}: world normal reconstruction failed: {exc}"
            ) from exc
        normal_input = principled.inputs.get("Normal")
        if normal_input is None:
            raise BlenderLayerPreviewError("Principled BSDF exposes no Normal input")
        links.new(final_normal, normal_input)
        normal_playback = True

    spec_sources = []
    preserved_normal_sources = []
    for layer in range(4):
        spec = v1._role_dependency(deps, layer, "specularMap")
        normal = v1._role_dependency(deps, layer, "normalMap")
        if spec is not None:
            spec_sources.append({
                "layer": layer,
                "sourceTexture": v1._source(
                    spec, material=material_name, layer=layer, role="specularMap", required=False
                ),
            })
        if normal is not None:
            preserved_normal_sources.append({
                "layer": layer,
                "sourceTexture": v1._source(
                    normal, material=material_name, layer=layer, role="normalMap", required=False
                ),
                "executed": normal_playback and layer in normal_sources,
            })

    blender_material["T6_preview_status"] = (
        "exact generated diffuse + exact layered normal when paired-VS basis is present; Blender downstream lighting"
    )
    blender_material["T6_technique_set"] = technique
    blender_material["T6_layer_steps_json"] = json.dumps(layer_nodes, sort_keys=True)
    blender_material["T6_height_dags_json"] = json.dumps(height_dag_rows, sort_keys=True)
    blender_material["T6_layered_normal_steps_json"] = json.dumps(normal_rows, sort_keys=True)
    blender_material["T6_layered_normal_dependencies_json"] = json.dumps(preserved_normal_sources, sort_keys=True)
    blender_material["T6_layered_specular_dependencies_json"] = json.dumps(spec_sources, sort_keys=True)
    blender_material["T6_layered_normal_playback"] = bool(normal_playback)
    blender_material["T6_preview_proof_boundary"] = (
        "exact generated diffuse/vN equations plus, where canonical v9/v15/v16/v20 proof is complete, exact base/secondary "
        "normal sample DAGs, dual-proof 2x2 ownership, same RGB factor recurrence, separately interpolated N/T/B basis and "
        "retail normalize(N+X*T+Y*B); Blender arithmetic/downstream lighting are not claimed bit-identical to D3D11; "
        "T6 specular/lightmap/reflection remain separate"
    )
    return {
        "layers": layer_nodes,
        "heightDagCount": len(height_dag_rows),
        "heightDags": height_dag_rows,
        "normalPlayback": normal_playback,
        "normalLayerCount": len(normal_tokens) if normal_playback else 0,
        "normalSteps": normal_rows,
        "specularDependencies": len(spec_sources),
        "normalDependencies": len(preserved_normal_sources),
    }


def apply_preview(input_path: Path, output_blend: Path, *, recipes: Path | None = None, strict: bool = False) -> dict:
    basis_contract = _root_v20_preflight(input_path)
    old_builder = v4._build_material_v4
    v4._build_material_v4 = _build_material_v6
    try:
        result = v5.apply_preview(
            input_path, output_blend, recipes=recipes, strict=strict
        )
    finally:
        v4._build_material_v4 = old_builder

    normal_materials = sum(1 for row in result.get("rebuilt", []) if bool(row.get("normalPlayback")))
    normal_layers = sum(int(row.get("normalLayerCount", 0)) for row in result.get("rebuilt", []))
    result["format"] = "t6-blender-generated-layer-preview-v6"
    result["normalBasisAttributeContract"] = BASIS_ATTRIBUTE_V2_FORMAT
    result["normalBasisAttributeContractSha256"] = basis_contract.get("contractSha256")
    result["normalPlaybackMaterialCount"] = normal_materials
    result["normalPlaybackLayerCount"] = normal_layers
    result["normalPlaybackPolicy"] = (
        "secondary layered normals execute only with canonical v9 decode + v15 transform + v16 paired-VS basis + "
        "v20 separately interpolated N/T/B attributes; base-only unproven populations are not widened"
    )
    result["proofBoundary"] = (
        "Exact generated diffuse plus source-closed layered normal graph for the paired-VS-proven population. "
        "Blender remains a downstream lighting preview; retail specular/lightmap/reflection final composition is separate."
    )
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
        "heightDagCompiledLayerCount": result["heightDagCompiledLayerCount"],
        "normalPlaybackMaterialCount": result["normalPlaybackMaterialCount"],
        "normalPlaybackLayerCount": result["normalPlaybackLayerCount"],
        "normalBasisAttributeContract": result["normalBasisAttributeContract"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
