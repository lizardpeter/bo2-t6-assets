#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_generated_final_output_directional_lightmap_anchor_v2 as anchor
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3


def final_output() -> dict:
    return {
        "format": symbolic_v3.FORMAT,
        "materials": [{"material": "*a"}, {"material": "*b"}],
        "shaders": [{"sha256": "a" * 64}, {"sha256": "b" * 64}],
    }


def equation(i: int) -> dict:
    return {
        "encoding": "explicit",
        "factorNode": 10 + i,
        "normalNodes": {"x": 20 + i, "y": 30 + i, "z": 40 + i},
        "normalSha256": f"{100 + i:064x}",
        "rgbNodes": {"x": 50 + i, "y": 60 + i, "z": 70 + i},
        "rgbSha256": f"{200 + i:064x}",
        "row0NormalizedNodes": {"x": 1, "y": 2, "z": 3},
        "row1NormalizedNodes": {"x": 4, "y": 5, "z": 6},
        "directionNodes": {"x": 7, "y": 8, "z": 9},
        "rowSampleDwords": [100, 120, 140],
    }


def probe_result(counts) -> dict:
    shaders = []
    for index, count in enumerate(counts):
        shaders.append({
            "sha256": ("a" if index == 0 else "b") * 64,
            "techniqueSets": [f"lit_sm_{index}"],
            "rowTripletCount": 1,
            "explicitDirectionalEquationCount": count,
            "equations": [equation(i + index * 10) for i in range(count)],
        })
    return {
        "format": anchor.probe.FORMAT,
        "shaders": shaders,
        "summary": {},
    }


def run(counts, strict=True):
    old = anchor.probe.build
    try:
        anchor.probe.build = lambda doc: copy.deepcopy(probe_result(counts))
        return anchor.build(final_output(), strict=strict)
    finally:
        anchor.probe.build = old


def expect_fail(counts, phrase):
    try:
        run(counts, strict=True)
    except anchor.DirectionalLightmapAnchorV2Error as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"expected failure containing {phrase!r}")


def main() -> int:
    result = run([1, 2], strict=True)
    assert result["format"] == anchor.FORMAT
    assert result["sourceFormat"] == symbolic_v3.FORMAT
    assert result["sourceProbeFormat"] == anchor.probe.FORMAT
    assert result["summary"]["shaderCount"] == 2
    assert result["summary"]["directionalEquationCount"] == 3
    assert result["summary"]["oneEquationShaderCount"] == 1
    assert result["summary"]["twoEquationShaderCount"] == 1
    assert result["summary"]["zeroEquationShaderCount"] == 0
    assert result["summary"]["threeOrMoreEquationShaderCount"] == 0
    assert result["summary"]["anchoredShaderCount"] == 2
    assert result["summary"]["uniqueNormalCounterpartHashCount"] == 3
    assert result["retainedCorpusInvariant"]["uniqueSlot4ShaderCount"] == 173
    assert result["retainedCorpusInvariant"]["directionalEquationCount"] == 331
    assert result["retainedCorpusInvariant"]["compilerEquationEncodingCounts"] == {"explicit": 316, "folded": 15}
    for shader in result["shaders"]:
        assert shader["anchored"] is True
        for eq in shader["equations"]:
            assert "encoding" not in eq
            assert eq["expressionEncoding"] == "symbolic-sm4-expression-dag"
            assert eq["compilerMaterialization"] == "not inferred from expression DAG"
    assert "MAD" in result["symbolicNormalizationPolicy"]
    assert "No commutative" in result["symbolicNormalizationPolicy"]

    relaxed = run([0, 3], strict=False)
    assert relaxed["summary"]["zeroEquationShaderCount"] == 1
    assert relaxed["summary"]["threeOrMoreEquationShaderCount"] == 1
    assert relaxed["summary"]["anchoredShaderCount"] == 0

    expect_fail([0, 1], "outside retained 1..2 invariant")
    expect_fail([3, 1], "outside retained 1..2 invariant")

    bad = final_output(); bad["format"] = "wrong"
    old = anchor.probe.build
    try:
        anchor.probe.build = lambda doc: probe_result([1, 1])
        try:
            anchor.build(bad)
        except anchor.DirectionalLightmapAnchorV2Error as exc:
            assert "unsupported final-output format" in str(exc)
        else:
            raise AssertionError("wrong source format was accepted")
    finally:
        anchor.probe.build = old

    print("PASS: semantic directional-lightmap final-output anchor v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
