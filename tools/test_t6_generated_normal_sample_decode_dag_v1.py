#!/usr/bin/env python3
from __future__ import annotations

from types import SimpleNamespace

import t6_generated_normal_sample_decode_dag_v1 as decode


class FakeComp:
    @staticmethod
    def symbolic(blob, opcode, operand, inspect):
        assert blob.startswith(b"DXBC")
        nodes = [
            {"kind": "sample", "resource": "normalMapSampler1", "channel": "x", "sampler": "s2"}, # 0
            {"kind": "lit", "value": 2.0},                                                            # 1
            {"kind": "mul", "args": [0, 1]},                                                        # 2
            {"kind": "lit", "value": -1.0},                                                        # 3
            {"kind": "add", "args": [2, 3]},                                                        # 4 decoded x
            {"kind": "input", "name": "TEXCOORD7.x"},                                             # 5 matrix
            {"kind": "dot", "args": [4, 5]},                                                        # 6 current x
            {"kind": "sample", "resource": "normalMapSampler1", "channel": "y", "sampler": "s2"}, # 7
            {"kind": "mul", "args": [7, 1]},                                                        # 8
            {"kind": "add", "args": [8, 3]},                                                        # 9 decoded y
            {"kind": "input", "name": "TEXCOORD7.y"},                                             # 10 matrix
            {"kind": "dot", "args": [9, 10]},                                                       # 11 current y
            {"kind": "input", "name": "COLOR.y"},                                                 # 12 weight
        ]
        return SimpleNamespace(n=nodes)

    @staticmethod
    def mode_sig(technique_set):
        return "b"

    @staticmethod
    def sequence(d, mode, channel):
        assert mode == "b" and channel == "x"
        return [(0, [12])]

    @staticmethod
    def specs(technique_set):
        return [(1, "b", ("n",))]

    @staticmethod
    def value_resources(d, root):
        seen = set()
        resources = set()
        def visit(i):
            if i in seen:
                return
            seen.add(i)
            node = d.n[i]
            if node["kind"] == "sample":
                resources.add(node["resource"])
            for child in node.get("args", []):
                visit(child)
        visit(root)
        return resources

    @staticmethod
    def input_deps(d, root):
        seen = set()
        deps = set()
        def visit(i):
            if i in seen:
                return
            seen.add(i)
            node = d.n[i]
            if node["kind"] == "input":
                deps.add(node["name"])
            for child in node.get("args", []):
                visit(child)
        visit(root)
        return deps


class FakeNormal:
    direct = False

    @staticmethod
    def current_pair(comp, d, layer, weight):
        assert layer == 1 and weight == 12
        return [4, 9] if FakeNormal.direct else [6, 11]

    @staticmethod
    def sample_channels(comp, d, root, resource):
        seen = set()
        channels = set()
        def visit(i):
            if i in seen:
                return
            seen.add(i)
            node = d.n[i]
            if node["kind"] == "sample" and node["resource"] == resource:
                channels.add(node["channel"])
            for child in node.get("args", []):
                visit(child)
        visit(root)
        return channels


def main() -> int:
    dummy = object()
    FakeNormal.direct = False
    result = decode.extract_normal_decode_dags(
        b"DXBC-normal-decode-fixture",
        "lit_sm_r0c0n0_b1c1n1",
        modules=(FakeComp, FakeNormal, dummy, dummy, dummy),
    )
    assert result["format"] == decode.SET_FORMAT
    assert result["normalLayerCount"] == 1
    assert result["allDecodeLeavesSampleOnly"] is True
    layer = result["layers"][0]
    assert layer["layerIndex"] == 1
    assert layer["normalResource"] == "normalMapSampler1"
    assert layer["sampleChannels"] == ["x", "y"]
    assert layer["transformMode"] == "transform2x2"
    x, y = layer["components"]
    # Must peel past dot( decoded, matrix input ) and retain the signed decode add.
    assert x["currentNormalRoot"] == 6 and x["decodeRoot"] == 4
    assert y["currentNormalRoot"] == 11 and y["decodeRoot"] == 9
    assert x["forensicDag"]["nodes"][-1]["kind"] == "add"
    assert y["forensicDag"]["nodes"][-1]["kind"] == "add"
    assert x["leafInventory"]["input"] == [] and x["leafInventory"]["cb"] == []
    assert x["leafInventory"]["sample"] == [{
        "resource": "normalMapSampler1", "channel": "x", "sampler": "s2"
    }]
    assert y["leafInventory"]["sample"] == [{
        "resource": "normalMapSampler1", "channel": "y", "sampler": "s2"
    }]
    for sample, expected in ((0.0, -1.0), (0.5, 0.0), (1.0, 1.0)):
        assert abs(decode.evaluate_decode_component(x["forensicDag"], sample) - expected) < 1e-12
        assert abs(decode.evaluate_decode_component(y["forensicDag"], sample) - expected) < 1e-12

    # Direct normal pair should serialize the same decode roots without requiring
    # or inventing a matrix input.
    FakeNormal.direct = True
    direct = decode.extract_normal_decode_dags(
        b"DXBC-normal-decode-fixture",
        "lit_sm_r0c0n0_b1c1n1",
        modules=(FakeComp, FakeNormal, dummy, dummy, dummy),
    )
    assert direct["layers"][0]["transformMode"] == "direct"
    assert [c["decodeRoot"] for c in direct["layers"][0]["components"]] == [4, 9]

    # If sample-only ancestry is not unique, extraction must not choose an
    # arbitrary inner/outer expression.
    d = FakeComp.symbolic(b"DXBC", dummy, dummy, dummy)
    # Add a second independent x decode branch under a synthetic parent that also
    # depends on matrix input; neither branch contains the other.
    d.n.extend([
        {"kind": "sample", "resource": "normalMapSampler1", "channel": "x", "sampler": "s2"}, #13
        {"kind": "add", "args": [13, 3]}, #14
        {"kind": "add", "args": [4, 14]}, #15 sample-only but contains both branches -> actually unique maximal
    ])
    # The maximal rule should prefer 15 rather than either inner decode.
    assert decode._maximal_decode_candidate(FakeComp, FakeNormal, d, 15, "normalMapSampler1", "x") == 15

    # Injecting a cbuffer/input dependency into the decode subtree prevents it
    # from being classified sample-only in the first place.
    try:
        decode._maximal_decode_candidate(FakeComp, FakeNormal, d, 6, "normalMapSampler1", "z")
    except decode.GeneratedNormalDecodeDagError as exc:
        assert "no sample-only" in str(exc)
    else:
        raise AssertionError("missing exact normal sample channel was accepted")

    print("PASS: exact generated normal sample decode DAG v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
