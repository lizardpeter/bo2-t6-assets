#!/usr/bin/env python3
"""Build the source-closed T6 generated layered-normal graph in Blender.

Inputs are intentionally stronger than a generic normal-map workflow:

* recovery-v9 `normalSampleDecodeV2` with exact base/secondary scalar DAGs;
* v15 `normalTransformShaderBindingsV1` with dual-proof transform ownership;
* v16 `layeredNormalBasisV1` with exact paired-VS N/T/B roles;
* v20 custom `_T6_WORLD_NORMAL/_T6_WORLD_TANGENT/_T6_WORLD_BINORMAL`
  vertex attributes preserving retail interpolation topology.

The caller supplies the exact RGB compositor factor socket for each secondary
layer, so diffuse and normal recurrences cannot silently diverge.  This module
never uses Blender's Normal Map or Tangent nodes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import t6_blender_normal_decode_dag_nodes_v1 as decode_nodes
from t6_generated_shader_recipe_contract_v1 import validate_recipe

NORMAL_STATE_KEY = "normalSampleDecodeV2"
TRANSFORM_KEY = "normalTransformShaderBindingsV1"
BASIS_KEY = "layeredNormalBasisV1"
NORMAL_STATE_FORMAT = "t6-generated-normal-sample-decode-recipe-v2"
BASIS_FORMAT = "t6-generated-layered-normal-basis-recipe-v1"
BASIS_ATTRIBUTE_FORMAT_V2 = "t6-generated-normal-basis-attributes-v2"


class BlenderGeneratedNormalError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalPlaybackPlan:
    material: str
    technique_set: str
    baseline: dict
    layers: dict[int, dict]
    transform_bindings: dict[int, dict]
    basis: dict


def prepare_plan(recipe: dict, *, technique_set: str, normal_layers: list[int]) -> NormalPlaybackPlan:
    canonical = validate_recipe(recipe)
    material = str(canonical.get("material") or "")
    if canonical.get("techniqueSet") != technique_set:
        raise BlenderGeneratedNormalError(
            f"{material!r}: canonical TechniqueSet disagrees with Blender material"
        )
    expected_layers = sorted(int(v) for v in normal_layers)
    if not expected_layers:
        raise BlenderGeneratedNormalError(
            f"{material!r}: normal playback plan requested with no secondary normal layers"
        )

    state = canonical.get(NORMAL_STATE_KEY)
    if not isinstance(state, dict) or state.get("format") != NORMAL_STATE_FORMAT:
        raise BlenderGeneratedNormalError(
            f"{material!r}: exact {NORMAL_STATE_KEY} v2 is absent"
        )
    if state.get("material") != material or state.get("techniqueSet") != technique_set:
        raise BlenderGeneratedNormalError(
            f"{material!r}: normal state material/TechniqueSet identity disagrees"
        )
    if state.get("pixelShaderArchetype") != canonical.get("pixelShaderArchetype"):
        raise BlenderGeneratedNormalError(
            f"{material!r}: normal state pixel-shader identity disagrees"
        )
    if not bool(state.get("allDecodeLeavesExact")):
        raise BlenderGeneratedNormalError(
            f"{material!r}: normal sample decode leaves are not exact"
        )
    baseline = state.get("baseline")
    if not isinstance(baseline, dict) or str(baseline.get("mode") or "") not in ("zero", "explicit_normal"):
        raise BlenderGeneratedNormalError(
            f"{material!r}: normal baseline is not exact zero/explicit_normal"
        )
    if baseline["mode"] == "zero":
        if baseline.get("components") not in ([], None) or baseline.get("normalResource") is not None:
            raise BlenderGeneratedNormalError(
                f"{material!r}: zero baseline carries normal sample data"
            )
    else:
        portable = baseline.get("portableDependency")
        if not isinstance(portable, dict) or int(portable.get("layerIndex", -1)) != 0 or portable.get("role") != "normalMap":
            raise BlenderGeneratedNormalError(
                f"{material!r}: explicit base normal lacks exact layer0 normalMap dependency"
            )
        if str(baseline.get("normalResource") or "") != "normalMapSampler":
            raise BlenderGeneratedNormalError(
                f"{material!r}: unexpected base normal resource {baseline.get('normalResource')!r}"
            )
        if not str(baseline.get("materialArgument") or ""):
            raise BlenderGeneratedNormalError(
                f"{material!r}: explicit base normal lacks exact material argument"
            )

    state_rows = state.get("layers")
    if not isinstance(state_rows, list):
        raise BlenderGeneratedNormalError(f"{material!r}: normal state layers are not a list")
    by_layer = {int(row["layerIndex"]): row for row in state_rows}
    if sorted(by_layer) != expected_layers:
        raise BlenderGeneratedNormalError(
            f"{material!r}: normal state layers {sorted(by_layer)} != TechniqueSet normal layers {expected_layers}"
        )

    transform = canonical.get(TRANSFORM_KEY)
    if not isinstance(transform, dict) or not bool(transform.get("crossProofAgreement")):
        raise BlenderGeneratedNormalError(
            f"{material!r}: v15 dual-proof normal-transform ownership is absent"
        )
    transform_rows = transform.get("secondaryNormalBindings")
    if not isinstance(transform_rows, list):
        raise BlenderGeneratedNormalError(f"{material!r}: transform binding rows are absent")
    transform_by_layer = {int(row["layerIndex"]): row for row in transform_rows}
    if sorted(transform_by_layer) != expected_layers:
        raise BlenderGeneratedNormalError(
            f"{material!r}: transform layers {sorted(transform_by_layer)} != {expected_layers}"
        )

    for layer in expected_layers:
        state_row = by_layer[layer]
        transform_row = transform_by_layer[layer]
        for key in ("mode",):
            state_mode = str(state_row.get("transformMode") or "")
            transform_mode = str(transform_row.get(key) or "")
            if state_mode != transform_mode:
                raise BlenderGeneratedNormalError(
                    f"{material!r} layer {layer}: decode/transform mode disagreement {state_mode!r}/{transform_mode!r}"
                )
        mode = str(state_row.get("transformMode") or "")
        if mode == "direct":
            if state_row.get("normalTransformIndex") is not None or state_row.get("normalTransformAttribute") is not None:
                raise BlenderGeneratedNormalError(
                    f"{material!r} layer {layer}: direct normal state carries transform metadata"
                )
        elif mode == "transform2x2":
            index = int(state_row.get("normalTransformIndex", -1))
            attribute = str(state_row.get("normalTransformAttribute") or "")
            if index not in (0, 1) or attribute != f"_T6_NORMAL_TRANSFORM_{index}":
                raise BlenderGeneratedNormalError(
                    f"{material!r} layer {layer}: malformed exact normal transform binding"
                )
            if transform_row.get("normalTransformIndex") != index or transform_row.get("attribute") != attribute:
                raise BlenderGeneratedNormalError(
                    f"{material!r} layer {layer}: v9/v15 transform identity disagrees"
                )
        else:
            raise BlenderGeneratedNormalError(
                f"{material!r} layer {layer}: unsupported normal transform mode {mode!r}"
            )
        portable = state_row.get("portableDependency")
        if not isinstance(portable, dict) or int(portable.get("layerIndex", -1)) != layer or portable.get("role") != "normalMap":
            raise BlenderGeneratedNormalError(
                f"{material!r} layer {layer}: normal state lacks exact portable dependency"
            )
        if not str(state_row.get("normalResource") or "") or not str(state_row.get("materialArgument") or ""):
            raise BlenderGeneratedNormalError(
                f"{material!r} layer {layer}: normal state resource/material argument is empty"
            )

    basis = canonical.get(BASIS_KEY)
    if not isinstance(basis, dict) or basis.get("format") != BASIS_FORMAT:
        raise BlenderGeneratedNormalError(
            f"{material!r}: exact paired-VS layeredNormalBasisV1 is absent"
        )
    if sorted(int(v) for v in basis.get("secondaryNormalLayers", [])) != expected_layers:
        raise BlenderGeneratedNormalError(
            f"{material!r}: basis attachment normal layers disagree"
        )
    roles = basis.get("directRoleMatches")
    if not isinstance(roles, dict):
        raise BlenderGeneratedNormalError(f"{material!r}: basis direct-role proof is absent")
    required_roles = (
        "baseIsWorldNormalFromNormal0",
        "xBasisIsWorldTangentFromTangent0",
        "yBasisExactCrossHandedness",
    )
    if any(not bool(roles.get(key)) for key in required_roles) or roles.get("yBasisPhysicalRole") != "worldBinormal":
        raise BlenderGeneratedNormalError(
            f"{material!r}: all three paired-VS physical normal basis roles are not exact"
        )

    return NormalPlaybackPlan(
        material=material,
        technique_set=technique_set,
        baseline=baseline,
        layers=by_layer,
        transform_bindings=transform_by_layer,
        basis=basis,
    )


def _socket(collection, *names):
    for name in names:
        value = collection.get(name)
        if value is not None:
            return value
    return None


def _separate_rg(nodes, links, color_socket, label: str):
    try:
        sep = nodes.new("ShaderNodeSeparateColor")
        if hasattr(sep, "mode"):
            sep.mode = "RGB"
        target = _socket(sep.inputs, "Color", "Image")
        red = _socket(sep.outputs, "Red", "R")
        green = _socket(sep.outputs, "Green", "G")
    except Exception:
        sep = nodes.new("ShaderNodeSeparateRGB")
        target = _socket(sep.inputs, "Image", "Color")
        red = _socket(sep.outputs, "R", "Red")
        green = _socket(sep.outputs, "G", "Green")
    if target is None or red is None or green is None:
        raise BlenderGeneratedNormalError("Blender cannot expose exact normal texture R/G channels")
    sep.label = label
    links.new(color_socket, target)
    return red, green


def compile_decode_pair(nodes, links, payload: dict, *, layer_index: int, texture_node):
    resource = str(payload.get("normalResource") or "")
    if not resource:
        raise BlenderGeneratedNormalError(f"layer {layer_index}: empty exact normal resource")
    try:
        px, py = decode_nodes.prepare_pair(
            payload,
            layer_index=layer_index,
            expected_resource=resource,
        )
    except decode_nodes.BlenderNormalDecodeDagError as exc:
        raise BlenderGeneratedNormalError(
            f"layer {layer_index}: exact normal decode plan failed: {exc}"
        ) from exc
    red, green = _separate_rg(
        nodes, links, texture_node.outputs["Color"], f"T6 L{layer_index} exact normal RG"
    )
    try:
        x = decode_nodes.compile_component(nodes, links, px, sample_socket=red)
        y = decode_nodes.compile_component(nodes, links, py, sample_socket=green)
    except decode_nodes.BlenderNormalDecodeDagError as exc:
        raise BlenderGeneratedNormalError(
            f"layer {layer_index}: exact normal decode node compilation failed: {exc}"
        ) from exc
    return (x, y), {
        "layer": layer_index,
        "resource": resource,
        "xDagSha256": px.forensic_sha256,
        "yDagSha256": py.forensic_sha256,
    }


def _math(nodes, operation: str, label: str):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    node.label = label
    return node


def _binary(nodes, links, operation: str, a, b, label: str):
    node = _math(nodes, operation, label)
    links.new(a, node.inputs[0]); links.new(b, node.inputs[1])
    return node.outputs[0]


def _value(nodes, value: float, label: str):
    node = nodes.new("ShaderNodeValue")
    node.label = label
    node.outputs[0].default_value = float(value)
    return node.outputs[0]


def _signed_unorm(nodes, links, value, label: str):
    two = _math(nodes, "MULTIPLY", label + " *2")
    links.new(value, two.inputs[0]); two.inputs[1].default_value = 2.0
    minus = _math(nodes, "ADD", label + " -1")
    links.new(two.outputs[0], minus.inputs[0]); minus.inputs[1].default_value = -1.0
    return minus.outputs[0]


def _matrix_components(nodes, links, attribute_name: str):
    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_name = attribute_name
    attr.label = f"T6 exact logical {attribute_name}"
    color = attr.outputs.get("Color")
    alpha = attr.outputs.get("Alpha")
    if color is None or alpha is None:
        raise BlenderGeneratedNormalError(
            f"Blender Attribute node cannot expose {attribute_name} VEC4"
        )
    red, green = _separate_rg(nodes, links, color, f"{attribute_name} m00/m01")
    # Need B as m10 too. Use a second compatible separator to avoid relying on
    # implementation-specific output indexing.
    try:
        sep = nodes.new("ShaderNodeSeparateColor")
        if hasattr(sep, "mode"):
            sep.mode = "RGB"
        target = _socket(sep.inputs, "Color", "Image")
        blue = _socket(sep.outputs, "Blue", "B")
    except Exception:
        sep = nodes.new("ShaderNodeSeparateRGB")
        target = _socket(sep.inputs, "Image", "Color")
        blue = _socket(sep.outputs, "B", "Blue")
    if target is None or blue is None:
        raise BlenderGeneratedNormalError("Blender cannot expose normal-transform B channel")
    links.new(color, target)
    return tuple(
        _signed_unorm(nodes, links, socket, f"{attribute_name} {name}")
        for socket, name in ((red, "m00"), (green, "m01"), (blue, "m10"), (alpha, "m11"))
    )


def apply_transform(nodes, links, xy, layer_row: dict):
    mode = str(layer_row.get("transformMode") or "")
    if mode == "direct":
        return xy
    if mode != "transform2x2":
        raise BlenderGeneratedNormalError(f"unsupported normal transform mode {mode!r}")
    attribute = str(layer_row.get("normalTransformAttribute") or "")
    if not attribute:
        raise BlenderGeneratedNormalError("transform2x2 normal layer has no exact attribute")
    m00, m01, m10, m11 = _matrix_components(nodes, links, attribute)
    x0 = _binary(nodes, links, "MULTIPLY", xy[0], m00, f"{attribute} x*m00")
    x1 = _binary(nodes, links, "MULTIPLY", xy[1], m01, f"{attribute} y*m01")
    out_x = _binary(nodes, links, "ADD", x0, x1, f"{attribute} transformed X")
    y0 = _binary(nodes, links, "MULTIPLY", xy[0], m10, f"{attribute} x*m10")
    y1 = _binary(nodes, links, "MULTIPLY", xy[1], m11, f"{attribute} y*m11")
    out_y = _binary(nodes, links, "ADD", y0, y1, f"{attribute} transformed Y")
    return out_x, out_y


def compose_xy(nodes, links, previous, layer_xy, factor, *, operation: str, layer_index: int):
    if operation not in ("blend", "threshold"):
        raise BlenderGeneratedNormalError(
            f"layer {layer_index}: layered normal recurrence does not support {operation!r}"
        )
    out = []
    for channel, prev, current in (("X", previous[0], layer_xy[0]), ("Y", previous[1], layer_xy[1])):
        delta = _binary(nodes, links, "SUBTRACT", current, prev, f"T6 L{layer_index} normal {channel} delta")
        weighted = _binary(nodes, links, "MULTIPLY", factor, delta, f"T6 L{layer_index} normal {channel} factor")
        out.append(_binary(nodes, links, "ADD", prev, weighted, f"T6 L{layer_index} normal {channel} recurrence"))
    return tuple(out)


def zero_baseline(nodes):
    return (
        _value(nodes, 0.0, "T6 exact zero normal baseline X"),
        _value(nodes, 0.0, "T6 exact zero normal baseline Y"),
    )


def _attribute_vector(nodes, name: str):
    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_name = name
    attr.label = f"T6 exact {name}"
    socket = attr.outputs.get("Vector") or attr.outputs.get("Color")
    if socket is None:
        raise BlenderGeneratedNormalError(f"Blender Attribute node cannot expose vector {name}")
    return socket


def _object_to_world(nodes, links, vector, label: str):
    node = nodes.new("ShaderNodeVectorTransform")
    node.vector_type = "VECTOR"
    node.convert_from = "OBJECT"
    node.convert_to = "WORLD"
    node.label = label
    links.new(vector, node.inputs["Vector"])
    return node.outputs["Vector"]


def _scale_vector(nodes, links, vector, scalar_value, label: str):
    combine = nodes.new("ShaderNodeCombineXYZ")
    combine.label = label + " scalar splat"
    for socket_name in ("X", "Y", "Z"):
        links.new(scalar_value, combine.inputs[socket_name])
    mul = nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    mul.label = label
    links.new(vector, mul.inputs[0]); links.new(combine.outputs["Vector"], mul.inputs[1])
    return mul.outputs["Vector"]


def _add_vector(nodes, links, a, b, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "ADD"
    node.label = label
    links.new(a, node.inputs[0]); links.new(b, node.inputs[1])
    return node.outputs["Vector"]


def reconstruct_world_normal(nodes, links, xy):
    normal = _object_to_world(
        nodes, links, _attribute_vector(nodes, "_T6_WORLD_NORMAL"), "T6 exact N object->world"
    )
    tangent = _object_to_world(
        nodes, links, _attribute_vector(nodes, "_T6_WORLD_TANGENT"), "T6 exact T object->world"
    )
    binormal = _object_to_world(
        nodes, links, _attribute_vector(nodes, "_T6_WORLD_BINORMAL"), "T6 exact B object->world"
    )
    tx = _scale_vector(nodes, links, tangent, xy[0], "T6 layeredNormalX * T")
    by = _scale_vector(nodes, links, binormal, xy[1], "T6 layeredNormalY * B")
    raw = _add_vector(nodes, links, normal, tx, "T6 N + X*T")
    raw = _add_vector(nodes, links, raw, by, "T6 raw layered world normal")
    normalized = nodes.new("ShaderNodeVectorMath")
    normalized.operation = "NORMALIZE"
    normalized.label = "T6 retail normalize(rawNormal)"
    links.new(raw, normalized.inputs[0])
    return normalized.outputs["Vector"]
