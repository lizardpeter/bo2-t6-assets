#!/usr/bin/env python3
"""Connect solved T6 lprobe local nodes to the exact retail final-output equation.

`t6_blender_lprobe_nodes_v2` source-closes all material-local arithmetic but ends
at a Principled authoring substitute because renderer-global resources are not
supplied there. This bridge removes that final approximation when a caller can
supply exact global shader values (or exact baked equivalents):

- modelLighting.rgb after the retail 3D lookup/square/occlusion term;
- reflectionRgb after exact probe/Fresnel/SH-ratio arithmetic;
- fogColor.rgb and fogVisibility;
- hdrControl0.x.

The final RGB equations are the SHA-pinned lprobe equations retained in
`T6_RETAIL_LPROBE_LIT_SEMANTICS_V1.json`. The computed RGB is connected through
an Emission shader so Blender's own PBR lighting cannot modify it. Arbitrary D3D
framebuffer blend state and display/output color management remain separate
pipeline contracts.
"""
from __future__ import annotations

from typing import Any

import t6_blender_lprobe_nodes_v2 as local

FORMAT = "t6-blender-lprobe-retail-output-v1"
BlenderLprobeRetailOutputError = local.BlenderLprobeNodeError
bpy = local.bpy
v1 = local.v1

REQUIRED_GLOBALS = (
    "modelLighting",
    "reflectionRgb",
    "fogColor",
    "fogVisibility",
    "hdrControl0X",
)


def _socket(collection, name: str):
    return v1._socket(collection, name)


def _is_socket(value: Any) -> bool:
    return hasattr(value, "is_output") or value.__class__.__name__.startswith("NodeSocket")


def _scalar(nodes, value: Any, label: str):
    if _is_socket(value):
        return value
    node = nodes.new("ShaderNodeValue")
    node.label = label
    node.outputs[0].default_value = float(value)
    return node.outputs[0]


def _vector(nodes, value: Any, label: str):
    if _is_socket(value):
        return value
    if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
        raise BlenderLprobeRetailOutputError(f"{label}: expected vector socket or 3/4 numeric values")
    node = nodes.new("ShaderNodeRGB")
    node.label = label
    rgba = list(float(x) for x in value[:3]) + [float(value[3]) if len(value) == 4 else 1.0]
    node.outputs[0].default_value = rgba
    return node.outputs[0]


def _find_label(nodes, label: str):
    matches = [node for node in nodes if str(getattr(node, "label", "")) == label]
    if len(matches) != 1:
        raise BlenderLprobeRetailOutputError(f"expected one node labelled {label!r}, found {len(matches)}")
    return matches[0]


def _vmath(nodes, links, operation: str, a, b, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = operation
    node.label = label
    links.new(a, node.inputs[0])
    links.new(b, node.inputs[1])
    return _socket(node.outputs, "Vector")


def _scale(nodes, links, vec, scalar, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "SCALE"
    node.label = label
    links.new(vec, node.inputs[0])
    links.new(scalar, _socket(node.inputs, "Scale"))
    return _socket(node.outputs, "Vector")


def _divide_vector_by_scalar(nodes, links, vec, scalar, label: str):
    reciprocal = nodes.new("ShaderNodeMath")
    reciprocal.operation = "DIVIDE"
    reciprocal.label = label + " reciprocal"
    reciprocal.inputs[0].default_value = 1.0
    links.new(scalar, reciprocal.inputs[1])
    return _scale(nodes, links, vec, reciprocal.outputs[0], label)


def _sqrt_vector(nodes, links, vec, label: str):
    sep = nodes.new("ShaderNodeSeparateColor")
    sep.mode = "RGB"
    sep.label = label + " separate"
    links.new(vec, _socket(sep.inputs, "Color"))
    comb = nodes.new("ShaderNodeCombineColor")
    comb.mode = "RGB"
    comb.label = label
    for channel in ("Red", "Green", "Blue"):
        math = nodes.new("ShaderNodeMath")
        math.operation = "SQRT"
        math.label = f"{label} {channel}"
        links.new(_socket(sep.outputs, channel), math.inputs[0])
        links.new(math.outputs[0], _socket(comb.inputs, channel))
    return _socket(comb.outputs, "Color")


def _replace_surface(nodes, links, rgb, alpha, family: str):
    output = next((node for node in nodes if node.bl_idname == "ShaderNodeOutputMaterial"), None)
    if output is None:
        raise BlenderLprobeRetailOutputError("local lprobe graph has no Material Output")
    surface = _socket(output.inputs, "Surface")
    for link in list(surface.links):
        links.remove(link)
    emission = nodes.new("ShaderNodeEmission")
    emission.label = "T6 exact retail final RGB (emission transport)"
    links.new(rgb, _socket(emission.inputs, "Color"))
    emission.inputs["Strength"].default_value = 1.0
    links.new(_socket(emission.outputs, "Emission"), surface)

    # Surface shaders do not carry an independent alpha scalar. Keep exact alpha
    # on the material and, where Blender exposes it, use the emission color alpha
    # only as authoring metadata. D3D blending remains governed by retained state.
    if alpha is not None:
        alpha_node = nodes.new("ShaderNodeValue") if not _is_socket(alpha) else None
        if alpha_node is not None:
            alpha_node.label = "T6 exact final alpha"
            alpha_node.outputs[0].default_value = float(alpha)
        elif getattr(alpha, "node", None) is not None:
            alpha.node.label = str(alpha.node.label) + " | T6 exact final alpha"
    emission["t6_transport_only"] = True
    emission["t6_family"] = family
    return emission


def compile_retail_output(material, plan: dict, global_inputs: dict[str, Any], *, image_cache: dict | None = None) -> dict:
    if bpy is None:
        raise BlenderLprobeRetailOutputError("bpy unavailable; run inside Blender")
    missing = [name for name in REQUIRED_GLOBALS if name not in global_inputs]
    if missing:
        raise BlenderLprobeRetailOutputError(f"missing exact global lprobe inputs: {missing}")

    local_report = local.compile_material(material, plan, image_cache=image_cache)
    family = str(plan.get("family") or "")
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    linear_node = _find_label(nodes, "T6 explicit encoded RGB square")
    linear_like = _socket(linear_node.outputs, "Vector")
    model_lighting = _vector(nodes, global_inputs["modelLighting"], "T6 exact modelLighting global")
    reflection_rgb = _vector(nodes, global_inputs["reflectionRgb"], "T6 exact reflectionRgb global")
    fog_color = _vector(nodes, global_inputs["fogColor"], "T6 exact fogColor global")
    fog_visibility = _scalar(nodes, global_inputs["fogVisibility"], "T6 exact fogVisibility global")
    hdr = _scalar(nodes, global_inputs["hdrControl0X"], "T6 exact hdrControl0.x global")

    diffuse = _vmath(nodes, links, "MULTIPLY", model_lighting, linear_like, "T6 modelLighting * linearLikeRgb")
    diffuse = _scale(nodes, links, diffuse, _scalar(nodes, 32.0, "T6 exact diffuse factor 32"), "T6 32 * modelLighting * linearLikeRgb")

    if family == local.OPAQUE_FAMILY:
        lit = _vmath(nodes, links, "ADD", diffuse, reflection_rgb, "T6 litRgb = diffuse + reflection")
        lit_minus_fog = _vmath(nodes, links, "SUBTRACT", lit, fog_color, "T6 litRgb - fogColor")
        visible = _scale(nodes, links, lit_minus_fog, fog_visibility, "T6 fogVisibility * (litRgb-fogColor)")
        fogged = _vmath(nodes, links, "ADD", fog_color, visible, "T6 foggedRgb")
        alpha = 1.0
    elif family == local.GLASS_FAMILY:
        alpha_encoded_node = _find_label(nodes, "T6 alphaEncoded = colorMap.a * vertexColor.a")
        alpha_encoded = alpha_encoded_node.outputs[0]
        reflection_unpremul = _divide_vector_by_scalar(nodes, links, reflection_rgb, alpha_encoded, "T6 reflectionRgb / alphaEncoded")
        lit_unpremul = _vmath(nodes, links, "ADD", diffuse, reflection_unpremul, "T6 glass litUnpremul")
        alpha_lit = _scale(nodes, links, lit_unpremul, alpha_encoded, "T6 alphaEncoded * litUnpremul")
        fog_premul = _scale(nodes, links, fog_color, alpha_encoded, "T6 alphaEncoded * fogColor")
        delta = _vmath(nodes, links, "SUBTRACT", alpha_lit, fog_premul, "T6 glass alphaLit - fogPremul")
        visible = _scale(nodes, links, delta, fog_visibility, "T6 glass fogVisibility * delta")
        fogged = _vmath(nodes, links, "ADD", fog_premul, visible, "T6 glass premulFogged")
        alpha_node = _find_label(nodes, "T6 output alpha = sqrt(alphaEncoded)")
        alpha = alpha_node.outputs[0]
    else:
        raise BlenderLprobeRetailOutputError(f"unsupported exact lprobe family {family!r}")

    hdr_rgb = _scale(nodes, links, fogged, hdr, "T6 foggedRgb * hdrControl0.x")
    final_rgb = _sqrt_vector(nodes, links, hdr_rgb, "T6 outRgb = sqrt(fogged*hdr)")
    emission = _replace_surface(nodes, links, final_rgb, alpha, family)

    # Keep the old Principled node visible but explicitly disconnected/retired.
    for node in nodes:
        if node.bl_idname == "ShaderNodeBsdfPrincipled":
            node.label = "RETIRED AUTHORING SUBSTITUTE: exact T6 output connected"
            node["t6_retired"] = True

    material["t6_shader_backend"] = FORMAT
    material["t6_complete_retail_pixel_arithmetic"] = True
    material["t6_global_inputs_exact_or_baked"] = True
    material["t6_preview_surface"] = "exact T6 RGB arithmetic transported through Blender Emission; framebuffer blend/output transform separate"
    material["t6_remaining_pipeline_boundaries"] = "D3D framebuffer blend/depth state and final display/color-management transfer"

    return {
        "format": FORMAT,
        "material": material.name,
        "family": family,
        "localReport": local_report,
        "nodeCount": len(nodes),
        "completeRetailPixelArithmetic": True,
        "surfaceTransport": "Emission",
        "requiredGlobalInputs": list(REQUIRED_GLOBALS),
        "remainingPipelineBoundaries": ["D3D framebuffer blend/depth state", "Blender/display color-management transfer"],
        "emissionNode": emission.name,
    }
