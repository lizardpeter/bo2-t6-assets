#!/usr/bin/env python3
from __future__ import annotations

import t6_nuketown_generated_shader_recipe_recover_v6 as recover


def _base_manifest():
    rows = [
        {
            "material": "*65n_82n(wpc/base:wpc/layer)",
            "techniqueSet": "lit_sm_r0c0n0_b1c1n1",
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
        },
        {
            "material": "*64_9_127n(wpc/base:wpc/decal:wpc/normal)",
            "techniqueSet": "lit_sm_r0c0_b1c1_b2c2n2",
            "pixelShaderArchetype": "sha256:" + "c" * 64,
            "vertexShaderArchetype": "sha256:" + "d" * 64,
            "worldVertFormats": [3],
            "proof": {"fixture": True},
            "layerProgram": [
                {
                    "layerIndex": 1,
                    "operation": "blend",
                    "weightClass": "alpha_vertex",
                    "hasNormal": False,
                    "hasSpecular": False,
                    "xVariant": False,
                    "heightVariant": False,
                },
                {
                    "layerIndex": 2,
                    "operation": "blend",
                    "weightClass": "alpha_vertex",
                    "hasNormal": True,
                    "hasSpecular": False,
                    "xVariant": False,
                    "heightVariant": False,
                },
            ],
        },
    ]
    return {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": rows,
        "recovery": {
            "format": "t6-nuketown-generated-shader-recipe-recovery-v5",
            "recipeRowsSha256": "e" * 64,
        },
    }


def main() -> int:
    result = recover._augment_normal_transform_bindings(_base_manifest())
    rows = {row["material"]: row for row in result["materials"]}

    transformed = rows["*65n_82n(wpc/base:wpc/layer)"][recover.NORMAL_BINDING_KEY]
    assert transformed["secondaryNormalBindings"] == [{
        "layerIndex": 1,
        "normalComponentOrdinal": 1,
        "mode": "transform2x2",
        "transformSlot": 0,
        "attribute": "_T6_NORMAL_TRANSFORM_0",
    }]

    direct = rows["*64_9_127n(wpc/base:wpc/decal:wpc/normal)"][recover.NORMAL_BINDING_KEY]
    assert direct["secondaryNormalBindings"][0]["layerIndex"] == 2
    assert direct["secondaryNormalBindings"][0]["mode"] == "direct"
    assert direct["secondaryNormalBindings"][0]["attribute"] is None

    rec = result["recovery"]
    assert rec["format"] == recover.FORMAT
    assert rec["baseRecoveryFormat"] == "t6-nuketown-generated-shader-recipe-recovery-v5"
    assert rec["normalTransformBoundMaterialCount"] == 2
    assert rec["secondaryNormalMaterialCount"] == 2
    assert rec["secondaryNormalLayerCount"] == 2
    assert rec["directSecondaryNormalLayerCount"] == 1
    assert rec["transformedSecondaryNormalLayerCount"] == 1
    assert rec["normalTransformSlotHistogram"] == {"0": 1}
    assert rec["normalTransformBindingCoverageComplete"] is True
    assert rec["recipeRowsSha256"] != rec["baseRecipeRowsSha256"]

    # A world-layout contradiction from the retained recipe must abort recovery.
    bad = _base_manifest()
    bad["materials"][0]["worldVertFormats"] = [1]
    try:
        recover._augment_normal_transform_bindings(bad)
    except recover.NuketownShaderRecipeRecoveryV6Error as exc:
        assert "normal transform binding failed" in str(exc)
        assert "world format normalCount" in str(exc)
    else:
        raise AssertionError("normal transform binding contradiction was accepted")

    print("PASS: Nuketown generated shader recovery v6 normal transform bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
