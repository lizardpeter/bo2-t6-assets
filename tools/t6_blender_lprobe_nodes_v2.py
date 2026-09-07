#!/usr/bin/env python3
"""Blender lprobe node backend v2: fix UV-node transport without changing T6 semantics.

v1 returned the UV output socket from `_uv()` and then attempted to assign a
node layout location to that socket.  Blender 4.0 correctly rejects that.  v2
changes only this authoring/backend detail: create and position the UV Map node,
then link its UV output socket to the texture Vector input.

All T6 material-local equations, exact resource ownership, normal reconstruction,
glass alpha behavior, and proof boundaries remain v1.
"""
from __future__ import annotations

import t6_blender_lprobe_nodes_v1 as v1

FORMAT = "t6-blender-lprobe-nodes-v2"
PLAN_FORMAT = v1.PLAN_FORMAT
OPAQUE_FAMILY = v1.OPAQUE_FAMILY
GLASS_FAMILY = v1.GLASS_FAMILY
BlenderLprobeNodeError = v1.BlenderLprobeNodeError
bpy = v1.bpy


def _texture(nodes, links, plan: dict, role: str, cache: dict, x: float, y: float):
    resource = plan["materialResources"].get(role)
    if not isinstance(resource, dict):
        raise BlenderLprobeNodeError(f"plan lacks exact Material resource {role!r}")
    image_name = str(resource.get("image") or "")
    if not image_name:
        raise BlenderLprobeNodeError(f"plan resource {role!r} has empty image identity")

    node = nodes.new("ShaderNodeTexImage")
    node.name = f"T6_{role}"
    node.label = f"T6 exact {role}: {image_name}"
    node.image = v1._data_image(image_name, role, cache)
    node.interpolation = "Linear"
    node.extension = "REPEAT"
    node.location = (x, y)

    uv_node = nodes.new("ShaderNodeUVMap")
    uv_node.uv_map = "UVMap"
    uv_node.label = "T6 exact texcoord[0]"
    uv_node.location = (x - 220, y)
    links.new(v1._socket(uv_node.outputs, "UV"), v1._socket(node.inputs, "Vector"))
    return node


def compile_material(material, plan: dict, *, image_cache: dict | None = None) -> dict:
    old_texture = v1._texture
    v1._texture = _texture
    try:
        result = v1.compile_material(material, plan, image_cache=image_cache)
    finally:
        v1._texture = old_texture
    material["t6_shader_backend"] = FORMAT
    result = dict(result)
    result["format"] = FORMAT
    result["backendFix"] = "UV Map node/socket separation only; no T6 semantic change"
    return result
