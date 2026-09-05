#!/usr/bin/env python3
"""Deterministic tests for canonical generated-world shader recipe attachment."""
from __future__ import annotations

from t6_generated_shader_recipe_contract_v1 import (
    EXTRA_KEY,
    FORMAT,
    GeneratedShaderRecipeError,
    attach_recipes,
    canonical_layer_program,
    validate_manifest,
)


def _recipe(material: str, technique: str, archetype: str = "ps-fixture") -> dict:
    return {
        "material": material,
        "techniqueSet": technique,
        "pixelShaderArchetype": archetype,
        "worldVertFormats": [3, 1, 3],
        "proof": {
            "kind": "retail-fixture",
            "identity": archetype,
        },
    }


def main() -> int:
    technique = "lit_sm_r0c0n0x0_b1c1n1s1_b2c2x2_m3c3"
    program = canonical_layer_program(technique)
    assert program == [
        {
            "layerIndex": 1,
            "operation": "blend",
            "weightClass": "alpha_vertex",
            "hasNormal": True,
            "hasSpecular": True,
            "xVariant": False,
            "heightVariant": False,
        },
        {
            "layerIndex": 2,
            "operation": "blend",
            "weightClass": "vertex_only",
            "hasNormal": False,
            "hasSpecular": False,
            "xVariant": True,
            "heightVariant": False,
        },
        {
            "layerIndex": 3,
            "operation": "multiply",
            "weightClass": "vertex_only",
            "hasNormal": False,
            "hasSpecular": False,
            "xVariant": False,
            "heightVariant": False,
        },
    ]

    manifest = {
        "format": FORMAT,
        "materials": [
            _recipe("*fixture_a", technique, "ps-a"),
            _recipe("*fixture_b", "lit_sm_r0c0n0_t1c1n1s1", "ps-b"),
        ],
    }
    rows = validate_manifest(manifest)
    assert sorted(rows) == ["*fixture_a", "*fixture_b"]
    assert rows["*fixture_a"]["worldVertFormats"] == [1, 3]
    assert rows["*fixture_a"]["layerProgram"] == program

    gltf = {
        "asset": {"version": "2.0"},
        "materials": [
            {"name": "ordinary"},
            {"name": "*fixture_a", "extras": {"T6": {"materialDependencyGraph": {}}}},
            {"name": "*fixture_b", "extras": {"T6": {"embeddedDependencyTextures": []}}},
        ],
        "extras": {"T6": {}},
    }
    stats = attach_recipes(gltf, manifest)
    assert stats["generatedMaterialCount"] == 2
    assert stats["attachedRecipeCount"] == 2
    a = gltf["materials"][1]["extras"]["T6"]
    b = gltf["materials"][2]["extras"]["T6"]
    assert a[EXTRA_KEY]["pixelShaderArchetype"] == "ps-a"
    assert b[EXTRA_KEY]["pixelShaderArchetype"] == "ps-b"
    assert a["materialDependencyGraph"] == {}
    assert b["embeddedDependencyTextures"] == []
    assert gltf["extras"]["T6"]["generatedShaderRecipes"]["attachedRecipeCount"] == 2

    missing_manifest = {
        "format": FORMAT,
        "materials": [_recipe("*fixture_a", technique, "ps-a")],
    }
    gltf_missing = {
        "materials": [{"name": "*fixture_a"}, {"name": "*fixture_b"}],
        "extras": {"T6": {}},
    }
    try:
        attach_recipes(gltf_missing, missing_manifest)
    except GeneratedShaderRecipeError:
        pass
    else:
        raise AssertionError("missing generated recipe did not fail closed")

    unused_manifest = {
        "format": FORMAT,
        "materials": [
            _recipe("*fixture_a", technique, "ps-a"),
            _recipe("*not_in_gltf", technique, "ps-unused"),
        ],
    }
    gltf_unused = {"materials": [{"name": "*fixture_a"}], "extras": {"T6": {}}}
    try:
        attach_recipes(gltf_unused, unused_manifest)
    except GeneratedShaderRecipeError:
        pass
    else:
        raise AssertionError("unused recipe did not fail closed")

    bad_program = _recipe("*fixture_a", technique, "ps-a")
    bad_program["layerProgram"] = []
    try:
        validate_manifest({"format": FORMAT, "materials": [bad_program]})
    except GeneratedShaderRecipeError:
        pass
    else:
        raise AssertionError("mismatched serialized layerProgram did not fail closed")

    print("PASS: canonical T6 generated shader recipe contract v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
