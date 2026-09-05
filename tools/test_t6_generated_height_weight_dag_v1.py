#!/usr/bin/env python3
from __future__ import annotations

import copy
from types import SimpleNamespace

import t6_generated_height_weight_dag_v1 as height


class FakeCompositor:
    @staticmethod
    def symbolic(blob, opcode, operand, inspect):
        assert blob.startswith(b"DXBC")
        return SimpleNamespace(n=[
            {"kind": "input", "name": "COLOR.y"},
            {"kind": "lit", "value": 2.0},
            {"kind": "mul", "args": [0, 1]},
            {
                "kind": "sample",
                "resource": "colorMapSampler1",
                "channel": "w",
                "sampler": "s1",
                "instructionDword": 77,
            },
            {"kind": "add", "args": [2, 3]},
            {"kind": "sat", "args": [4]},
        ])

    @staticmethod
    def mode_sig(technique_set):
        assert technique_set == "lit_sm_r0c0_b1c1v1"
        return "b"

    @staticmethod
    def specs(technique_set):
        return [(1, "b", ("v",))]

    @staticmethod
    def sequence(d, mode, channel):
        assert mode == "b" and channel in "xyz"
        return [(0, [5])]

    @staticmethod
    def predict(operation, flags):
        return "height" if operation == "b" and "v" in flags else "alpha_vertex"

    @staticmethod
    def wclass(operation, flags, d, root):
        assert root == 5
        return "height"


def main() -> int:
    dummy = object()
    result = height.extract_height_weight_dags(
        b"DXBC-height-fixture",
        "lit_sm_r0c0_b1c1v1",
        modules=(FakeCompositor, dummy, dummy, dummy),
    )
    assert result["format"] == "t6-generated-height-weight-dag-set-v1"
    assert result["heightLayerCount"] == 1
    row = result["layers"][0]
    assert row["layerIndex"] == 1
    assert row["operation"] == "b"
    assert row["flags"] == ["v"]
    assert row["weightClass"] == "height"
    assert len(row["semanticWeightDagSha256"]) == 64

    dag = row["forensicDag"]
    height.validate_forensic_dag(dag)
    assert dag["nodeCount"] == 6
    assert dag["root"] == 5
    # Forensic serialization keeps shader-position metadata even though the
    # separate semantic hash intentionally omits it for cross-pass comparison.
    sample = next(node for node in dag["nodes"] if node["kind"] == "sample")
    assert sample["instructionDword"] == 77
    assert sample["resource"] == "colorMapSampler1"

    value = height.evaluate_forensic_dag(
        dag,
        inputs={"COLOR.y": 0.2},
        constants={},
        samples={"colorMapSampler1": {"w": 0.3}},
    )
    assert abs(value - 0.7) < 1e-12

    # Saturation is part of the serialized program, not an adapter heuristic.
    value = height.evaluate_forensic_dag(
        dag,
        inputs={"COLOR.y": 0.8},
        constants={},
        samples={"colorMapSampler1": {"w": 0.6}},
    )
    assert value == 1.0

    tampered = copy.deepcopy(dag)
    tampered["nodes"][2]["args"] = [1, 0]
    try:
        height.validate_forensic_dag(tampered)
    except height.GeneratedHeightDagError as exc:
        assert "forensic SHA mismatch" in str(exc)
    else:
        raise AssertionError("forensic operation-order tamper was accepted")

    bad_order = copy.deepcopy(dag)
    bad_order["nodes"][4]["args"] = [5, 3]
    try:
        height.validate_forensic_dag(bad_order)
    except height.GeneratedHeightDagError as exc:
        assert "child-before-parent" in str(exc)
    else:
        raise AssertionError("non-topological DAG was accepted")

    print("PASS: exact T6 generated height-weight DAG contract v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
