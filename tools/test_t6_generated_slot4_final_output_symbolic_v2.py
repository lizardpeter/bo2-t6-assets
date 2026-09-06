#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import t6_generated_slot4_final_output_symbolic_v1 as v1
import t6_generated_slot4_final_output_symbolic_v2 as v2


def _base_result() -> dict:
    return {
        "nodes": [
            {"id": 0, "kind": "literal32", "bits": "3f800000"},
            {"id": 1, "kind": "op", "op": "mul", "args": [0, 0]},
        ],
        "outputs": [{
            "register": 0,
            "lanes": [
                {"channel": "x", "written": True, "node": 1, "resources": []},
                {"channel": "y", "written": True, "node": 1, "resources": []},
                {"channel": "z", "written": True, "node": 1, "resources": []},
                {"channel": "w", "written": False, "node": None, "resources": []},
            ],
        }],
        "samples": [],
        "branches": [],
        "elseCount": 0,
        "maxBranchDepth": 0,
        "discards": [],
        "textureBindings": [],
        "samplerBindings": [],
        "dagSha256": "a" * 64,
        "rdefResourceTableSha256": "b" * 64,
        "shaderModel": "4.0",
    }


def test_undefined_reachability() -> None:
    clean = _base_result()
    assert v2._undefined_reachable(clean) == []

    dead = _base_result()
    dead["nodes"].append({"id": 2, "kind": "undefined", "name": "dead"})
    assert v2._undefined_reachable(dead) == []

    bad = _base_result()
    bad["nodes"].append({"id": 2, "kind": "undefined", "name": "branch-missing"})
    bad["nodes"].append({"id": 3, "kind": "op", "op": "select", "args": [0, 1, 2]})
    bad["outputs"][0]["lanes"][0]["node"] = 3
    failures = v2._undefined_reachable(bad)
    assert len(failures) == 1
    assert failures[0]["output"] == "o0.x"
    assert failures[0]["undefinedNodes"] == [2]


def test_sample_derivative_width() -> None:
    old_source = v1.straight.source_nodes
    old_idx = v1.straight.idx
    old_components = v1.straight.source_components
    counter = {"value": 0}

    def source_nodes(source, lanes, state, dag, blockers, at):
        out = []
        for lane in lanes:
            out.append(dag.add("symbol", name=f"{source['name']}.{lane}.{counter['value']}"))
            counter["value"] += 1
        return out

    def idx(source):
        return source.get("register")

    def components(source, lanes):
        return [source.get("channel", 0) for _ in lanes]

    v1.straight.source_nodes = source_nodes
    v1.straight.idx = idx
    v1.straight.source_components = components
    try:
        dag = v1.Dag()
        O = [
            {"name": "dest"},
            {"name": "coord"},
            {"name": "resource", "register": 3, "channel": 1},
            {"name": "sampler", "register": 2},
            {"name": "ddx"},
            {"name": "ddy"},
        ]
        values, row = v2._named_sample_nodes_v2(
            O, [0, 1, 2], {}, dag, [], 17, "sample_d",
            {3: "colorMapSampler1"}, {2: "colorMapSampler1_s"},
        )
        assert len(values) == 3
        assert row["derivativeOperandsFullWidth"] is True
        assert row["extraOperandWidths"] == [4, 4]
        assert len(row["extraOperandNodes"]) == 8
        assert all(dag.nodes[node]["resource"] == "colorMapSampler1" for node in values)
        assert all(dag.nodes[node]["channel"] == "y" for node in values)

        dag2 = v1.Dag()
        _, scalar = v2._named_sample_nodes_v2(
            O[:5], [0], {}, dag2, [], 21, "sample_l",
            {3: "colorMapSampler1"}, {2: "colorMapSampler1_s"},
        )
        assert scalar["derivativeOperandsFullWidth"] is False
        assert scalar["extraOperandWidths"] == [1]
    finally:
        v1.straight.source_nodes = old_source
        v1.straight.idx = old_idx
        v1.straight.source_components = old_components


def test_symbolic_rejects_reachable_undefined() -> None:
    old_base = v2._BASE_SYMBOLIC
    try:
        v2._BASE_SYMBOLIC = lambda blob: _base_result()
        clean = v2.symbolic(b"fixture")
        assert clean["undefinedOutputReachabilityFailureCount"] == 0
        assert "sample_d" in clean["sampleDerivativeOperandPolicy"]

        bad = _base_result()
        bad["nodes"].append({"id": 2, "kind": "undefined", "name": "branch-missing"})
        bad["outputs"][0]["lanes"][0]["node"] = 2
        v2._BASE_SYMBOLIC = lambda blob: bad
        try:
            v2.symbolic(b"fixture")
        except v2.GeneratedFinalOutputSymbolicV2Error as exc:
            assert "undefined state reaches written output" in str(exc)
        else:
            raise AssertionError("reachable undefined output did not fail closed")
    finally:
        v2._BASE_SYMBOLIC = old_base


def test_build_promotion() -> None:
    old_build = v1.build
    old_base = v2._BASE_SYMBOLIC
    seen = {"symbolic": 0}

    def fake_base(blob):
        seen["symbolic"] += 1
        return _base_result()

    def fake_build(recipe_manifest, *, oat_root, strict_nuketown=False):
        row = v1.symbolic(b"fixture")
        return {
            "format": v1.FORMAT,
            "summary": {"uniquePixelShaderCount": 1},
            "shaders": [row],
            "materials": [],
        }

    try:
        v1.build = fake_build
        v2._BASE_SYMBOLIC = fake_base
        result = v2.build({}, oat_root=Path("."), strict_nuketown=False)
    finally:
        v1.build = old_build
        v2._BASE_SYMBOLIC = old_base
    assert seen["symbolic"] == 1
    assert result["format"] == v2.FORMAT
    assert result["baseFormat"] == v1.FORMAT
    assert result["summary"]["undefinedOutputReachabilityFailureCount"] == 0
    assert result["summary"]["fullDerivativeSampleOperandRetention"] is True


def main() -> int:
    test_undefined_reachability()
    test_sample_derivative_width()
    test_symbolic_rejects_reachable_undefined()
    test_build_promotion()
    print("PASS: generated slot-4 final-output symbolic v2 hardening")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
