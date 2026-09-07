#!/usr/bin/env python3
"""Compile one exact generated T6 pixel-shader o0 DAG into a Blender material.

Consumes a shader row from `t6-generated-slot4-final-output-symbolic-v3` and the
shared multi-root v3 Blender DAG compiler. Callers resolve exact symbol and
textureSample leaves. This module lowers all written o0 lanes once, combines
x/y/z into RGB, and transports the already-computed T6 pixel value through an
Emission shader so Blender PBR lighting cannot alter it.

This closes final expression-DAG wiring only. Texture sampling equivalence,
renderer-global symbol values, framebuffer blend/depth state, and display/color
management remain separately gated.
"""
from __future__ import annotations

from typing import Any

import t6_blender_symbolic_dag_nodes_v3 as dag

FORMAT = "t6-blender-generated-retail-output-v1"
bpy = dag.bpy
BlenderGeneratedRetailOutputError = dag.BlenderSymbolicDagError


def _is_socket(value: Any) -> bool:
    return hasattr(value, "is_output") or value.__class__.__name__.startswith("NodeSocket")


def _set_or_link(links, socket, value):
    if _is_socket(value):
        links.new(value, socket)
    else:
        socket.default_value = float(value)


def _o0_roots(shader: dict) -> tuple[dict[str, int], bool]:
    rows = [row for row in shader.get("outputs", []) if int(row.get("register", -1)) == 0]
    if len(rows) != 1:
        raise BlenderGeneratedRetailOutputError(
            f"shader {shader.get('sha256')}: expected exactly one o0 row, found {len(rows)}"
        )
    lanes = rows[0].get("lanes")
    if not isinstance(lanes, list) or [row.get("channel") for row in lanes] != list("xyzw"):
        raise BlenderGeneratedRetailOutputError("o0 lanes are not serialized as xyzw")
    roots = {}
    for lane in lanes:
        if bool(lane.get("written")):
            if lane.get("node") is None:
                raise BlenderGeneratedRetailOutputError(f"written o0.{lane['channel']} lacks a root node")
            roots[str(lane["channel"])] = int(lane["node"])
    if not all(channel in roots for channel in "xyz"):
        raise BlenderGeneratedRetailOutputError("generated pixel shader does not write complete o0.rgb")
    return roots, "w" in roots


def compile_material_output(material, shader: dict, *, symbol_resolver, texture_resolver) -> dict:
    if bpy is None:
        raise BlenderGeneratedRetailOutputError("bpy unavailable; run inside Blender")
    nodes_data = shader.get("nodes")
    if not isinstance(nodes_data, list) or not nodes_data:
        raise BlenderGeneratedRetailOutputError("shader row has no symbolic DAG nodes")
    roots, alpha_written = _o0_roots(shader)

    material.use_nodes = True
    tree = material.node_tree
    if tree is None:
        raise BlenderGeneratedRetailOutputError("material has no node tree")
    nodes, links = tree.nodes, tree.links
    nodes.clear()

    compiled, stats = dag.compile_dag_roots(
        nodes,
        links,
        nodes_data,
        roots,
        symbol_resolver=symbol_resolver,
        texture_resolver=texture_resolver,
    )

    combine = nodes.new("ShaderNodeCombineColor")
    combine.mode = "RGB"
    combine.label = "T6 exact generated o0.rgb"
    for channel, socket_name in (("x", "Red"), ("y", "Green"), ("z", "Blue")):
        _set_or_link(links, combine.inputs[socket_name], compiled[channel])

    emission = nodes.new("ShaderNodeEmission")
    emission.label = "T6 exact generated final RGB (emission transport)"
    links.new(combine.outputs["Color"], emission.inputs["Color"])
    emission.inputs["Strength"].default_value = 1.0
    emission["t6_transport_only"] = True
    emission["t6_pixel_shader_sha256"] = str(shader.get("sha256") or "")

    output = nodes.new("ShaderNodeOutputMaterial")
    output.label = "T6 exact generated pixel output"
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    alpha_node_name = None
    if alpha_written:
        alpha_value = compiled["w"]
        if _is_socket(alpha_value):
            if getattr(alpha_value, "node", None) is not None:
                alpha_value.node.label = str(alpha_value.node.label) + " | T6 exact o0.a"
                alpha_node_name = alpha_value.node.name
        else:
            alpha_node = nodes.new("ShaderNodeValue")
            alpha_node.label = "T6 exact o0.a"
            alpha_node.outputs[0].default_value = float(alpha_value)
            alpha_node_name = alpha_node.name

    material["t6_shader_backend"] = FORMAT
    material["t6_pixel_shader_sha256"] = str(shader.get("sha256") or "")
    material["t6_complete_symbolic_o0_arithmetic"] = True
    material["t6_o0_alpha_written"] = bool(alpha_written)
    material["t6_surface_transport"] = "Emission"
    material["t6_remaining_pipeline_boundaries"] = (
        "exact texture/global resource resolution and D3D sampling; framebuffer blend/depth state; display/color-management transfer"
    )

    return {
        "format": FORMAT,
        "material": material.name,
        "pixelShaderSha256": str(shader.get("sha256") or ""),
        "techniqueSets": sorted(str(x) for x in shader.get("techniqueSets", [])),
        "compiledO0Lanes": sorted(compiled),
        "alphaWritten": bool(alpha_written),
        "alphaNode": alpha_node_name,
        "nodeCount": len(nodes),
        "dagCompiler": stats,
        "completeSymbolicO0Arithmetic": True,
        "surfaceTransport": "Emission",
        "remainingPipelineBoundaries": [
            "exact texture/global leaf resolution and D3D sampling",
            "D3D framebuffer blend/depth state",
            "display/color-management transfer",
        ],
    }
