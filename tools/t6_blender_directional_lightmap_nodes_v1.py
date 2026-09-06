#!/usr/bin/env python3
"""Build the retained T6 directional secondary-lightmap equation in Blender.

This module assumes the caller already supplies:
- the decoded authoring preview image derived from the exact archived DDS;
- the exact lightmap TEXCOORD index for this GfxSurface/material shell;
- the exact reconstructed T6 world normal socket.

Equation (retained slot-4 DXBC proof):

  row0 = sample(secondary, (u, v/3))
  row1 = sample(secondary, (u, v/3 + 1/3))
  row2 = sample(secondary, (u, v/3 + 2/3))
  direction = 2*row2.rgb - 1
  factor = saturate(dot(direction, N))
  rgb = row0.rgb/(row0.a+1e-6) + row1.rgb/(row1.a+1e-6)*factor

The equation/coordinates are exact.  Blender/Pillow texture decoding/filtering is
an authoring backend and is not claimed bit-identical to the retail D3D11
sampler.  The returned RGB state is not combined with diffuse/specular/reflection
here because that final composition remains a separate proof boundary.
"""
from __future__ import annotations

from typing import Any

EPSILON = 1.0e-6
FORMAT = "t6-blender-directional-secondary-lightmap-nodes-v1"


class BlenderDirectionalLightmapError(RuntimeError):
    pass


def uv_map_name(texcoord: int) -> str:
    value = int(texcoord)
    if value < 0:
        raise BlenderDirectionalLightmapError(f"negative lightmap TEXCOORD {value}")
    return "UVMap" if value == 0 else f"UVMap.{value:03d}"


def _math(nodes, operation: str, label: str):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    node.label = label
    return node


def _vector(nodes, operation: str, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = operation
    node.label = label
    return node


def _socket(collection, *names):
    for name in names:
        socket = collection.get(name)
        if socket is not None:
            return socket
    return None


def _separate_xyz(nodes, links, vector_socket, label: str):
    node = nodes.new("ShaderNodeSeparateXYZ")
    node.label = label
    links.new(vector_socket, node.inputs["Vector"])
    return node.outputs["X"], node.outputs["Y"], node.outputs["Z"]


def _combine_xy(nodes, links, x, y, label: str):
    node = nodes.new("ShaderNodeCombineXYZ")
    node.label = label
    links.new(x, node.inputs["X"])
    links.new(y, node.inputs["Y"])
    node.inputs["Z"].default_value = 0.0
    return node.outputs["Vector"]


def _row_uv(nodes, links, u, v, row: int):
    div = _math(nodes, "DIVIDE", f"T6 LM row{row} v/3")
    links.new(v, div.inputs[0]); div.inputs[1].default_value = 3.0
    y = div.outputs[0]
    if row:
        add = _math(nodes, "ADD", f"T6 LM row{row} + {row}/3")
        links.new(y, add.inputs[0]); add.inputs[1].default_value = float(row) / 3.0
        y = add.outputs[0]
    return _combine_xy(nodes, links, u, y, f"T6 LM row{row} UV")


def _texture(nodes, links, image, vector_socket, row: int):
    node = nodes.new("ShaderNodeTexImage")
    node.name = f"T6_LIGHTMAP_SECONDARY_ROW{row}"
    node.label = f"T6 exact secondary lightmap row {row} (authoring sampler)"
    node.image = image
    if hasattr(node, "interpolation"):
        node.interpolation = "Linear"
    if hasattr(node, "extension"):
        node.extension = "EXTEND"
    links.new(vector_socket, node.inputs["Vector"])
    color = node.outputs.get("Color")
    alpha = node.outputs.get("Alpha")
    if color is None or alpha is None:
        raise BlenderDirectionalLightmapError("Blender image texture lacks Color/Alpha outputs")
    return node, color, alpha


def _normalized_row(nodes, links, rgb, alpha, row: int):
    denom = _math(nodes, "ADD", f"T6 LM row{row} alpha + 1e-6")
    links.new(alpha, denom.inputs[0]); denom.inputs[1].default_value = EPSILON
    recip = _math(nodes, "DIVIDE", f"T6 LM row{row} reciprocal alpha")
    recip.inputs[0].default_value = 1.0; links.new(denom.outputs[0], recip.inputs[1])
    splat = nodes.new("ShaderNodeCombineXYZ")
    splat.label = f"T6 LM row{row} reciprocal splat"
    for name in ("X", "Y", "Z"):
        links.new(recip.outputs[0], splat.inputs[name])
    mul = _vector(nodes, "MULTIPLY", f"T6 LM row{row} rgb/(a+1e-6)")
    links.new(rgb, mul.inputs[0]); links.new(splat.outputs["Vector"], mul.inputs[1])
    return mul.outputs["Vector"]


def _signed_direction(nodes, links, rgb):
    scale = _vector(nodes, "SCALE", "T6 LM direction row2.rgb * 2")
    links.new(rgb, scale.inputs[0])
    scale_input = _socket(scale.inputs, "Scale")
    if scale_input is None:
        # Vector Math SCALE is normally Vector + Scale; fail closed if Blender's
        # API shape changes instead of silently choosing a socket index.
        raise BlenderDirectionalLightmapError("Blender Vector Math SCALE exposes no Scale input")
    scale_input.default_value = 2.0
    add = _vector(nodes, "ADD", "T6 LM direction = 2*row2.rgb - 1")
    links.new(scale.outputs["Vector"], add.inputs[0])
    add.inputs[1].default_value = (-1.0, -1.0, -1.0)
    return add.outputs["Vector"]


def _saturate(nodes, links, value):
    lo = _math(nodes, "MAXIMUM", "T6 LM dot max(0)")
    links.new(value, lo.inputs[0]); lo.inputs[1].default_value = 0.0
    hi = _math(nodes, "MINIMUM", "T6 LM dot min(1)")
    links.new(lo.outputs[0], hi.inputs[0]); hi.inputs[1].default_value = 1.0
    return hi.outputs[0]


def build_directional_secondary(
    nodes,
    links,
    *,
    image,
    lightmap_texcoord: int,
    world_normal_socket,
) -> tuple[Any, dict]:
    if image is None:
        raise BlenderDirectionalLightmapError("secondary lightmap preview image is absent")
    uv_name = uv_map_name(lightmap_texcoord)
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = uv_name
    uv.label = f"T6 exact lightmap TEXCOORD_{int(lightmap_texcoord)}"
    u, v, _ = _separate_xyz(nodes, links, uv.outputs["UV"], "T6 lightmap UV split")

    samples = []
    for row in range(3):
        coord = _row_uv(nodes, links, u, v, row)
        tex, color, alpha = _texture(nodes, links, image, coord, row)
        samples.append((tex, color, alpha))

    row0 = _normalized_row(nodes, links, samples[0][1], samples[0][2], 0)
    row1 = _normalized_row(nodes, links, samples[1][1], samples[1][2], 1)
    direction = _signed_direction(nodes, links, samples[2][1])
    dot = _vector(nodes, "DOT_PRODUCT", "T6 LM dot(direction, reconstructed N)")
    links.new(direction, dot.inputs[0]); links.new(world_normal_socket, dot.inputs[1])
    dot_value = _socket(dot.outputs, "Value")
    if dot_value is None:
        raise BlenderDirectionalLightmapError("Blender Vector Math DOT_PRODUCT exposes no Value output")
    factor = _saturate(nodes, links, dot_value)

    factor_vec = nodes.new("ShaderNodeCombineXYZ")
    factor_vec.label = "T6 LM directional factor splat"
    for name in ("X", "Y", "Z"):
        links.new(factor, factor_vec.inputs[name])
    directional = _vector(nodes, "MULTIPLY", "T6 LM row1 normalized * directional factor")
    links.new(row1, directional.inputs[0]); links.new(factor_vec.outputs["Vector"], directional.inputs[1])
    final = _vector(nodes, "ADD", "T6 exact directional secondary-lightmap RGB")
    links.new(row0, final.inputs[0]); links.new(directional.outputs["Vector"], final.inputs[1])

    return final.outputs["Vector"], {
        "format": FORMAT,
        "lightmapTexCoord": int(lightmap_texcoord),
        "blenderUvMap": uv_name,
        "rowOffsets": [0.0, 1.0 / 3.0, 2.0 / 3.0],
        "epsilon": EPSILON,
        "directionNormalization": False,
        "usesReconstructedT6WorldNormal": True,
        "equation": (
            "row0.rgb/(row0.a+1e-6) + row1.rgb/(row1.a+1e-6) * "
            "saturate(dot(2*row2.rgb-1,N))"
        ),
        "samplingBoundary": (
            "equation/coordinates exact; Pillow/Blender decode/filter backend not claimed bit-identical to retail D3D11 sampler"
        ),
        "finalComposition": "unassigned; directional RGB state only",
    }
