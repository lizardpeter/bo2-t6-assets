#!/usr/bin/env python3
from __future__ import annotations

import t6_nuketown_generated_normal_transform_binding_v1 as binding


def _recipe(material: str, technique: str, world_format: int, steps: list[dict]) -> dict:
    return {
        "material": material,
        "techniqueSet": technique,
        "pixelShaderArchetype": "sha256:" + "a" * 64,
        "vertexShaderArchetype": "sha256:" + "b" * 64,
        "worldVertFormats": [world_format],
        "proof": {"fixture": True},
        "layerProgram": steps,
    }


def main() -> int:
    # Base normal + secondary layer-1 normal: base owns vd0 basis, layer 1 gets slot 0.
    row = binding.bind_recipe(_recipe(
        "*65n_82n(wpc/base:wpc/layer)",
        "lit_sm_r0c0n0_b1c1n1",
        2,  # TEX_2_NRM_2
        [{"layerIndex": 1, "hasNormal": True}],
    ))
    assert row["normalMarkedLayers"] == [0, 1]
    assert row["firstNormalBasisLayer"] == 0
    assert row["expectedWorldNormalCount"] == 2
    assert row["secondaryNormalBindings"] == [{
        "layerIndex": 1,
        "normalComponentOrdinal": 1,
        "mode": "transform2x2",
        "transformSlot": 0,
        "attribute": "_T6_NORMAL_TRANSFORM_0",
    }]

    # Critical counterexample to layerIndex-1: base/layer1 have no normal, layer2
    # is the first n component. World NRM_1 has no transform word, so layer2 is direct.
    row = binding.bind_recipe(_recipe(
        "*64_9_127n(wpc/base:wpc/decal:wpc/normal_layer)",
        "lit_sm_r0c0_b1c1_b2c2n2",
        3,  # TEX_3_NRM_1
        [
            {"layerIndex": 1, "hasNormal": False},
            {"layerIndex": 2, "hasNormal": True},
        ],
    ))
    assert row["normalMarkedLayers"] == [2]
    assert row["firstNormalBasisLayer"] == 2
    assert row["secondaryNormalBindings"][0]["layerIndex"] == 2
    assert row["secondaryNormalBindings"][0]["mode"] == "direct"
    assert row["secondaryNormalBindings"][0]["transformSlot"] is None

    # No base normal, two secondary normals: first secondary is direct; second
    # consumes slot 0. This is normal-component order, not material layer number.
    row = binding.bind_recipe(_recipe(
        "*64_82n_127n(wpc/base:wpc/n1:wpc/n2)",
        "lit_sm_r0c0_b1c1n1_b2c2n2",
        4,  # TEX_3_NRM_2
        [
            {"layerIndex": 1, "hasNormal": True},
            {"layerIndex": 2, "hasNormal": True},
        ],
    ))
    assert [item["mode"] for item in row["secondaryNormalBindings"]] == [
        "direct", "transform2x2"
    ]
    assert [item["transformSlot"] for item in row["secondaryNormalBindings"]] == [None, 0]

    # Base normal + two secondary normals: both extra normal components consume
    # the two ordered vd1 transform slots.
    row = binding.bind_recipe(_recipe(
        "*65n_82n_127n(wpc/base:wpc/n1:wpc/n2)",
        "lit_sm_r0c0n0_b1c1n1_b2c2n2",
        5,  # TEX_3_NRM_3
        [
            {"layerIndex": 1, "hasNormal": True},
            {"layerIndex": 2, "hasNormal": True},
        ],
    ))
    assert [item["transformSlot"] for item in row["secondaryNormalBindings"]] == [0, 1]

    # A recipe/world-layout disagreement is provenance failure, never a cue to
    # squeeze a secondary normal into an unavailable transform slot.
    try:
        binding.bind_recipe(_recipe(
            "*65n_82n(wpc/base:wpc/layer)",
            "lit_sm_r0c0n0_b1c1n1",
            1,  # TEX_2_NRM_1 contradicts two n-marked components
            [{"layerIndex": 1, "hasNormal": True}],
        ))
    except binding.NuketownNormalTransformBindingError as exc:
        assert "world format normalCount" in str(exc)
    else:
        raise AssertionError("wrong world normalCount was accepted")

    # Shader recipe hasNormal and retained n markers must agree exactly.
    try:
        binding.bind_recipe(_recipe(
            "*65n_82n(wpc/base:wpc/layer)",
            "lit_sm_fixture",
            2,
            [{"layerIndex": 1, "hasNormal": False}],
        ))
    except binding.NuketownNormalTransformBindingError as exc:
        assert "recipe secondary normal layers" in str(exc)
    else:
        raise AssertionError("recipe/material normal ownership mismatch was accepted")

    # Never silently widen this map-specific proof.
    try:
        binding.bind_recipe(_recipe(
            "*65n_82n(wpc/base:wpc/layer)", "lit_sm_fixture", 2,
            [{"layerIndex": 1, "hasNormal": True}],
        ), map_name="mp_raid")
    except binding.NuketownNormalTransformBindingError as exc:
        assert "source-gated" in str(exc)
    else:
        raise AssertionError("Nuketown transform binding widened to another map")

    manifest = {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": [
            _recipe("*65n_82n(wpc/base:wpc/layer)", "lit_a", 2, [{"layerIndex": 1, "hasNormal": True}]),
            _recipe("*64_9_127n(wpc/base:wpc/decal:wpc/n2)", "lit_b", 3, [
                {"layerIndex": 1, "hasNormal": False}, {"layerIndex": 2, "hasNormal": True}
            ]),
        ],
    }
    doc = binding.build_manifest(manifest)
    assert doc["summary"]["generatedMaterialCount"] == 2
    assert doc["summary"]["secondaryNormalMaterialCount"] == 2
    assert doc["summary"]["secondaryNormalLayerCount"] == 2
    assert doc["summary"]["directSecondaryNormalLayerCount"] == 1
    assert doc["summary"]["transformedSecondaryNormalLayerCount"] == 1
    assert doc["summary"]["allWorldFormatNormalCountsExact"] is True
    assert doc["summary"]["allRecipeNormalLayersExact"] is True

    print("PASS: Nuketown generated normal transform-slot binding v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
