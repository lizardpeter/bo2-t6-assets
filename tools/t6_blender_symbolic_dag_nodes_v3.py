#!/usr/bin/env python3
"""T6 symbolic DAG -> Blender compiler v3: shared multi-output lowering.

v2 source-closes the scalar operation semantics needed by the retained T6 SM4
DAGs. Real pixel shaders write multiple o0 lanes whose roots share large parts
of the same DAG. Calling the scalar compiler independently for x/y/z/w would
recreate shared texture samples and arithmetic several times.

v3 lowers any number of named roots through one memoized traversal. Every exact
DAG node is therefore compiled at most once, preserving common-subexpression
identity across final outputs. Symbol and texture leaves remain caller-resolved
and unsupported v2 operations remain fail-closed.
"""
from __future__ import annotations

from typing import Any

import t6_blender_symbolic_dag_nodes_v1 as v1
import t6_blender_symbolic_dag_nodes_v2 as v2

FORMAT = "t6-blender-symbolic-dag-nodes-v3"
BlenderSymbolicDagError = v2.BlenderSymbolicDagError
bpy = v2.bpy
literal32 = v2.literal32


def compile_dag_roots(
    nodes,
    links,
    dag_nodes: list[dict],
    roots: dict[str, int],
    *,
    symbol_resolver,
    texture_resolver,
) -> tuple[dict[str, Any], dict]:
    if bpy is None:
        raise BlenderSymbolicDagError("bpy unavailable; run DAG lowering inside Blender")
    if not isinstance(dag_nodes, list) or not dag_nodes:
        raise BlenderSymbolicDagError("DAG nodes must be a non-empty list")
    if not isinstance(roots, dict) or not roots:
        raise BlenderSymbolicDagError("roots must be a non-empty mapping")

    by_id = {}
    for row in dag_nodes:
        node_id = int(row.get("id", -1))
        if node_id < 0 or node_id in by_id:
            raise BlenderSymbolicDagError(f"invalid/duplicate DAG node id {node_id}")
        by_id[node_id] = row

    cache: dict[int, Any] = {}
    counts: dict[str, int] = {}
    texture_calls = 0
    symbol_calls = 0

    def visit(node_id: int):
        nonlocal texture_calls, symbol_calls
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
            symbol_calls += 1
            value = symbol_resolver(name)
        elif kind == "textureSample":
            texture_calls += 1
            value = texture_resolver(row, args)
        elif kind == "op":
            value = v2._compile_op_v2(nodes, links, str(row.get("op") or ""), args, node_id)
        elif kind == "undefined":
            raise BlenderSymbolicDagError(f"reachable undefined DAG node {node_id}: {row.get('name')!r}")
        else:
            raise BlenderSymbolicDagError(f"unsupported T6 DAG node kind {kind!r}")
        cache[node_id] = value
        return value

    outputs = {name: visit(int(root)) for name, root in roots.items()}
    return outputs, {
        "format": FORMAT,
        "rootCount": len(roots),
        "roots": {name: int(root) for name, root in roots.items()},
        "compiledUniqueNodeCount": len(cache),
        "kindCounts": dict(sorted(counts.items())),
        "symbolResolverCallCount": symbol_calls,
        "textureResolverCallCount": texture_calls,
        "sharedDagMemoization": True,
        "sm4SemanticHardening": {
            "exp": "2^x",
            "log": "log2(x)",
            "saturate": "min(max(x,0),1)",
            "round_ne": "fail-closed pending tie-semantics proof",
            "bitwiseAndOr": "fail-closed pending exact adapter/bake",
        },
    }


def compile_scalar_dag(nodes, links, dag_nodes: list[dict], root_node: int, *, symbol_resolver, texture_resolver):
    outputs, stats = compile_dag_roots(
        nodes,
        links,
        dag_nodes,
        {"value": int(root_node)},
        symbol_resolver=symbol_resolver,
        texture_resolver=texture_resolver,
    )
    stats = dict(stats)
    stats["rootNode"] = int(root_node)
    return outputs["value"], stats
