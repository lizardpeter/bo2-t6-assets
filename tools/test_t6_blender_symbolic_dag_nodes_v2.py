#!/usr/bin/env python3
"""Run inside Blender: validate generic exact T6 symbolic DAG lowering v2."""
from __future__ import annotations

import json
import bpy
import t6_blender_symbolic_dag_nodes_v2 as dag


def value_node(nodes, value: float, label: str):
    node = nodes.new("ShaderNodeValue")
    node.outputs[0].default_value = value
    node.label = label
    return node.outputs[0]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material = bpy.data.materials.new("T6_DAG_TEST")
    material.use_nodes = True
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    nodes.clear()

    # A small but representative scalar DAG using a symbolic input, exact
    # textureSample leaf, SM4 base-2 exp/log, saturate, comparison and select.
    graph = [
        {"id": 0, "kind": "literal32", "bits": "3e800000"},  # 0.25
        {"id": 1, "kind": "symbol", "name": "v0.x"},
        {"id": 2, "kind": "textureSample", "resource": "colorMapSampler", "channel": "x", "opcode": "sample", "args": [1]},
        {"id": 3, "kind": "op", "op": "mul", "args": [2, 1]},
        {"id": 4, "kind": "op", "op": "exp", "args": [3]},
        {"id": 5, "kind": "op", "op": "log", "args": [4]},
        {"id": 6, "kind": "op", "op": "saturate", "args": [5]},
        {"id": 7, "kind": "literal32", "bits": "00000000"},
        {"id": 8, "kind": "op", "op": "ge", "args": [6, 7]},
        {"id": 9, "kind": "op", "op": "select", "args": [8, 6, 0]},
    ]

    symbol_calls = []
    sample_calls = []

    def symbol_resolver(name):
        symbol_calls.append(name)
        assert name == "v0.x"
        return value_node(nodes, 0.5, "fixture v0.x")

    def texture_resolver(row, compiled_args):
        sample_calls.append({"resource": row.get("resource"), "channel": row.get("channel"), "argCount": len(compiled_args)})
        assert row.get("resource") == "colorMapSampler"
        assert row.get("channel") == "x"
        assert len(compiled_args) == 1
        return value_node(nodes, 0.75, "fixture colorMapSampler.x")

    root, stats = dag.compile_scalar_dag(
        nodes, links, graph, 9,
        symbol_resolver=symbol_resolver,
        texture_resolver=texture_resolver,
    )

    emission = nodes.new("ShaderNodeEmission")
    emission.label = "T6 DAG compiled scalar inspection"
    links.new(root, emission.inputs["Strength"])
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    labels = {node.label for node in nodes if node.label}
    assert any("= 2^x" in label for label in labels)
    assert any("= log2(x)" in label for label in labels)
    assert any("max(x,0)" in label for label in labels)
    assert any("min(...,1)" in label for label in labels)
    assert stats["format"] == dag.FORMAT
    assert stats["rootNode"] == 9
    assert stats["compiledUniqueNodeCount"] == 10
    assert symbol_calls == ["v0.x"]
    assert sample_calls == [{"resource": "colorMapSampler", "channel": "x", "argCount": 1}]

    def expect_fail(op):
        bad = [
            {"id": 0, "kind": "literal32", "bits": "3f000000"},
            {"id": 1, "kind": "op", "op": op, "args": [0] if op == "round_ne" else [0, 0]},
        ]
        try:
            dag.compile_scalar_dag(
                nodes, links, bad, 1,
                symbol_resolver=symbol_resolver,
                texture_resolver=texture_resolver,
            )
        except dag.BlenderSymbolicDagError:
            return
        raise AssertionError(f"expected fail-closed op {op}")

    expect_fail("round_ne")
    expect_fail("and")
    expect_fail("or")

    report = {
        "format": "t6-blender-symbolic-dag-nodes-test-v2",
        "blenderVersion": bpy.app.version_string,
        "stats": stats,
        "symbolCalls": symbol_calls,
        "textureCalls": sample_calls,
        "validation": {
            "base2Exp": True,
            "base2Log": True,
            "explicitSaturate": True,
            "selectAndComparison": True,
            "roundNearestEvenFailsClosed": True,
            "bitwiseAndOrFailClosed": True,
            "blendSaved": True,
        },
    }
    print("T6_BLENDER_SYMBOLIC_DAG_V2_TEST=" + json.dumps(report, sort_keys=True))
    bpy.ops.wm.save_as_mainfile(filepath="/tmp/T6_BLENDER_SYMBOLIC_DAG_V2_TEST.blend")
    with open("/tmp/T6_BLENDER_SYMBOLIC_DAG_V2_TEST.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
