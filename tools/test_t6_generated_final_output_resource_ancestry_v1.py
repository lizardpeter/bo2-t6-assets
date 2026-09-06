#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_generated_final_output_resource_ancestry_v1 as ancestry
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3


def fixture() -> dict:
    nodes = [
        {"id": 0, "kind": "textureSample", "resource": "colorMapSampler", "args": []},
        {"id": 1, "kind": "textureSample", "resource": "normalMapSampler1", "args": []},
        {"id": 2, "kind": "textureSample", "resource": "lightmapSamplerSecondary", "args": [1]},
        {"id": 3, "kind": "textureSample", "resource": "reflectionProbeSampler", "args": []},
        {"id": 4, "kind": "op", "op": "mul", "args": [0, 2]},
        {"id": 5, "kind": "op", "op": "add", "args": [4, 3]},
        {"id": 6, "kind": "textureSample", "resource": "mysterySampler", "args": []},
        {"id": 7, "kind": "op", "op": "add", "args": [5, 6]},
    ]
    rgb_resources = [
        "colorMapSampler",
        "lightmapSamplerSecondary",
        "mysterySampler",
        "normalMapSampler1",
        "reflectionProbeSampler",
    ]
    return {
        "format": symbolic_v3.FORMAT,
        "materials": [{"material": "*fixture"}],
        "summary": {"canonicalShaderIdentityMismatchCount": 0},
        "shaders": [{
            "sha256": "a" * 64,
            "techniqueSets": ["lit_sm_fixture"],
            "nodes": nodes,
            "samples": [
                {"resource": "colorMapSampler"},
                {"resource": "normalMapSampler1"},
                {"resource": "lightmapSamplerSecondary"},
                {"resource": "reflectionProbeSampler"},
                {"resource": "mysterySampler"},
            ],
            "outputs": [{
                "register": 0,
                "lanes": [
                    {"channel": "x", "written": True, "node": 7, "resources": rgb_resources},
                    {"channel": "y", "written": True, "node": 7, "resources": rgb_resources},
                    {"channel": "z", "written": True, "node": 7, "resources": rgb_resources},
                    {"channel": "w", "written": True, "node": 0, "resources": ["colorMapSampler"]},
                ],
            }],
        }],
    }


def expect_fail(doc: dict, phrase: str, *, strict=False) -> None:
    try:
        ancestry.build(doc, strict_nuketown=strict)
    except ancestry.GeneratedFinalOutputResourceAncestryError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"expected failure containing {phrase!r}")


def main() -> int:
    doc = fixture()
    result = ancestry.build(doc)
    assert result["format"] == ancestry.FORMAT
    assert result["summary"]["shaderCount"] == 1
    assert result["summary"]["sampleCount"] == 5
    assert result["summary"]["outputAncestryCheckCount"] == 4
    assert result["summary"]["outputAncestryMismatchCount"] == 0
    assert result["summary"]["unknownOutputResources"] == ["mysterySampler"]
    assert result["summary"]["unknownOutputResourceCount"] == 1
    row = result["shaders"][0]
    assert row["rgbResourceUnion"] == [
        "colorMapSampler",
        "lightmapSamplerSecondary",
        "mysterySampler",
        "normalMapSampler1",
        "reflectionProbeSampler",
    ]
    assert row["rgbResourceIntersection"] == row["rgbResourceUnion"]
    classes = {x["resource"]: x for x in row["classifiedOutputResources"]}
    assert classes["colorMapSampler"] == {
        "resource": "colorMapSampler", "class": "generatedColor", "layerIndex": 0, "known": True
    }
    assert classes["normalMapSampler1"]["class"] == "generatedNormal"
    assert classes["normalMapSampler1"]["layerIndex"] == 1
    assert classes["lightmapSamplerSecondary"]["class"] == "lightmapSecondary"
    assert classes["reflectionProbeSampler"]["class"] == "reflectionProbe"
    assert classes["mysterySampler"]["known"] is False
    assert set(row["ancestryClasses"]) == {
        "generatedColor", "generatedNormal", "lightmapSecondary", "reflectionProbe", "unclassified"
    }

    bad = fixture()
    bad["shaders"][0]["outputs"][0]["lanes"][0]["resources"] = ["colorMapSampler"]
    expect_fail(bad, "recomputed resources")

    bad = fixture()
    bad["shaders"][0]["nodes"][7]["args"] = [7]
    expect_fail(bad, "contains a cycle")

    bad = fixture()
    bad["shaders"][0]["outputs"][0]["lanes"][3] = {
        "channel": "w", "written": False, "node": 0, "resources": []
    }
    expect_fail(bad, "unwritten lane carries node/resources")

    bad = fixture()
    expect_fail(bad, "requires v3 strictNuketown proof block", strict=True)

    # Exact lexical classifiers do not generalize names that only look similar.
    assert ancestry._classify("colorMapSampler4")["known"] is False
    assert ancestry._classify("ReflectionProbeSampler")["known"] is False
    assert ancestry._classify("specularMapSampler3") == {
        "resource": "specularMapSampler3", "class": "generatedSpecular", "layerIndex": 3, "known": True
    }

    print("PASS: generated final-output exact resource ancestry v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
