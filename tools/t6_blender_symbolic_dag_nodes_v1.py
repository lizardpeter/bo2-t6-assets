#!/usr/bin/env python3
"""Compile exact T6 scalar symbolic shader DAGs into Blender math nodes.

The input node vocabulary is produced by the retained T6 SM4 symbolic tools.
This module is intentionally resource-agnostic: callers provide resolvers for
`symbol` and `textureSample` leaves.  It handles only operations whose scalar
semantics can be represented faithfully with Blender shader nodes; unsupported
SM4/bitwise behavior fails closed rather than being approximated.

This is the common compiler needed to lower the 34 exact Nuketown generated
slot-4 final-output DAGs without hand-writing 34 Blender shaders.
"""
from __future__ import annotations

import struct
from typing import Any, Callable

try:
    import bpy  # type: ignore
except ImportError:
    bpy = None

FORMAT = "t6-blender-symbolic-dag-nodes-v1"


class BlenderSymbolicDagError(RuntimeError):
    pass


def _socket(collection, name: str):
    value = collection.get(name)
    if value is None:
        raise BlenderSymbolicDagError(f"Blender node lacks {name!r} socket")
    return value


def literal32(bits: str) -> float:
    text = str(bits)
    if len(text) != 8 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise BlenderSymbolicDagError(f"invalid literal32 bits {bits!r}")
    return struct.unpack("<f", struct.pack("<I", int(text, 16)))[0]


def _is_socket(value: Any) -> bool:
    return hasattr(value, "is_output") or value.__class__.__name__.startswith("NodeSocket")


def _set_or_link(links, socket, value) -> None:
    if _is_socket(value):
        links.new(value, socket)
    else:
        socket.default_value = float(value)


def _math(nodes, links, operation: str, args: list[Any], label: str):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    node.label = label
    for index, value in enumerate(args):
        if index >= len(node.inputs):
            raise BlenderSymbolicDagError(
                f"Blender Math {operation} exposes only {len(node.inputs)} inputs for {len(args)} arguments"
            )
        _set_or_link(links, node.inputs[index], value)
    return node.outputs[0]


def _one_minus(nodes, links, value, label: str):
    return _math(nodes, links, "SUBTRACT", [1.0, value], label)


def _boolize(nodes, links, value, label: str):
    # Exact T6 symbolic branch tests define nonzero as true. Blender Math
    # COMPARE with epsilon=0 is exact equality; invert equality-to-zero.
    eq_zero = _math(nodes, links, "COMPARE", [value, 0.0, 0.0], label + " == 0")
    return _one_minus(nodes, links, eq_zero, label + " != 0")


def _select(nodes, links, cond, a, b, label: str):
    # T6 movc/select chooses A when condition is nonzero. Normalize condition
    # to 0/1, then exact scalar mix = b + c*(a-b).
    c = _boolize(nodes, links, cond, label + " condition")
    delta = _math(nodes, links, "SUBTRACT", [a, b], label + " a-b")
    weighted = _math(nodes, links, "MULTIPLY", [c, delta], label + " c*(a-b)")
    return _math(nodes, links, "ADD", [b, weighted], label)


def _round_mode(nodes, links, op: str, value, label: str):
    mapping = {
        "round_ni": "FLOOR",
        "round_pi": "CEIL",
        "round_z": "TRUNC",
        "round_ne": "ROUND",
    }
    operation = mapping.get(op)
    if operation is None:
        raise BlenderSymbolicDagError(f"unsupported round op {op!r}")
    return _math(nodes, links, operation, [value], label)


def _compile_op(nodes, links, op: str, args: list[Any], node_id: int):
    label = f"T6 DAG n{node_id} {op}"
    binary = {
        "add": "ADD",
        "mul": "MULTIPLY",
        "div": "DIVIDE",
        "min": "MINIMUM",
        "max": "MAXIMUM",
        "lt": "LESS_THAN",
        "eq": "COMPARE",
    }
    unary = {
        "abs": "ABSOLUTE",
        "sqrt": "SQRT",
        "exp": "EXPONENT",
        "log": "LOGARITHM",
        "frc": "FRACT",
        "sin": "SINE",
        "cos": "COSINE",
    }
    if op in binary:
        if len(args) != 2:
            raise BlenderSymbolicDagError(f"{op} expects two arguments")
        if op == "eq":
            return _math(nodes, links, "COMPARE", [args[0], args[1], 0.0], label)
        return _math(nodes, links, binary[op], args, label)
    if op in unary:
        if len(args) != 1:
            raise BlenderSymbolicDagError(f"{op} expects one argument")
        return _math(nodes, links, unary[op], args, label)
    if op == "neg":
        if len(args) != 1:
            raise BlenderSymbolicDagError("neg expects one argument")
        return _math(nodes, links, "MULTIPLY", [args[0], -1.0], label)
    if op == "rcp":
        if len(args) != 1:
            raise BlenderSymbolicDagError("rcp expects one argument")
        return _math(nodes, links, "DIVIDE", [1.0, args[0]], label)
    if op == "rsq":
        if len(args) != 1:
            raise BlenderSymbolicDagError("rsq expects one argument")
        root = _math(nodes, links, "SQRT", [args[0]], label + " sqrt")
        return _math(nodes, links, "DIVIDE", [1.0, root], label)
    if op == "saturate":
        if len(args) != 1:
            raise BlenderSymbolicDagError("saturate expects one argument")
        return _math(nodes, links, "CLAMP", [args[0], 0.0, 1.0], label)
    if op == "ge":
        if len(args) != 2:
            raise BlenderSymbolicDagError("ge expects two arguments")
        lt = _math(nodes, links, "LESS_THAN", args, label + " <")
        return _one_minus(nodes, links, lt, label)
    if op == "ne":
        if len(args) != 2:
            raise BlenderSymbolicDagError("ne expects two arguments")
        eq = _math(nodes, links, "COMPARE", [args[0], args[1], 0.0], label + " ==")
        return _one_minus(nodes, links, eq, label)
    if op in {"test_nonzero", "test_zero"}:
        if len(args) != 1:
            raise BlenderSymbolicDagError(f"{op} expects one argument")
        nz = _boolize(nodes, links, args[0], label)
        return nz if op == "test_nonzero" else _one_minus(nodes, links, nz, label + " invert")
    if op == "not_bool":
        if len(args) != 1:
            raise BlenderSymbolicDagError("not_bool expects one argument")
        return _one_minus(nodes, links, _boolize(nodes, links, args[0], label), label)
    if op == "and_bool":
        if len(args) != 2:
            raise BlenderSymbolicDagError("and_bool expects two arguments")
        a = _boolize(nodes, links, args[0], label + " a")
        b = _boolize(nodes, links, args[1], label + " b")
        return _math(nodes, links, "MULTIPLY", [a, b], label)
    if op == "select":
        if len(args) != 3:
            raise BlenderSymbolicDagError("select expects condition,a,b")
        return _select(nodes, links, args[0], args[1], args[2], label)
    if op in {"round_ni", "round_ne", "round_pi", "round_z"}:
        if len(args) != 1:
            raise BlenderSymbolicDagError(f"{op} expects one argument")
        return _round_mode(nodes, links, op, args[0], label)
    if op in {"and", "or"}:
        raise BlenderSymbolicDagError(
            f"SM4 bitwise op {op!r} is not lowered to float Blender Math; exact bit semantics require a dedicated adapter/bake"
        )
    raise BlenderSymbolicDagError(f"unsupported T6 DAG op {op!r}")


def compile_scalar_dag(
    nodes,
    links,
    dag_nodes: list[dict],
    root_node: int,
    *,
    symbol_resolver: Callable[[str], Any],
    texture_resolver: Callable[[dict, list[Any]], Any],
) -> tuple[Any, dict]:
    """Compile one scalar output root and return `(socket_or_float, stats)`.

    `symbol_resolver(name)` must return a Blender scalar socket or literal.
    `texture_resolver(node, compiled_args)` must return the selected scalar
    channel for that exact symbolic `textureSample` leaf.
    """
    if bpy is None:
        raise BlenderSymbolicDagError("bpy unavailable; run DAG lowering inside Blender")
    if not isinstance(dag_nodes, list) or not dag_nodes:
        raise BlenderSymbolicDagError("DAG nodes must be a non-empty list")
    by_id = {}
    for row in dag_nodes:
        node_id = int(row.get("id", -1))
        if node_id < 0 or node_id in by_id:
            raise BlenderSymbolicDagError(f"invalid/duplicate DAG node id {node_id}")
        by_id[node_id] = row
    cache: dict[int, Any] = {}
    counts: dict[str, int] = {}

    def visit(node_id: int):
        if node_id in cache:
            return cache[node_id]
        row = by_id.get(node_id)
        if row is None:
            raise BlenderSymbolicDagError(f"DAG references missing node {node_id}")
        kind = str(row.get("kind") or "")
        counts[kind] = counts.get(kind, 0) + 1
        args = [visit(int(child)) for child in row.get("args", [])]
        if kind == "literal32":
            value = literal32(str(row.get("bits") or ""))
        elif kind == "symbol":
            name = str(row.get("name") or "")
            if not name:
                raise BlenderSymbolicDagError(f"symbol node {node_id} has empty name")
            value = symbol_resolver(name)
        elif kind == "textureSample":
            value = texture_resolver(row, args)
        elif kind == "op":
            value = _compile_op(nodes, links, str(row.get("op") or ""), args, node_id)
        elif kind == "undefined":
            raise BlenderSymbolicDagError(f"reachable undefined DAG node {node_id}: {row.get('name')!r}")
        else:
            raise BlenderSymbolicDagError(f"unsupported T6 DAG node kind {kind!r}")
        cache[node_id] = value
        return value

    result = visit(int(root_node))
    return result, {
        "format": FORMAT,
        "rootNode": int(root_node),
        "compiledUniqueNodeCount": len(cache),
        "kindCounts": dict(sorted(counts.items())),
        "cacheHitPotential": len(dag_nodes) - len(cache),
    }
