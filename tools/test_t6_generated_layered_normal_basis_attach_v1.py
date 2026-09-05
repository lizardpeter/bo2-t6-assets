#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_generated_layered_normal_basis_attach_v1 as attach
from t6_generated_shader_recipe_contract_v1 import canonical_layer_program


PS = "1" * 64
VS = "2" * 64
TECH_NORMAL = "lit_sm_r0c0n0_b1c1n1"
TECH_COLOR = "lit_sm_r0c0_b1c1"


def recipe(material: str, technique: str, *, normal: bool) -> dict:
    row = {
        "material": material,
        "techniqueSet": technique,
        "pixelShaderArchetype": f"sha256:{PS}",
        "vertexShaderArchetype": f"sha256:{VS}",
        "worldVertFormats": [0],
        "layerProgram": canonical_layer_program(technique),
        "proof": {"kind": "synthetic attachment regression"},
    }
    if normal:
        row["normalTransformBindingsV1"] = {
            "secondaryNormalBindings": [
                {
                    "layerIndex": 1,
                    "mode": "direct",
                    "transformSlot": None,
                    "attribute": None,
                }
            ]
        }
    return row


def manifest() -> dict:
    return {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": [
            recipe("*normal_fixture", TECH_NORMAL, normal=True),
            recipe("*color_fixture", TECH_COLOR, normal=False),
        ],
    }


def proof() -> dict:
    return {
        "format": "t6-generated-layered-normal-vs-basis-probe-v2",
        "profiles": [
            {
                "techniqueSet": TECH_NORMAL,
                "vertexShaderSha256": VS,
                "pixelShaderSha256": PS,
                "directRoleMatches": {
                    "baseIsWorldNormalFromNormal0": True,
                    "xBasisIsWorldTangentFromTangent0": True,
                    "yBasisExactCrossHandedness": True,
                    "yBasisPhysicalRole": "worldBinormal",
                },
                "binormalAlgebra": {
                    "status": "exact-binormal",
                    "comparison": {
                        "uniqueMatch": "cross(normal,tangent)*handedness",
                    },
                },
            }
        ],
        "summary": {
            "allThreeBasisRolesExact": True,
            "profilesV2Sha256": "3" * 64,
        },
    }


def expect_error(fn, text: str) -> None:
    try:
        fn()
    except attach.LayeredNormalBasisAttachError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError(f"expected LayeredNormalBasisAttachError containing {text!r}")


def main() -> int:
    source = manifest()
    out, stats = attach.attach_manifest(source, proof())
    assert stats["generatedRecipeCount"] == 2
    assert stats["secondaryNormalRecipeCount"] == 1
    assert stats["attachedBasisCount"] == 1
    assert stats["allSecondaryNormalRecipesAttached"]

    by_name = {row["material"]: row for row in out["materials"]}
    normal = by_name["*normal_fixture"]
    color = by_name["*color_fixture"]
    payload = normal[attach.ATTACHMENT_KEY]
    assert payload["format"] == attach.FORMAT
    assert payload["vertexShaderSha256"] == VS
    assert payload["pixelShaderSha256"] == PS
    assert payload["secondaryNormalLayers"] == [1]
    assert payload["directRoleMatches"]["yBasisPhysicalRole"] == "worldBinormal"
    assert payload["binormalAlgebra"]["status"] == "exact-binormal"
    assert attach.ATTACHMENT_KEY not in color
    # Input is immutable.
    assert attach.ATTACHMENT_KEY not in source["materials"][0]

    gltf = {
        "materials": [
            {
                "name": row["material"],
                "extras": {"T6": {attach.CANONICAL_RECIPE_KEY: copy.deepcopy(row)}},
            }
            for row in source["materials"]
        ]
    }
    gltf_stats = attach.attach_gltf(gltf, proof())
    assert gltf_stats["attachedBasisCount"] == 1
    assert gltf["materials"][0]["extras"]["T6"][attach.CANONICAL_RECIPE_KEY][attach.ATTACHMENT_KEY]
    assert attach.ATTACHMENT_KEY not in gltf["materials"][1]["extras"]["T6"][attach.CANONICAL_RECIPE_KEY]
    assert gltf["extras"]["T6"]["layeredNormalBasisAttachment"]["stats"] == gltf_stats

    bad_vs = proof()
    bad_vs["profiles"][0]["vertexShaderSha256"] = "4" * 64
    expect_error(lambda: attach.attach_manifest(manifest(), bad_vs), "basis proof VS differs")

    bad_roles = proof()
    bad_roles["profiles"][0]["directRoleMatches"]["yBasisExactCrossHandedness"] = False
    expect_error(lambda: attach.attach_manifest(manifest(), bad_roles), "all three physical normal-basis roles are not exact")

    bad_binding = manifest()
    bad_binding["materials"][0]["normalTransformBindingsV1"]["secondaryNormalBindings"] = []
    expect_error(lambda: attach.attach_manifest(bad_binding, proof()), "transform binding layers []")

    bad_global = proof()
    bad_global["summary"]["allThreeBasisRolesExact"] = False
    expect_error(lambda: attach.attach_manifest(manifest(), bad_global), "does not close all three")

    print("PASS t6_generated_layered_normal_basis_attach_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
