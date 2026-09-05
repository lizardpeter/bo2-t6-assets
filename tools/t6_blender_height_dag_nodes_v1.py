#!/usr/bin/env python3
"""Compile exact serialized T6 generated vN scalar DAGs to Blender Math nodes.

This module is intentionally narrow. It does not discover shader semantics and it
does not invent a generic height-blend equation. It accepts only the complete
renderer-neutral contracts embedded by Nuketown recipe recovery v4:

- ``heightWeightDagsV1``: exact shader-specific forensic scalar DAG;
- ``heightConstantBindingsV1``: exact per-Material cbuffer scalar values;
- ``heightLeafBindingsV1``: exact raw-input/sample bindings for the solved layer.

The compiler preserves DAG child order. Blender is an authoring preview backend,
so this proves graph/topology/equation fidelity, not bit-identical GPU rounding
with the retail D3D11 shader.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from t6_generated_height_weight_dag_v1 import validate_forensic_dag


HEIGHT_DAG_KEY = "heightWeightDagsV1"
HEIGHT_CONSTANT_KEY = "heightConstantBindingsV1"
HEIGHT_LEAF_KEY = "heightLeafBindingsV1"


class BlenderHeightDagError(RuntimeError):
    pass


@dataclass(frozen=True)
class HeightDagPlan:
    layer_index: int
    dag: dict
    vertex_leaf_names: tuple[str, ...]
    sample_leaves: tuple[tuple[str, str], ...]
    constant_values: dict[str, float]
    forensic_sha256: str
    raw_vertex_component: str


def _one_layer(payload: dict, layer_index: int, label: str) -> dict:
    rows = payload.get("layers")
    if not isinstance(rows, list):
        raise BlenderHeightDagError(f"{label} has no layers list")
    matches = [row for row in rows if int(row.get("layerIndex", -1)) == layer_index]
    if len(matches) != 1:
        raise BlenderHeightDagError(
            f"{label} layer {layer_index} matched {len(matches)} rows, expected exactly one"
        )
    return matches[0]


def prepare_height_dag_plan(recipe: dict, layer_index: int) -> HeightDagPlan:
    height = recipe.get(HEIGHT_DAG_KEY)
    constants = recipe.get(HEIGHT_CONSTANT_KEY)
    leaves = recipe.get(HEIGHT_LEAF_KEY)
    if not isinstance(height, dict):
        raise BlenderHeightDagError(f"layer {layer_index}: recipe lacks {HEIGHT_DAG_KEY}")
    if not isinstance(constants, dict):
        raise BlenderHeightDagError(f"layer {layer_index}: recipe lacks {HEIGHT_CONSTANT_KEY}")
    if not isinstance(leaves, dict):
        raise BlenderHeightDagError(f"layer {layer_index}: recipe lacks {HEIGHT_LEAF_KEY}")
    if not bool(leaves.get("allLeavesExact")):
        raise BlenderHeightDagError(f"layer {layer_index}: height leaf coverage is not exact")

    hrow = _one_layer(height, layer_index, HEIGHT_DAG_KEY)
    lrow = _one_layer(leaves, layer_index, HEIGHT_LEAF_KEY)
    dag = hrow.get("forensicDag")
    if not isinstance(dag, dict):
        raise BlenderHeightDagError(f"layer {layer_index}: missing forensic DAG")
    try:
        validate_forensic_dag(dag)
    except Exception as exc:
        raise BlenderHeightDagError(f"layer {layer_index}: invalid forensic DAG: {exc}") from exc

    if lrow.get("forensicDagSha256") not in (None, dag.get("forensicDagSha256")):
        raise BlenderHeightDagError(
            f"layer {layer_index}: leaf-binding forensic SHA disagrees with DAG"
        )

    normalized = lrow.get("normalizedVertexWeight")
    if not isinstance(normalized, dict):
        raise BlenderHeightDagError(f"layer {layer_index}: missing normalized vertex-weight binding")
    if normalized.get("attribute") != "_T6_LAYER_WEIGHTS":
        raise BlenderHeightDagError(
            f"layer {layer_index}: unexpected height weight attribute {normalized.get('attribute')!r}"
        )
    expected_component = {1: "G", 2: "B", 3: "A"}.get(layer_index)
    component = str(normalized.get("component") or "")
    if component != expected_component:
        raise BlenderHeightDagError(
            f"layer {layer_index}: normalized component {component!r} != {expected_component!r}"
        )

    raw_inputs = lrow.get("rawVertexInputs")
    if not isinstance(raw_inputs, list) or len(raw_inputs) != 1 or not str(raw_inputs[0]):
        raise BlenderHeightDagError(
            f"layer {layer_index}: expected exactly one exact raw vertex input binding"
        )
    vertex_leaf_names = (str(raw_inputs[0]),)

    sample_bindings = lrow.get("sampleBindings")
    if not isinstance(sample_bindings, list) or not sample_bindings:
        raise BlenderHeightDagError(f"layer {layer_index}: missing exact sample bindings")
    sample_leaves: list[tuple[str, str]] = []
    for row in sample_bindings:
        portable = row.get("portableDependency")
        if not isinstance(portable, dict):
            raise BlenderHeightDagError(
                f"layer {layer_index}: sample binding lacks portable dependency"
            )
        if int(portable.get("layerIndex", -1)) != layer_index or portable.get("role") != "colorMap":
            raise BlenderHeightDagError(
                f"layer {layer_index}: sample portable dependency is not this layer's colorMap"
            )
        resource = str(row.get("resource") or "")
        channel = str(row.get("channel") or "")
        if not resource or channel != "w":
            raise BlenderHeightDagError(
                f"layer {layer_index}: height sample must be exact alpha channel, got {resource!r}.{channel}"
            )
        sample_leaves.append((resource, channel))
    sample_leaves = sorted(set(sample_leaves))

    constant_rows = constants.get("bindings")
    if not isinstance(constant_rows, list):
        raise BlenderHeightDagError(f"layer {layer_index}: constant bindings are not a list")
    constant_values: dict[str, float] = {}
    for row in constant_rows:
        leaf = str(row.get("leaf") or "")
        material_constant = row.get("materialConstant")
        if not leaf or not isinstance(material_constant, dict):
            raise BlenderHeightDagError(f"layer {layer_index}: malformed constant binding row")
        if leaf in constant_values:
            raise BlenderHeightDagError(f"layer {layer_index}: duplicate constant binding {leaf!r}")
        try:
            constant_values[leaf] = float(material_constant["value"])
        except Exception as exc:
            raise BlenderHeightDagError(
                f"layer {layer_index}: nonnumeric exact constant value for {leaf!r}"
            ) from exc

    dag_inputs = sorted(
        str(node.get("name") or "") for node in dag["nodes"] if node.get("kind") == "input"
    )
    dag_constants = sorted(
        str(node.get("name") or "") for node in dag["nodes"] if node.get("kind") == "cb"
    )
    dag_samples = sorted({
        (str(node.get("resource") or ""), str(node.get("channel") or ""))
        for node in dag["nodes"] if node.get("kind") == "sample"
    })
    if dag_inputs != sorted(vertex_leaf_names):
        raise BlenderHeightDagError(
            f"layer {layer_index}: DAG inputs {dag_inputs} != exact bindings {sorted(vertex_leaf_names)}"
        )
    if dag_constants != sorted(constant_values):
        raise BlenderHeightDagError(
            f"layer {layer_index}: DAG constants {dag_constants} != exact bindings {sorted(constant_values)}"
        )
    if dag_samples != sample_leaves:
        raise BlenderHeightDagError(
            f"layer {layer_index}: DAG samples {dag_samples} != exact bindings {sample_leaves}"
        )

    return HeightDagPlan(
        layer_index=layer_index,
        dag=dag,
        vertex_leaf_names=vertex_leaf_names,
        sample_leaves=tuple(sample_leaves),
        constant_values=constant_values,
        forensic_sha256=str(dag["forensicDagSha256"]),
        raw_vertex_component=component,
    )


def _math(nodes, operation: str, label: str):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    node.label = label
    return node


def _value(nodes, value: float, label: str):
    node = nodes.new("ShaderNodeValue")
    node.label = label
    node.outputs[0].default_value = float(value)
    return node.outputs[0]


def _binary(nodes, links, operation: str, a, b, label: str):
    node = _math(nodes, operation, label)
    links.new(a, node.inputs[0])
    links.new(b, node.inputs[1])
    return node.outputs[0]


def _unary(nodes, links, operation: str, a, label: str):
    node = _math(nodes, operation, label)
    links.new(a, node.inputs[0])
    return node.outputs[0]


def _neg(nodes, links, a, label: str):
    node = _math(nodes, "MULTIPLY", label)
    links.new(a, node.inputs[0])
    node.inputs[1].default_value = -1.0
    return node.outputs[0]


def _sat(nodes, links, a, label: str):
    lo = _math(nodes, "MAXIMUM", label + " max(0)")
    links.new(a, lo.inputs[0])
    lo.inputs[1].default_value = 0.0
    hi = _math(nodes, "MINIMUM", label + " min(1)")
    links.new(lo.outputs[0], hi.inputs[0])
    hi.inputs[1].default_value = 1.0
    return hi.outputs[0]


def _exp2(nodes, links, a, label: str):
    node = _math(nodes, "POWER", label + " exp2")
    node.inputs[0].default_value = 2.0
    links.new(a, node.inputs[1])
    return node.outputs[0]


def _log2(nodes, links, a, label: str):
    node = _math(nodes, "LOGARITHM", label + " log2")
    links.new(a, node.inputs[0])
    node.inputs[1].default_value = 2.0
    return node.outputs[0]


def _rcp(nodes, links, a, label: str):
    node = _math(nodes, "DIVIDE", label + " reciprocal")
    node.inputs[0].default_value = 1.0
    links.new(a, node.inputs[1])
    return node.outputs[0]


def _ge_finite(nodes, links, a, b, label: str):
    # For finite scalar inputs: a >= b == 1 - (a < b).
    lt = _binary(nodes, links, "LESS_THAN", a, b, label + " <")
    node = _math(nodes, "SUBTRACT", label + " >=")
    node.inputs[0].default_value = 1.0
    links.new(lt, node.inputs[1])
    return node.outputs[0]


def _eq_finite(nodes, links, a, b, label: str):
    # Equality for finite scalars: neither a<b nor b<a.
    ab = _binary(nodes, links, "LESS_THAN", a, b, label + " a<b")
    ba = _binary(nodes, links, "LESS_THAN", b, a, label + " b<a")
    neq = _binary(nodes, links, "MAXIMUM", ab, ba, label + " ne")
    node = _math(nodes, "SUBTRACT", label + " eq")
    node.inputs[0].default_value = 1.0
    links.new(neq, node.inputs[1])
    return node.outputs[0]


def _ne_finite(nodes, links, a, b, label: str):
    ab = _binary(nodes, links, "LESS_THAN", a, b, label + " a<b")
    ba = _binary(nodes, links, "LESS_THAN", b, a, label + " b<a")
    return _binary(nodes, links, "MAXIMUM", ab, ba, label + " ne")


def _select_boolean(nodes, links, condition, when_true, when_false, label: str):
    # Serialized comparison nodes produce 0/1. Preserve select arithmetic without
    # relying on Blender's color Mix conversion: false + cond*(true-false).
    delta = _binary(nodes, links, "SUBTRACT", when_true, when_false, label + " delta")
    scaled = _binary(nodes, links, "MULTIPLY", condition, delta, label + " cond*delta")
    return _binary(nodes, links, "ADD", when_false, scaled, label + " select")


def compile_height_dag(
    nodes,
    links,
    plan: HeightDagPlan,
    *,
    vertex_socket,
    sample_sockets: dict[tuple[str, str], Any],
):
    """Compile one validated exact scalar DAG and return its Blender value socket."""
    values: list[Any] = []
    dag_nodes = plan.dag["nodes"]
    for index, spec in enumerate(dag_nodes):
        kind = str(spec.get("kind") or "")
        label = f"T6 vN L{plan.layer_index} #{index} {kind}"
        args = [values[int(child)] for child in spec.get("args", [])]

        if kind == "input":
            name = str(spec.get("name") or "")
            if name not in plan.vertex_leaf_names:
                raise BlenderHeightDagError(f"{label}: unbound input leaf {name!r}")
            out = vertex_socket
        elif kind == "cb":
            name = str(spec.get("name") or "")
            if name not in plan.constant_values:
                raise BlenderHeightDagError(f"{label}: unbound constant leaf {name!r}")
            out = _value(nodes, plan.constant_values[name], label + f" = {name}")
        elif kind == "lit":
            try:
                literal = float(spec["value"])
            except Exception as exc:
                raise BlenderHeightDagError(f"{label}: invalid literal {spec.get('value')!r}") from exc
            out = _value(nodes, literal, label)
        elif kind == "sample":
            key = (str(spec.get("resource") or ""), str(spec.get("channel") or ""))
            out = sample_sockets.get(key)
            if out is None:
                raise BlenderHeightDagError(f"{label}: no exact sample socket for {key!r}")
        elif kind == "add" and len(args) == 2:
            out = _binary(nodes, links, "ADD", args[0], args[1], label)
        elif kind == "mul" and len(args) == 2:
            out = _binary(nodes, links, "MULTIPLY", args[0], args[1], label)
        elif kind == "div" and len(args) == 2:
            out = _binary(nodes, links, "DIVIDE", args[0], args[1], label)
        elif kind == "min" and len(args) == 2:
            out = _binary(nodes, links, "MINIMUM", args[0], args[1], label)
        elif kind == "max" and len(args) == 2:
            out = _binary(nodes, links, "MAXIMUM", args[0], args[1], label)
        elif kind == "neg" and len(args) == 1:
            out = _neg(nodes, links, args[0], label)
        elif kind in ("sat", "saturate") and len(args) == 1:
            out = _sat(nodes, links, args[0], label)
        elif kind == "abs" and len(args) == 1:
            out = _unary(nodes, links, "ABSOLUTE", args[0], label)
        elif kind == "exp" and len(args) == 1:
            out = _exp2(nodes, links, args[0], label)
        elif kind == "log" and len(args) == 1:
            out = _log2(nodes, links, args[0], label)
        elif kind == "rcp" and len(args) == 1:
            out = _rcp(nodes, links, args[0], label)
        elif kind == "sqrt" and len(args) == 1:
            out = _unary(nodes, links, "SQRT", args[0], label)
        elif kind == "rsq" and len(args) == 1:
            out = _unary(nodes, links, "INVERSE_SQRT", args[0], label)
        elif kind == "frc" and len(args) == 1:
            out = _unary(nodes, links, "FRACT", args[0], label)
        elif kind == "lt" and len(args) == 2:
            out = _binary(nodes, links, "LESS_THAN", args[0], args[1], label)
        elif kind == "ge" and len(args) == 2:
            out = _ge_finite(nodes, links, args[0], args[1], label)
        elif kind == "eq" and len(args) == 2:
            out = _eq_finite(nodes, links, args[0], args[1], label)
        elif kind == "ne" and len(args) == 2:
            out = _ne_finite(nodes, links, args[0], args[1], label)
        elif kind == "select" and len(args) == 3:
            parent_ids = [int(child) for child in spec.get("args", [])]
            condition_kind = str(dag_nodes[parent_ids[0]].get("kind") or "")
            if condition_kind not in ("lt", "ge", "eq", "ne"):
                raise BlenderHeightDagError(
                    f"{label}: select condition {condition_kind!r} is not proven boolean 0/1"
                )
            out = _select_boolean(nodes, links, args[0], args[1], args[2], label)
        else:
            raise BlenderHeightDagError(
                f"{label}: unsupported exact DAG node or arity ({kind!r}, {len(args)})"
            )
        values.append(out)

    root = int(plan.dag["root"])
    if not 0 <= root < len(values):
        raise BlenderHeightDagError(f"layer {plan.layer_index}: compiled root out of range")
    return values[root]
