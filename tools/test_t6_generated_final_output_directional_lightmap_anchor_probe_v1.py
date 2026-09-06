#!/usr/bin/env python3
from __future__ import annotations

import struct

import t6_generated_final_output_directional_lightmap_anchor_probe_v1 as probe
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3


def bits(value: float) -> str:
    return f"{struct.unpack('<I', struct.pack('<f', float(value)))[0]:08x}"


def fixture(two_equations: bool = False) -> dict:
    nodes = []
    def add(kind, **kw):
        i = len(nodes); nodes.append({"id": i, "kind": kind, **kw}); return i
    u = add("symbol", name="v0.z")
    v = add("symbol", name="v0.w")
    one_third = add("literal32", bits="3eaaaaab")
    two_thirds = add("literal32", bits="3f2aaaab")
    two = add("literal32", bits="40000000")
    minus_one = add("literal32", bits="bf800000")
    eps = add("literal32", bits=probe.EPS_BITS)
    v0 = add("op", op="mul", args=[v, one_third])
    v1 = add("op", op="add", args=[v0, one_third])
    v2 = add("op", op="add", args=[v0, two_thirds])

    rows = []
    for dword, vv in ((100, v0), (120, v1), (140, v2)):
        channels = {}
        for ch in "xyzw":
            channels[ch] = add(
                "textureSample",
                resource=probe.RESOURCE,
                channel=ch,
                sampler="lightmapSamplerSecondary_s",
                samplerRegister=1,
                textureRegister=13,
                opcode="sample",
                instructionDword=dword,
                args=[u, vv],
            )
        rows.append(channels)

    denom0 = add("op", op="add", args=[rows[0]["w"], eps])
    denom1 = add("op", op="add", args=[eps, rows[1]["w"]])
    norm0 = {}; norm1 = {}; direction = {}
    for ch in "xyz":
        norm0[ch] = add("op", op="div", args=[rows[0][ch], denom0])
        rcp = add("op", op="rcp", args=[denom1])
        norm1[ch] = add("op", op="mul", args=[rcp, rows[1][ch]])
        scaled = add("op", op="mul", args=[two, rows[2][ch]])
        direction[ch] = add("op", op="add", args=[minus_one, scaled])

    def equation(prefix: str):
        normal = {ch: add("symbol", name=f"{prefix}.N{ch}") for ch in "xyz"}
        terms = {ch: add("op", op="mul", args=[normal[ch], direction[ch]]) for ch in "xyz"}
        sum_xy = add("op", op="add", args=[terms["x"], terms["y"]])
        dot = add("op", op="add", args=[sum_xy, terms["z"]])
        factor = add("op", op="saturate", args=[dot])
        rgb = {}
        for ch in "xyz":
            weighted = add("op", op="mul", args=[factor, norm1[ch]])
            rgb[ch] = add("op", op="add", args=[weighted, norm0[ch]])
        return normal, factor, rgb

    normal1, factor1, rgb1 = equation("A")
    equations = [(normal1, factor1, rgb1)]
    if two_equations:
        normal2, factor2, rgb2 = equation("B")
        equations.append((normal2, factor2, rgb2))
        output_rgb = {ch: add("op", op="add", args=[rgb1[ch], rgb2[ch]]) for ch in "xyz"}
    else:
        output_rgb = rgb1

    return {
        "format": symbolic_v3.FORMAT,
        "materials": [{"material": "*fixture"}],
        "shaders": [{
            "sha256": "a" * 64,
            "techniqueSets": ["lit_sm_fixture"],
            "nodes": nodes,
            "outputs": [{
                "register": 0,
                "lanes": [
                    {"channel": "x", "written": True, "node": output_rgb["x"], "resources": []},
                    {"channel": "y", "written": True, "node": output_rgb["y"], "resources": []},
                    {"channel": "z", "written": True, "node": output_rgb["z"], "resources": []},
                    {"channel": "w", "written": False, "node": None, "resources": []},
                ],
            }],
        }],
    }


def main() -> int:
    one = probe.build(fixture(False))
    assert one["format"] == probe.FORMAT
    assert one["summary"]["shaderCount"] == 1
    assert one["summary"]["rowTripletCount"] == 1
    assert one["summary"]["explicitDirectionalEquationCount"] == 1
    assert one["summary"]["oneExplicitEquationShaderCount"] == 1
    assert one["summary"]["zeroExplicitEquationShaderCount"] == 0
    eq = one["shaders"][0]["equations"][0]
    assert eq["encoding"] == "explicit"
    assert eq["rowSampleDwords"] == [100, 120, 140]
    assert set(eq["normalNodes"]) == set("xyz")
    assert set(eq["rgbNodes"]) == set("xyz")
    assert len(eq["normalSha256"]) == 64 and len(eq["rgbSha256"]) == 64

    two = probe.build(fixture(True))
    assert two["summary"]["explicitDirectionalEquationCount"] == 2
    assert two["summary"]["twoOrMoreExplicitEquationShaderCount"] == 1
    assert two["shaders"][0]["explicitDirectionalEquationCount"] == 2
    assert len({eq["factorNode"] for eq in two["shaders"][0]["equations"]}) == 2
    # The same three retained lightmap samples can feed multiple equations with
    # different bytecode-proven normal counterparts.
    assert {tuple(eq["rowSampleDwords"]) for eq in two["shaders"][0]["equations"]} == {(100, 120, 140)}

    wrong_coord = fixture(False)
    nodes = wrong_coord["shaders"][0]["nodes"]
    # Find the row2 v expression via the known row2 sample and change 2/3 to 1/2.
    half = len(nodes); nodes.append({"id": half, "kind": "literal32", "bits": bits(0.5)})
    row2_sample = next(
        node for node in nodes
        if node.get("kind") == "textureSample" and node.get("instructionDword") == 140
    )
    old_v = row2_sample["args"][1]
    old_node = nodes[old_v]
    old_node["args"] = [old_node["args"][0], half]
    wrong = probe.build(wrong_coord)
    assert wrong["summary"]["rowTripletCount"] == 0
    assert wrong["summary"]["explicitDirectionalEquationCount"] == 0
    assert wrong["summary"]["zeroExplicitEquationShaderCount"] == 1

    missing_explicit = fixture(False)
    nodes = missing_explicit["shaders"][0]["nodes"]
    # Break one row0 normalization without altering the exact three-row samples.
    target = next(
        node for node in nodes
        if node.get("kind") == "op" and node.get("op") == "div"
    )
    target["op"] = "mul"
    missing = probe.build(missing_explicit)
    assert missing["summary"]["rowTripletCount"] == 1
    assert missing["summary"]["explicitDirectionalEquationCount"] == 0
    assert missing["summary"]["zeroExplicitEquationShaderCount"] == 1

    print("PASS: explicit directional-lightmap final-output anchor probe v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
