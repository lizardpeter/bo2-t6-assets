#!/usr/bin/env python3
from __future__ import annotations

from types import SimpleNamespace

import t6_generated_normal_sample_decode_probe_v1 as probe


class FakeDag:
    def __init__(self, nodes):
        self.n = nodes


class FakeComp:
    @staticmethod
    def value_resources(dag, node_id):
        node = dag.n[node_id]
        if node.get("kind") == "sample":
            return {node["resource"]}
        out = set()
        for child in node.get("args", []):
            out |= FakeComp.value_resources(dag, child)
        return out

    @staticmethod
    def canon_hash(dag, node_id):
        node = dag.n[node_id]
        if not node.get("args"):
            return repr((node.get("kind"), node.get("resource"), node.get("channel"), node.get("value"), node.get("name")))
        return repr((node.get("kind"), tuple(FakeComp.canon_hash(dag, c) for c in node.get("args", []))))

    @staticmethod
    def collect(root, parser, helper):
        return None, {
            "shader": {
                "techniqueSet": "lit_sm_r0c0n0_b1c1n1",
                "blob": b"fixture",
                "format": 0,
            }
        }

    @staticmethod
    def specs(technique):
        return [(1, "b", "n1")]

    @staticmethod
    def symbolic(blob, opcode, operand, inspect):
        return make_dag()

    @staticmethod
    def mode_sig(technique):
        return "fixture"

    @staticmethod
    def sequence(dag, mode, channel):
        # current_pair regression ignores the actual weight ids, but preserve the
        # same outer shape the retained compositor exposes.
        return [(None, [99])]


def make_dag(*, y_scale=2.0):
    # 0/5 exact texture sample atoms.
    nodes = [
        {"kind": "sample", "resource": "normalMapSampler1", "channel": "x", "args": []},  # 0
        {"kind": "lit", "value": "2.0", "args": []},                                       # 1
        {"kind": "mul", "args": [0, 1]},                                                     # 2
        {"kind": "lit", "value": "-1.0", "args": []},                                      # 3
        {"kind": "add", "args": [2, 3]},                                                     # 4 decoded X
        {"kind": "sample", "resource": "normalMapSampler1", "channel": "y", "args": []},  # 5
        {"kind": "lit", "value": str(y_scale), "args": []},                                 # 6
        {"kind": "mul", "args": [5, 6]},                                                     # 7
        {"kind": "add", "args": [7, 3]},                                                     # 8 decoded Y
        {"kind": "input", "name": "TEXCOORD6.x", "args": []},                              # 9 transform-only
        {"kind": "input", "name": "TEXCOORD6.y", "args": []},                              # 10
        {"kind": "dot", "args": [4, 9, 8, 10]},                                              # 11 transformed X
        {"kind": "dot", "args": [4, 10, 8, 9]},                                              # 12 transformed Y
    ]
    return FakeDag(nodes)


def fake_sample_channels(comp_module, dag, root, resource):
    out = set()
    seen = set()
    def walk(node_id):
        if node_id in seen:
            return
        seen.add(node_id)
        node = dag.n[node_id]
        if node.get("kind") == "sample" and node.get("resource") == resource:
            out.add(node.get("channel"))
        for child in node.get("args", []):
            walk(child)
    walk(root)
    return out


def main() -> int:
    old_comp = probe.comp
    old_current = probe.normal.current_pair
    old_channels = probe.normal.sample_channels
    try:
        probe.comp = FakeComp
        probe.normal.current_pair = lambda comp, dag, layer, weight: [11, 12]
        probe.normal.sample_channels = fake_sample_channels

        dag = make_dag()
        boundary = probe._decode_boundary(FakeComp, dag, [11, 12], "normalMapSampler1")
        assert boundary == {"x": 4, "y": 8}, boundary
        x = probe._classify_scalar(dag, 4, "normalMapSampler1", "x")
        y = probe._classify_scalar(dag, 8, "normalMapSampler1", "y")
        assert x["scale"] == 2.0 and x["offset"] == -1.0
        assert y["scale"] == 2.0 and y["offset"] == -1.0
        assert x["scaleFloat32Bits"] == "40000000"
        assert x["offsetFloat32Bits"] == "bf800000"

        doc = probe.build(SimpleNamespace())
        assert doc["summary"]["shaderCount"] == 1
        assert doc["summary"]["normalLayerCount"] == 1
        assert doc["summary"]["channelDecodeObservationCount"] == 2
        assert doc["summary"]["uniqueAffineDecodeCount"] == 1
        assert doc["summary"]["uniformAffineDecode"] is True
        assert doc["uniformDecode"]["scale"] == 2.0
        assert doc["uniformDecode"]["offset"] == -1.0
        assert doc["uniformDecode"]["scaleFloat32Bits"] == "40000000"
        assert doc["uniformDecode"]["offsetFloat32Bits"] == "bf800000"

        # An inconsistent Y decode must be reported, not averaged or silently
        # coerced to the X channel's result.
        FakeComp.symbolic = staticmethod(lambda blob, opcode, operand, inspect: make_dag(y_scale=1.0))
        mixed = probe.build(SimpleNamespace())
        assert mixed["summary"]["uniqueAffineDecodeCount"] == 2
        assert mixed["summary"]["uniformAffineDecode"] is False
        assert mixed["uniformDecode"] is None

        # Nonlinear sample*sample is not an affine decode.
        nonlinear = FakeDag([
            {"kind": "sample", "resource": "normalMapSampler1", "channel": "x", "args": []},
            {"kind": "mul", "args": [0, 0]},
        ])
        assert probe._affine(nonlinear, 1, 0) is None
    finally:
        probe.comp = old_comp
        probe.normal.current_pair = old_current
        probe.normal.sample_channels = old_channels

    print("PASS: t6_generated_normal_sample_decode_probe_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
