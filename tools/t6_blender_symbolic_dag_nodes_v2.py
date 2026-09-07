#!/usr/bin/env python3
"""T6 symbolic DAG -> Blender compiler v2: harden SM4 operation semantics.

v1 established the generic compiler architecture. v2 corrects/locks operations
where Blender's similarly named Math modes must not be assumed equivalent:

- SM4 `exp` is base-2: compile as 2^x;
- SM4 `log` is base-2: compile as log(x, 2);
- saturate is explicit min(max(x,0),1), not a guessed node mode;
- round_ne (nearest-even) remains fail-closed until Blender tie semantics are
  independently proven;
- bitwise and/or remain fail-closed.

All other v1 resource-agnostic contracts are preserved.
"""
from __future__ import annotations

import t6_blender_symbolic_dag_nodes_v1 as v1

FORMAT = "t6-blender-symbolic-dag-nodes-v2"
BlenderSymbolicDagError = v1.BlenderSymbolicDagError
bpy = v1.bpy
literal32 = v1.literal32
_BASE_COMPILE_OP = v1._compile_op


def _compile_op_v2(nodes, links, op: str, args: list, node_id: int):
    label = f"T6 DAG n{node_id} {op}"
    if op == "exp":
        if len(args) != 1:
            raise BlenderSymbolicDagError("SM4 exp expects one argument")
        return v1._math(nodes, links, "POWER", [2.0, args[0]], label + " = 2^x")
    if op == "log":
        if len(args) != 1:
            raise BlenderSymbolicDagError("SM4 log expects one argument")
        return v1._math(nodes, links, "LOGARITHM", [args[0], 2.0], label + " = log2(x)")
    if op == "saturate":
        if len(args) != 1:
            raise BlenderSymbolicDagError("saturate expects one argument")
        lower = v1._math(nodes, links, "MAXIMUM", [args[0], 0.0], label + " max(x,0)")
        return v1._math(nodes, links, "MINIMUM", [lower, 1.0], label + " min(...,1)")
    if op == "round_ne":
        raise BlenderSymbolicDagError(
            "SM4 round_ne is nearest-even; Blender ROUND tie semantics are not yet proven equivalent"
        )
    return _BASE_COMPILE_OP(nodes, links, op, args, node_id)


def compile_scalar_dag(
    nodes,
    links,
    dag_nodes: list[dict],
    root_node: int,
    *,
    symbol_resolver,
    texture_resolver,
):
    old = v1._compile_op
    v1._compile_op = _compile_op_v2
    try:
        value, stats = v1.compile_scalar_dag(
            nodes,
            links,
            dag_nodes,
            root_node,
            symbol_resolver=symbol_resolver,
            texture_resolver=texture_resolver,
        )
    finally:
        v1._compile_op = old
    stats = dict(stats)
    stats["format"] = FORMAT
    stats["sm4SemanticHardening"] = {
        "exp": "2^x",
        "log": "log2(x)",
        "saturate": "min(max(x,0),1)",
        "round_ne": "fail-closed pending tie-semantics proof",
        "bitwiseAndOr": "fail-closed pending exact adapter/bake",
    }
    return value, stats
