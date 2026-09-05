#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json

import t6_blender_normal_decode_dag_nodes_v1 as compiler
from test_t6_blender_height_dag_nodes_v1 import Links, Nodes, Socket


def _sha(dag):
    value = {"format": dag["format"], "root": dag["root"], "nodes": dag["nodes"]}
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def component(channel: str):
    dag = {
        "format": "t6-generated-height-weight-dag-v1",
        "root": 4,
        "nodes": [
            {"id": 0, "kind": "sample", "resource": "normalMapSampler1", "channel": channel, "sampler": "s"},
            {"id": 1, "kind": "lit", "value": 2.0},
            {"id": 2, "kind": "mul", "args": [0, 1]},
            {"id": 3, "kind": "lit", "value": -1.0},
            {"id": 4, "kind": "add", "args": [2, 3]},
        ],
        "nodeCount": 5,
        "ordering": "reachable child-before-parent; operation argument order preserved",
    }
    dag["forensicDagSha256"] = _sha(dag)
    return {"component": channel, "forensicDag": dag, "forensicDagSha256": dag["forensicDagSha256"]}


def main() -> int:
    payload = {
        "normalResource": "normalMapSampler1",
        "components": [component("x"), component("y")],
    }
    px, py = compiler.prepare_pair(payload, layer_index=1, expected_resource="normalMapSampler1")
    assert px.component == "x" and py.component == "y"
    sample = Socket("normal-R")
    nodes = Nodes(); links = Links()
    result = compiler.compile_component(nodes, links, px, sample_socket=sample)
    assert result is nodes.created[-1].outputs[0]
    math_ops = [n.operation for n in nodes.created if n.type == "ShaderNodeMath"]
    assert math_ops == ["MULTIPLY", "ADD"]
    values = [n.outputs[0].default_value for n in nodes.created if n.type == "ShaderNodeValue"]
    assert values == [2.0, -1.0]

    bad = component("x")
    bad["forensicDag"]["nodes"].insert(0, {"id": 0, "kind": "input", "name": "COLOR.y"})
    # Reindex deliberately omitted: validation itself must reject the corrupted graph.
    try:
        compiler.prepare_component(bad, layer_index=1, resource="normalMapSampler1", component="x")
    except compiler.BlenderNormalDecodeDagError:
        pass
    else:
        raise AssertionError("normal decode DAG with vertex input was accepted")

    wrong = component("x")
    try:
        compiler.prepare_component(wrong, layer_index=1, resource="normalMapSampler2", component="x")
    except compiler.BlenderNormalDecodeDagError as exc:
        assert "sample leaves" in str(exc)
    else:
        raise AssertionError("wrong normal resource was accepted")

    mismatch = component("x")
    mismatch["forensicDagSha256"] = "0" * 64
    try:
        compiler.prepare_component(mismatch, layer_index=1, resource="normalMapSampler1", component="x")
    except compiler.BlenderNormalDecodeDagError as exc:
        assert "forensic SHA" in str(exc)
    else:
        raise AssertionError("mismatched component forensic SHA was accepted")

    print("PASS: exact Blender normal decode DAG compiler v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
