#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json

import t6_blender_height_dag_nodes_v1 as compiler


class Socket:
    def __init__(self, name=""):
        self.name = name
        self.default_value = None
        self.links = []


class SocketCollection:
    def __init__(self, count=4, names=()):
        self._items = [Socket(str(i)) for i in range(count)]
        self._named = {name: Socket(name) for name in names}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._items[key]
        return self._named[key]

    def get(self, key):
        return self._named.get(key)


class Node:
    def __init__(self, node_type):
        self.type = node_type
        self.operation = None
        self.label = ""
        self.inputs = SocketCollection(4)
        self.outputs = SocketCollection(2)


class Nodes:
    def __init__(self):
        self.created = []

    def new(self, node_type):
        node = Node(node_type)
        self.created.append(node)
        return node


class Links:
    def __init__(self):
        self.created = []

    def new(self, source, dest):
        self.created.append((source, dest))
        source.links.append(dest)


def _sha(dag):
    value = {"format": dag["format"], "root": dag["root"], "nodes": dag["nodes"]}
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _recipe():
    # sat((vertex * 2) + alpha + cb) exercises exact leaf joins, argument order,
    # binary math, material constant insertion and two-node saturation.
    dag = {
        "format": "t6-generated-height-weight-dag-v1",
        "root": 7,
        "nodes": [
            {"id": 0, "kind": "input", "name": "COLOR.y"},
            {"id": 1, "kind": "lit", "value": 2.0},
            {"id": 2, "kind": "mul", "args": [0, 1]},
            {"id": 3, "kind": "sample", "resource": "colorMapSampler1", "channel": "w", "sampler": "s1"},
            {"id": 4, "kind": "add", "args": [2, 3]},
            {"id": 5, "kind": "cb", "name": "cb1[59].x"},
            {"id": 6, "kind": "add", "args": [4, 5]},
            {"id": 7, "kind": "sat", "args": [6]},
        ],
        "nodeCount": 8,
        "ordering": "reachable child-before-parent; operation argument order preserved",
    }
    dag["forensicDagSha256"] = _sha(dag)
    return {
        compiler.HEIGHT_DAG_KEY: {
            "layers": [{"layerIndex": 1, "forensicDag": dag}],
        },
        compiler.HEIGHT_CONSTANT_KEY: {
            "leafCount": 1,
            "bindings": [{
                "leaf": "cb1[59].x",
                "materialConstant": {"value": 0.25},
            }],
        },
        compiler.HEIGHT_LEAF_KEY: {
            "allLeavesExact": True,
            "layers": [{
                "layerIndex": 1,
                "forensicDagSha256": dag["forensicDagSha256"],
                "rawVertexInputs": ["COLOR.y"],
                "normalizedVertexWeight": {
                    "attribute": "_T6_LAYER_WEIGHTS",
                    "component": "G",
                    "layerIndex": 1,
                },
                "sampleBindings": [{
                    "resource": "colorMapSampler1",
                    "channel": "w",
                    "portableDependency": {"layerIndex": 1, "role": "colorMap"},
                }],
            }],
        },
    }


def main() -> int:
    recipe = _recipe()
    plan = compiler.prepare_height_dag_plan(recipe, 1)
    assert plan.layer_index == 1
    assert plan.vertex_leaf_names == ("COLOR.y",)
    assert plan.sample_leaves == (("colorMapSampler1", "w"),)
    assert plan.constant_values == {"cb1[59].x": 0.25}
    assert plan.raw_vertex_component == "G"

    nodes = Nodes()
    links = Links()
    vertex = Socket("vertex-G")
    alpha = Socket("layer-alpha")
    result = compiler.compile_height_dag(
        nodes,
        links,
        plan,
        vertex_socket=vertex,
        sample_sockets={("colorMapSampler1", "w"): alpha},
    )
    assert result is nodes.created[-1].outputs[0]
    math_ops = [node.operation for node in nodes.created if node.type == "ShaderNodeMath"]
    assert math_ops == ["MULTIPLY", "ADD", "ADD", "MAXIMUM", "MINIMUM"]
    value_nodes = [node for node in nodes.created if node.type == "ShaderNodeValue"]
    assert len(value_nodes) == 2
    assert [node.outputs[0].default_value for node in value_nodes] == [2.0, 0.25]
    assert len(links.created) == 9

    # Exact sample coverage is mandatory; the compiler cannot substitute the
    # current color texture merely because it is building layer 1.
    try:
        compiler.compile_height_dag(
            Nodes(), Links(), plan, vertex_socket=vertex, sample_sockets={}
        )
    except compiler.BlenderHeightDagError as exc:
        assert "no exact sample socket" in str(exc)
    else:
        raise AssertionError("unbound exact height sample was accepted")

    bad_component = _recipe()
    bad_component[compiler.HEIGHT_LEAF_KEY]["layers"][0]["normalizedVertexWeight"]["component"] = "B"
    try:
        compiler.prepare_height_dag_plan(bad_component, 1)
    except compiler.BlenderHeightDagError as exc:
        assert "normalized component" in str(exc)
    else:
        raise AssertionError("wrong normalized layer-weight component was accepted")

    bad_constant = _recipe()
    bad_constant[compiler.HEIGHT_CONSTANT_KEY]["bindings"] = []
    try:
        compiler.prepare_height_dag_plan(bad_constant, 1)
    except compiler.BlenderHeightDagError as exc:
        assert "DAG constants" in str(exc)
    else:
        raise AssertionError("missing exact material constant was accepted")

    # Select is supported only when its serialized condition is a comparison,
    # ensuring the arithmetic selector receives a proven 0/1 condition.
    bad_select = _recipe()
    dag = bad_select[compiler.HEIGHT_DAG_KEY]["layers"][0]["forensicDag"]
    dag["nodes"].append({"id": 8, "kind": "select", "args": [0, 1, 5]})
    dag["root"] = 8
    dag["nodeCount"] = 9
    dag["forensicDagSha256"] = _sha(dag)
    bad_select[compiler.HEIGHT_LEAF_KEY]["layers"][0]["forensicDagSha256"] = dag["forensicDagSha256"]
    plan2 = compiler.prepare_height_dag_plan(bad_select, 1)
    try:
        compiler.compile_height_dag(
            Nodes(), Links(), plan2, vertex_socket=vertex,
            sample_sockets={("colorMapSampler1", "w"): alpha},
        )
    except compiler.BlenderHeightDagError as exc:
        assert "not proven boolean" in str(exc)
    else:
        raise AssertionError("select with non-boolean condition was accepted")

    print("PASS: exact T6 vN Blender height DAG compiler v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
