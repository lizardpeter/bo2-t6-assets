#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_world_generated_specular_state_v1 as spec
from t6_generated_shader_recipe_contract_v1 import canonical_layer_program


def recipe(technique: str, material: str = "*fixture") -> dict:
    return {
        "material": material,
        "techniqueSet": technique,
        "pixelShaderArchetype": "sha256:" + "1" * 64,
        "vertexShaderArchetype": "sha256:" + "2" * 64,
        "worldVertFormats": [1],
        "layerProgram": canonical_layer_program(technique),
        "proof": {"kind": "synthetic specular contract regression"},
    }


def dep(layer: int, role: str, source: str) -> dict:
    return {
        "layerIndex": layer,
        "role": role,
        "semantic": role,
        "sourceTexture": source,
        "gltfTextureIndex": layer * 10 + (0 if role == "colorMap" else 1),
        "gfxImageAsset": source.replace(".png", ""),
    }


def document(technique: str, deps: list[dict]) -> dict:
    r = recipe(technique)
    return {
        "materials": [{
            "name": "*fixture",
            "extras": {"T6": {
                "generatedShaderRecipeV1": r,
                "embeddedDependencyTextures": deps,
            }},
        }],
        "extras": {"T6": {}},
    }


def expect_error(doc: dict, text: str) -> None:
    try:
        spec.apply_contract(doc, b"raw", map_name=spec.MAP)
    except spec.GeneratedSpecularStateError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError(f"expected specular state error containing {text!r}")


def main() -> int:
    proof = spec.load_proof()
    assert proof["format"] == spec.PROOF_FORMAT
    assert proof["summary"]["recurrenceFailureCount"] == 0
    assert proof["summary"]["sameRgbWeightDagMismatchCount"] == 0

    # Explicit base s0 + layered s1.
    explicit_doc = document(
        "lit_sm_r0c0n0s0_b1c1n1s1",
        [dep(0, "colorMap", "base.png"), dep(0, "specularMap", "base_spec.png"),
         dep(1, "colorMap", "layer.png"), dep(1, "specularMap", "layer_spec.png")],
    )
    out, raw, stats = spec.apply_contract(explicit_doc, b"exact-bin", map_name=spec.MAP)
    assert raw == b"exact-bin"
    assert stats["layeredSpecularMaterialCount"] == 1
    assert stats["secondarySpecularLayerCount"] == 1
    assert stats["explicitBaseSpecularMaterialCount"] == 1
    state = out["materials"][0]["extras"]["T6"]["generatedShaderRecipeV1"][spec.RECIPE_KEY]
    assert state["baseline"]["mode"] == "explicit_specular"
    assert state["baseline"]["dependency"]["sourceTexture"] == "base_spec.png"
    assert state["steps"][0]["operator"] == "b"
    assert state["steps"][0]["dependency"]["sourceTexture"] == "layer_spec.png"
    assert state["steps"][0]["factorBinding"]["source"].startswith("same exact generated RGB")
    assert out["extras"]["T6"][spec.ROOT_KEY]["stats"]["binByteIdentical"] is True

    # No base s0, but x0 means W begins from exact base color alpha.
    x0_doc = document(
        "lit_sm_r0c0n0x0_b1c1s1",
        [dep(0, "colorMap", "base.png"), dep(1, "colorMap", "layer.png"),
         dep(1, "specularMap", "layer_spec.png")],
    )
    out2, _, stats2 = spec.apply_contract(x0_doc, b"x", map_name=spec.MAP)
    state2 = out2["materials"][0]["extras"]["T6"]["generatedShaderRecipeV1"][spec.RECIPE_KEY]
    assert state2["baseline"] == {
        "mode": "retail_fallback",
        "rgb": [0.2, 0.2, 0.2],
        "alphaMode": "baseColorAlpha",
        "alphaDependency": {
            "layerIndex": 0,
            "role": "colorMap",
            "sourceTexture": "base.png",
            "gltfTextureIndex": 0,
            "gfxImageAsset": "base",
            "semantic": "colorMap",
        },
        "alphaChannel": "a",
    }
    assert stats2["fallbackBaseColorAlphaMaterialCount"] == 1

    # No s0 and no x0 => W is exact constant zero.
    zero_doc = document(
        "lit_sm_r0c0n0_b1c1s1",
        [dep(0, "colorMap", "base.png"), dep(1, "colorMap", "layer.png"),
         dep(1, "specularMap", "layer_spec.png")],
    )
    out3, _, stats3 = spec.apply_contract(zero_doc, b"z", map_name=spec.MAP)
    state3 = out3["materials"][0]["extras"]["T6"]["generatedShaderRecipeV1"][spec.RECIPE_KEY]
    assert state3["baseline"]["rgb"] == [0.2, 0.2, 0.2]
    assert state3["baseline"]["alphaMode"] == "constantZero"
    assert state3["baseline"]["alphaValue"] == 0.0
    assert stats3["fallbackZeroAlphaMaterialCount"] == 1

    # Threshold s1 binds to the same exact threshold condition, not a blend scalar.
    threshold_doc = document(
        "lit_sm_r0c0n0x0_t1c1n1s1",
        [dep(0, "colorMap", "base.png"), dep(1, "colorMap", "layer.png"),
         dep(1, "specularMap", "layer_spec.png")],
    )
    out4, _, _ = spec.apply_contract(threshold_doc, b"t", map_name=spec.MAP)
    step = out4["materials"][0]["extras"]["T6"]["generatedShaderRecipeV1"][spec.RECIPE_KEY]["steps"][0]
    assert step["operator"] == "t"
    assert step["factorBinding"]["kind"] == "exactRgbThresholdCondition"

    missing = document(
        "lit_sm_r0c0n0_b1c1s1",
        [dep(0, "colorMap", "base.png"), dep(1, "colorMap", "layer.png")],
    )
    expect_error(missing, "lacks exact specularMap dependency")

    ambiguous = document(
        "lit_sm_r0c0n0_b1c1s1",
        [dep(0, "colorMap", "base.png"), dep(1, "colorMap", "layer.png"),
         dep(1, "specularMap", "a.png"), dep(1, "specularMap", "b.png")],
    )
    expect_error(ambiguous, "ambiguous exact specularMap dependencies")

    bad_map = document(
        "lit_sm_r0c0n0_b1c1s1",
        [dep(0, "colorMap", "base.png"), dep(1, "colorMap", "layer.png"),
         dep(1, "specularMap", "layer_spec.png")],
    )
    try:
        spec.apply_contract(bad_map, b"x", map_name="mp_raid")
    except spec.GeneratedSpecularStateError as exc:
        assert "source-gated" in str(exc)
    else:
        raise AssertionError("unretained map accepted by Nuketown specular contract")

    already = copy.deepcopy(explicit_doc)
    already.setdefault("extras", {}).setdefault("T6", {})[spec.ROOT_KEY] = {"format": spec.FORMAT}
    expect_error(already, "already attached")

    print("PASS: exact Nuketown generated layered specular state v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
