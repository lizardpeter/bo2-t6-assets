#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_generated_final_output_rgb_square_anchor_v1 as anchor
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3


def fixture() -> dict:
    n = []
    def add(kind, **kw):
        i = len(n); n.append({"id": i, "kind": kind, **kw}); return i
    alpha = add("textureSample", resource="colorMapSampler1", channel="w", args=[])
    roots = []
    squares = []
    for ch in "xyz":
        base = add("textureSample", resource="colorMapSampler", channel=ch, args=[])
        layer = add("textureSample", resource="colorMapSampler1", channel=ch, args=[])
        weighted = add("op", op="mul", args=[layer, alpha])
        encoded = add("op", op="add", args=[base, weighted])
        square = add("op", op="mul", args=[encoded, encoded])
        lm = add("textureSample", resource="lightmapSamplerSecondary", channel=ch, args=[])
        root = add("op", op="mul", args=[square, lm])
        squares.append(square)
        roots.append(root)
    return {
        "format": symbolic_v3.FORMAT,
        "materials": [{"material": "*fixture"}],
        "shaders": [{
            "sha256": "a" * 64,
            "techniqueSets": ["lit_sm_fixture"],
            "nodes": n,
            "outputs": [{
                "register": 0,
                "lanes": [
                    {"channel": "x", "written": True, "node": roots[0], "resources": []},
                    {"channel": "y", "written": True, "node": roots[1], "resources": []},
                    {"channel": "z", "written": True, "node": roots[2], "resources": []},
                    {"channel": "w", "written": False, "node": None, "resources": []},
                ],
            }],
        }],
    }


def main() -> int:
    doc = fixture()
    result = anchor.build(doc, strict=True)
    assert result["format"] == anchor.FORMAT
    assert result["summary"]["shaderCount"] == 1
    assert result["summary"]["rgbLaneCount"] == 3
    assert result["summary"]["candidateCount"] == 3
    assert result["summary"]["anchoredRgbLaneCount"] == 3
    assert result["summary"]["missingRgbLaneCount"] == 0
    assert result["summary"]["ambiguousRgbLaneCount"] == 0
    assert result["summary"]["fullyAnchoredShaderCount"] == 1
    row = result["shaders"][0]
    for expected_channel, lane in zip("xyz", row["anchors"]):
        assert lane["anchored"] is True
        assert lane["candidateCount"] == 1
        candidate = lane["candidates"][0]
        assert candidate["channel"] == expected_channel
        assert candidate["resources"] == ["colorMapSampler", "colorMapSampler1"]
        assert candidate["sampleChannels"] == ["w", expected_channel]
        assert len(candidate["encodedRgbSha256"]) == 64
        assert len(candidate["squareSha256"]) == 64

    # A square that already contains lightmap data is not a generated RGB-square candidate.
    bad_resource = fixture()
    nodes = bad_resource["shaders"][0]["nodes"]
    lm = len(nodes); nodes.append({"id": lm, "kind": "textureSample", "resource": "lightmapSamplerSecondary", "channel": "x", "args": []})
    mix = len(nodes); nodes.append({"id": mix, "kind": "op", "op": "add", "args": [1, lm]})
    sq = len(nodes); nodes.append({"id": sq, "kind": "op", "op": "mul", "args": [mix, mix]})
    root = bad_resource["shaders"][0]["outputs"][0]["lanes"][0]["node"]
    new_root = len(nodes); nodes.append({"id": new_root, "kind": "op", "op": "add", "args": [root, sq]})
    bad_resource["shaders"][0]["outputs"][0]["lanes"][0]["node"] = new_root
    still = anchor.build(bad_resource, strict=True)
    assert still["shaders"][0]["anchors"][0]["candidateCount"] == 1

    # A second reachable color-only mul(X,X) in the same lane is ambiguous and must fail closed.
    ambiguous = fixture()
    nodes = ambiguous["shaders"][0]["nodes"]
    base_x = 1
    second = len(nodes); nodes.append({"id": second, "kind": "op", "op": "mul", "args": [base_x, base_x]})
    old_root = ambiguous["shaders"][0]["outputs"][0]["lanes"][0]["node"]
    combined = len(nodes); nodes.append({"id": combined, "kind": "op", "op": "add", "args": [old_root, second]})
    ambiguous["shaders"][0]["outputs"][0]["lanes"][0]["node"] = combined
    relaxed = anchor.build(ambiguous, strict=False)
    assert relaxed["shaders"][0]["anchors"][0]["candidateCount"] == 2
    assert relaxed["summary"]["ambiguousRgbLaneCount"] == 1
    try:
        anchor.build(ambiguous, strict=True)
    except anchor.GeneratedFinalOutputRgbSquareAnchorError as exc:
        assert "not unique" in str(exc)
    else:
        raise AssertionError("ambiguous RGB-square anchor did not fail closed")

    # Wrong sampled RGB lane cannot anchor o0.x even if the square is color-only.
    wrong = fixture()
    wrong["shaders"][0]["nodes"][1]["channel"] = "y"
    relaxed = anchor.build(wrong, strict=False)
    assert relaxed["shaders"][0]["anchors"][0]["candidateCount"] == 0
    try:
        anchor.build(wrong, strict=True)
    except anchor.GeneratedFinalOutputRgbSquareAnchorError as exc:
        assert "not unique" in str(exc)
    else:
        raise AssertionError("wrong-channel RGB-square anchor did not fail closed")

    print("PASS: generated final-output RGB-square anchor v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
