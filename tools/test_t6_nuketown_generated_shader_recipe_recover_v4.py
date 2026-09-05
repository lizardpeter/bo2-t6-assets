#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v4 as recover


def _base() -> dict:
    material = "*fixture(base:layer)"
    return {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": [{
            "material": material,
            "techniqueSet": "lit_sm_r0c0_b1c1v1",
            "pixelShaderArchetype": "sha256:" + "a" * 64,
            "worldVertFormats": [1],
            "proof": {"fixture": True},
            recover.v3.v2.HEIGHT_KEY: {
                "techniqueSet": "lit_sm_r0c0_b1c1v1",
                "pixelShaderSha256": "a" * 64,
                "layers": [{"layerIndex": 1}],
            },
            recover.v3.HEIGHT_CONSTANT_KEY: {
                "leafCount": 2,
                "bindings": [
                    {"leaf": "cb1[59].x"},
                    {"leaf": "cb1[59].y"},
                ],
                "materialArchiveSha256": "b" * 64,
            },
        }],
        "recovery": {
            "format": "t6-nuketown-generated-shader-recipe-recovery-v3",
            "recipeRowsSha256": "c" * 64,
        },
    }


def _leaf_doc():
    return {
        "format": "t6-generated-height-leaf-bindings-v1",
        "techniqueSet": "lit_sm_r0c0_b1c1v1",
        "pixelShaderSha256": "a" * 64,
        "heightLayerCount": 1,
        "layers": [{
            "layerIndex": 1,
            "rawVertexInputs": ["TEXCOORD6.y"],
            "normalizedVertexWeight": {
                "attribute": "_T6_LAYER_WEIGHTS",
                "component": "G",
                "layerIndex": 1,
            },
            "sampleBindings": [{
                "resource": "colorMapSampler1",
                "materialArgument": "colorMap1",
            }],
            "constantLeaves": ["cb1[59].x", "cb1[59].y"],
        }],
        "allNonconstantLeavesExact": True,
        "bindingSetSha256": "d" * 64,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_recipe_v4_") as td:
        root = Path(td)
        oat = root / "oat"
        (oat / "techniques").mkdir(parents=True)
        (oat / "techniques" / "fixture.tech").write_text("fixture\n", encoding="utf-8")

        old_resolve = recover.resolve_slot_shader
        old_build = recover.build_height_leaf_bindings
        try:
            recover.resolve_slot_shader = lambda oat_root, techset, slot_index: {
                "techniqueSet": techset,
                "techniqueAsset": "fixture",
                "techniqueFile": "techniques/fixture.tech",
                "pixelShaders": [{"sha256": "a" * 64}],
            }
            recover.build_height_leaf_bindings = lambda height, technique_text: _leaf_doc()
            result = recover._augment_leaf_bindings(_base(), oat_root=oat)
        finally:
            recover.resolve_slot_shader = old_resolve
            recover.build_height_leaf_bindings = old_build

        row = result["materials"][0]
        leaf = row[recover.HEIGHT_LEAF_KEY]
        assert leaf["allLeavesExact"] is True
        assert leaf["constantBindingsKey"] == recover.v3.HEIGHT_CONSTANT_KEY
        assert leaf["materialArchiveSha256"] == "b" * 64
        assert leaf["layers"][0]["normalizedVertexWeight"]["component"] == "G"
        rec = result["recovery"]
        assert rec["format"] == recover.FORMAT
        assert rec["heightLeafBoundMaterialCount"] == 1
        assert rec["heightLeafBoundLayerCount"] == 1
        assert rec["uniqueHeightRawVertexInputs"] == ["TEXCOORD6.y"]
        assert rec["uniqueHeightSampleResources"] == ["colorMapSampler1"]
        assert rec["uniqueHeightSampleMaterialArguments"] == ["colorMap1"]
        assert rec["heightAllLeafCoverageComplete"] is True

        bad = _base()
        bad["materials"][0][recover.v3.HEIGHT_CONSTANT_KEY]["bindings"] = [
            {"leaf": "cb1[59].x"}
        ]
        bad["materials"][0][recover.v3.HEIGHT_CONSTANT_KEY]["leafCount"] = 1
        old_resolve = recover.resolve_slot_shader
        old_build = recover.build_height_leaf_bindings
        try:
            recover.resolve_slot_shader = lambda oat_root, techset, slot_index: {
                "techniqueSet": techset,
                "techniqueAsset": "fixture",
                "techniqueFile": "techniques/fixture.tech",
                "pixelShaders": [{"sha256": "a" * 64}],
            }
            recover.build_height_leaf_bindings = lambda height, technique_text: _leaf_doc()
            try:
                recover._augment_leaf_bindings(bad, oat_root=oat)
            except recover.NuketownShaderRecipeRecoveryV4Error as exc:
                assert "DAG constant leaves" in str(exc)
            else:
                raise AssertionError("incomplete per-Material constant leaf set was accepted")
        finally:
            recover.resolve_slot_shader = old_resolve
            recover.build_height_leaf_bindings = old_build

    print("PASS: Nuketown shader recovery v4 complete exact vN leaf coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
