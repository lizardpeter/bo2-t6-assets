#!/usr/bin/env python3
"""Blender generated-normal nodes v2: explicit glTF -> Blender basis axes.

Production v20 custom `_T6_WORLD_*` attributes are application attributes whose
numeric values are the renderer-neutral glTF-space basis values.  They must not
be treated as if Blender's importer had applied the built-in NORMAL/TANGENT
semantic conversion to them.

For direction vectors the fixed glTF Y-up -> Blender Z-up conversion is:

    (x_gltf, y_gltf, z_gltf) -> (x_blender, y_blender, z_blender)
                              = (x_gltf, -z_gltf, y_gltf)

v2 applies that mapping explicitly to N/T/B custom attributes before the normal
v1 OBJECT->WORLD transform and retail `normalize(N + X*T + Y*B)` reconstruction.
No texture/normal recurrence semantics change.
"""
from __future__ import annotations

import t6_blender_generated_normal_nodes_v1 as v1


BlenderGeneratedNormalError = v1.BlenderGeneratedNormalError

# Re-export the stable v1 planning/normal arithmetic API used by preview v6/v7.
NORMAL_STATE_KEY = v1.NORMAL_STATE_KEY
TRANSFORM_KEY = v1.TRANSFORM_KEY
BASIS_KEY = v1.BASIS_KEY
NORMAL_STATE_FORMAT = v1.NORMAL_STATE_FORMAT
BASIS_FORMAT = v1.BASIS_FORMAT
BASIS_ATTRIBUTE_FORMAT_V2 = v1.BASIS_ATTRIBUTE_FORMAT_V2
NormalPlaybackPlan = v1.NormalPlaybackPlan
prepare_plan = v1.prepare_plan
compile_decode_pair = v1.compile_decode_pair
apply_transform = v1.apply_transform
compose_xy = v1.compose_xy
zero_baseline = v1.zero_baseline


def _socket(collection, name: str):
    value = collection.get(name)
    if value is None:
        raise BlenderGeneratedNormalError(f"Blender node lacks {name!r} socket")
    return value


def gltf_to_blender_object_vector(nodes, links, vector, label: str):
    """Map an application custom vector from glTF axes to Blender object axes."""
    separate = nodes.new("ShaderNodeSeparateXYZ")
    separate.label = label + " glTF xyz"
    links.new(vector, _socket(separate.inputs, "Vector"))

    neg_z = nodes.new("ShaderNodeMath")
    neg_z.operation = "MULTIPLY"
    neg_z.label = label + " -gltf.z"
    links.new(_socket(separate.outputs, "Z"), neg_z.inputs[0])
    neg_z.inputs[1].default_value = -1.0

    combine = nodes.new("ShaderNodeCombineXYZ")
    combine.label = label + " glTF->Blender (x,-z,y)"
    links.new(_socket(separate.outputs, "X"), _socket(combine.inputs, "X"))
    links.new(neg_z.outputs[0], _socket(combine.inputs, "Y"))
    links.new(_socket(separate.outputs, "Y"), _socket(combine.inputs, "Z"))
    return _socket(combine.outputs, "Vector")


def _attribute_gltf_vector(nodes, name: str):
    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_name = name
    attr.label = f"T6 exact glTF-space {name}"
    vector = attr.outputs.get("Vector")
    if vector is None:
        vector = attr.outputs.get("Color")
    if vector is None:
        raise BlenderGeneratedNormalError(
            f"Blender Attribute node cannot expose vector {name}"
        )
    return vector


def _object_to_world(nodes, links, vector, label: str):
    node = nodes.new("ShaderNodeVectorTransform")
    node.vector_type = "VECTOR"
    node.convert_from = "OBJECT"
    node.convert_to = "WORLD"
    node.label = label
    links.new(vector, _socket(node.inputs, "Vector"))
    return _socket(node.outputs, "Vector")


def _basis_world(nodes, links, name: str, short: str):
    raw = _attribute_gltf_vector(nodes, name)
    obj = gltf_to_blender_object_vector(
        nodes, links, raw, f"T6 exact {short}"
    )
    return _object_to_world(
        nodes, links, obj, f"T6 exact {short} Blender-object->world"
    )


def reconstruct_world_normal(nodes, links, xy):
    normal = _basis_world(nodes, links, "_T6_WORLD_NORMAL", "N")
    tangent = _basis_world(nodes, links, "_T6_WORLD_TANGENT", "T")
    binormal = _basis_world(nodes, links, "_T6_WORLD_BINORMAL", "B")
    tx = v1._scale_vector(nodes, links, tangent, xy[0], "T6 layeredNormalX * T")
    by = v1._scale_vector(nodes, links, binormal, xy[1], "T6 layeredNormalY * B")
    raw = v1._add_vector(nodes, links, normal, tx, "T6 N + X*T")
    raw = v1._add_vector(nodes, links, raw, by, "T6 raw layered world normal")
    normalized = nodes.new("ShaderNodeVectorMath")
    normalized.operation = "NORMALIZE"
    normalized.label = "T6 retail normalize(rawNormal)"
    links.new(raw, normalized.inputs[0])
    return normalized.outputs["Vector"]
