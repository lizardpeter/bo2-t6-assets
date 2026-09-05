#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v7 as recover


def _manifest(mode="transform2x2", shader_index=0):
    material = "*65n_82n(wpc/base:wpc/layer)"
    technique = "lit_sm_r0c0n0_b1c1n1"
    layout = {
        "format": "t6-nuketown-generated-normal-transform-binding-v1",
        "map": "mp_nuketown_2020",
        "material": material,
        "secondaryNormalBindings": [{
            "layerIndex": 1,
            "normalComponentOrdinal": 1,
            "mode": mode,
            "transformSlot": None if mode == "direct" else 0,
            "attribute": None if mode == "direct" else "_T6_NORMAL_TRANSFORM_0",
        }],
    }
    return {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": [{
            "material": material,
            "techniqueSet": technique,
            "pixelShaderArchetype": "sha256:" + "a" * 64,
            "vertexShaderArchetype": "sha256:" + "b" * 64,
            "worldVertFormats": [2],
            "proof": {"fixture": True},
            "layerProgram": [{
                "layerIndex": 1,
                "operation": "blend",
                "weightClass": "alpha_vertex",
                "hasNormal": True,
                "hasSpecular": False,
                "xVariant": False,
                "heightVariant": False,
            }],
            recover.v6.NORMAL_BINDING_KEY: layout,
        }],
        "recovery": {
            "format": "t6-nuketown-generated-shader-recipe-recovery-v6",
            "recipeRowsSha256": "c" * 64,
        },
    }


def _proof(*, mode="matrix2x2", shader_index=0):
    required = mode == "matrix2x2"
    return {
        "format": recover.shader_mapping.FORMAT,
        "profiles": [{
            "techniqueSet": "lit_sm_r0c0n0_b1c1n1",
            "materialOwnerCount": 1,
            "vertexShaderSha256": "b" * 64,
            "pixelShaderSha256": "a" * 64,
            "normalLayers": [{
                "layerIndex": 1,
                "normalPairKind": mode,
                "normalTransformRequired": required,
                "normalTransformIndex": shader_index if required else None,
                "candidateTransformIndices": [shader_index] if required else [],
                "pixelInputDependencies": ["TEXCOORD7.x", "TEXCOORD7.y"] if required else [],
            }],
        }],
        "summary": {
            "techniqueSetCount": 1,
            "allTransformedLayersUniquelyMapped": True,
        },
    }


def main() -> int:
    old_build = recover.shader_mapping.build
    with tempfile.TemporaryDirectory(prefix="t6_recipe_v7_") as td:
        root = Path(td)
        try:
            recover.shader_mapping.build = lambda *args, **kwargs: _proof()
            result = recover._augment_shader_transform_proof(
                _manifest(), oat_root=root
            )
        finally:
            recover.shader_mapping.build = old_build

        row = result["materials"][0]
        payload = row[recover.SHADER_BINDING_KEY]
        assert payload["crossProofAgreement"] is True
        assert payload["vertexShaderArchetype"] == "sha256:" + "b" * 64
        assert payload["pixelShaderArchetype"] == "sha256:" + "a" * 64
        bound = payload["secondaryNormalBindings"][0]
        assert bound["layerIndex"] == 1
        assert bound["mode"] == "transform2x2"
        assert bound["normalTransformIndex"] == 0
        assert bound["attribute"] == "_T6_NORMAL_TRANSFORM_0"
        assert bound["candidateTransformIndices"] == [0]
        assert bound["pixelInputDependencies"] == ["TEXCOORD7.x", "TEXCOORD7.y"]

        rec = result["recovery"]
        assert rec["format"] == recover.FORMAT
        assert rec["baseRecoveryFormat"] == "t6-nuketown-generated-shader-recipe-recovery-v6"
        assert rec["normalTransformCrossCheckedMaterialCount"] == 1
        assert rec["normalTransformCrossCheckedLayerCount"] == 1
        assert rec["shaderDirectSecondaryNormalLayerCount"] == 0
        assert rec["shaderTransformedSecondaryNormalLayerCount"] == 1
        assert rec["normalTransformCrossProofAgreementComplete"] is True

        # Layout says transform0, shader says transform1: do not pick either.
        try:
            recover.shader_mapping.build = lambda *args, **kwargs: _proof(shader_index=1)
            try:
                recover._augment_shader_transform_proof(_manifest(), oat_root=root)
            except recover.NuketownShaderRecipeRecoveryV7Error as exc:
                assert "layout transform 0 != exact shader mapping" in str(exc)
            else:
                raise AssertionError("layout/shader transform disagreement was accepted")
        finally:
            recover.shader_mapping.build = old_build

        # Direct-vs-matrix disagreement is equally fatal.
        direct_manifest = _manifest(mode="direct")
        try:
            recover.shader_mapping.build = lambda *args, **kwargs: _proof(mode="direct")
            direct = recover._augment_shader_transform_proof(direct_manifest, oat_root=root)
        finally:
            recover.shader_mapping.build = old_build
        drow = direct["materials"][0][recover.SHADER_BINDING_KEY]["secondaryNormalBindings"][0]
        assert drow["mode"] == "direct" and drow["normalTransformIndex"] is None

        try:
            recover.shader_mapping.build = lambda *args, **kwargs: _proof(mode="matrix2x2", shader_index=0)
            try:
                recover._augment_shader_transform_proof(_manifest(mode="direct"), oat_root=root)
            except recover.NuketownShaderRecipeRecoveryV7Error as exc:
                assert "layout says direct" in str(exc)
            else:
                raise AssertionError("direct/matrix cross-proof disagreement was accepted")
        finally:
            recover.shader_mapping.build = old_build

    print("PASS: Nuketown generated shader recovery v7 dual-proof normal transforms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
