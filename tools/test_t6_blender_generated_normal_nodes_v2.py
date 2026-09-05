#!/usr/bin/env python3
from __future__ import annotations

import t6_blender_generated_normal_nodes_v2 as nodes_v2


class Socket:
    def __init__(self, name):
        self.name = name
        self.default_value = None


class Sockets:
    def __init__(self, names):
        self.values = {name: Socket(name) for name in names}
    def get(self, name):
        return self.values.get(name)
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values.values())[key]
        return self.values[key]


class Node:
    def __init__(self, kind):
        self.bl_idname = kind
        self.label = ""
        self.operation = None
        self.vector_type = None
        self.convert_from = None
        self.convert_to = None
        if kind == "ShaderNodeSeparateXYZ":
            self.inputs = Sockets(["Vector"]); self.outputs = Sockets(["X", "Y", "Z"])
        elif kind == "ShaderNodeCombineXYZ":
            self.inputs = Sockets(["X", "Y", "Z"]); self.outputs = Sockets(["Vector"])
        elif kind == "ShaderNodeMath":
            self.inputs = Sockets(["0", "1"]); self.outputs = Sockets(["0"])
        elif kind == "ShaderNodeVectorTransform":
            self.inputs = Sockets(["Vector"]); self.outputs = Sockets(["Vector"])
        elif kind == "ShaderNodeAttribute":
            self.inputs = Sockets([]); self.outputs = Sockets(["Vector", "Color"]); self.attribute_name = ""
        elif kind == "ShaderNodeVectorMath":
            self.inputs = Sockets(["0", "1"]); self.outputs = Sockets(["Vector"])
        else:
            raise AssertionError(kind)


class Nodes:
    def __init__(self): self.created = []
    def new(self, kind):
        node = Node(kind); self.created.append(node); return node


class Links:
    def __init__(self): self.created = []
    def new(self, source, dest): self.created.append((source, dest))


def main() -> int:
    nodes = Nodes(); links = Links(); source = Socket("raw")
    result = nodes_v2.gltf_to_blender_object_vector(nodes, links, source, "basis")
    assert result is nodes.created[2].outputs["Vector"]
    assert [n.bl_idname for n in nodes.created] == [
        "ShaderNodeSeparateXYZ", "ShaderNodeMath", "ShaderNodeCombineXYZ"
    ]
    assert nodes.created[1].operation == "MULTIPLY"
    assert nodes.created[1].inputs["1"].default_value == -1.0
    # Links encode x -> X, -z -> Y, y -> Z.
    pairs = [(a.name, b.name) for a, b in links.created]
    assert pairs == [
        ("raw", "Vector"),
        ("Z", "0"),
        ("X", "X"),
        ("0", "Y"),
        ("Y", "Z"),
    ], pairs

    nodes = Nodes(); links = Links()
    world = nodes_v2._basis_world(nodes, links, "_T6_WORLD_NORMAL", "N")
    transform = [n for n in nodes.created if n.bl_idname == "ShaderNodeVectorTransform"]
    assert len(transform) == 1
    assert transform[0].vector_type == "VECTOR"
    assert transform[0].convert_from == "OBJECT"
    assert transform[0].convert_to == "WORLD"
    assert world is transform[0].outputs["Vector"]
    attr = [n for n in nodes.created if n.bl_idname == "ShaderNodeAttribute"][0]
    assert attr.attribute_name == "_T6_WORLD_NORMAL"

    print("PASS: explicit T6 glTF-to-Blender basis axis mapping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
