#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_world_lightmap_material_specialize_v1 as specialize
from t6_world_lightmap_preview_embed_v1 import FORMAT as PREVIEW_FORMAT, ROOT_KEY as PREVIEW_ROOT


def _role(asset: str, texture: int, image: int, sha: str) -> dict:
    return {
        "present": True,
        "embedded": True,
        "gfxImageAsset": asset,
        "sourceTexture": asset + ".dds",
        "codeTextureSource": 5,
        "samplerAccessor": "lightmapSamplerSecondary",
        "sha256": sha,
        "preview": {
            "format": PREVIEW_FORMAT,
            "previewOnly": True,
            "dataTexture": True,
            "previewTextureIndex": texture,
            "previewImageIndex": image,
            "previewBufferView": image,
            "previewPngSha256": (sha[::-1]),
            "sourceDdsSha256": sha,
            "width": 8,
            "height": 12,
        },
    }


def _absent(role: str) -> dict:
    return {
        "present": False,
        "embedded": False,
        "gfxImageAsset": None,
        "sourceTexture": None,
        "codeTextureSource": 4 if role == "primary" else 5,
        "samplerAccessor": "lightmapSamplerPrimary" if role == "primary" else "lightmapSamplerSecondary",
    }


def document() -> dict:
    retail_material = {
        "name": "*retail_generated",
        "extras": {"T6": {
            "sourceMaterial": "*retail_generated",
            "generatedShaderRecipeV1": {
                "material": "*retail_generated",
                "techniqueSet": "lit_sm_r0c0_b1c1",
                "pixelShaderArchetype": "sha256:" + "1" * 64,
                "worldVertFormats": [1],
                "proof": {"kind": "specialization fixture"},
            },
        }},
    }
    ordinary_material = {"name": "ordinary"}
    a = "a" * 64
    b = "b" * 64
    lightmaps = [
        {"index": 0, "primary": _absent("primary"), "secondary": _role("lm0", 10, 20, a)},
        {"index": 1, "primary": _absent("primary"), "secondary": _role("lm1", 11, 21, b)},
    ]
    bindings = [
        {"surfaceIndex": 0, "groupIndex": 0, "lightmapIndex": 0, "hasLightmap": True, "lightmapTexCoord": 1},
        {"surfaceIndex": 1, "groupIndex": 0, "lightmapIndex": 1, "hasLightmap": True, "lightmapTexCoord": 1},
        # Same tuple as surface 0 => must reuse the same specialized material.
        {"surfaceIndex": 2, "groupIndex": 1, "lightmapIndex": 0, "hasLightmap": True, "lightmapTexCoord": 1},
        {"surfaceIndex": 3, "groupIndex": 1, "lightmapIndex": 31, "hasLightmap": False, "lightmapTexCoord": 1},
        # Ordinary material also specializes correctly; the pass is not generated-only.
        {"surfaceIndex": 4, "groupIndex": 2, "lightmapIndex": 1, "hasLightmap": True, "lightmapTexCoord": 2},
    ]

    def prim(surface: int, lightmap: int, material: int, texcoord: int) -> dict:
        attrs = {"POSITION": 0, "TEXCOORD_0": 1}
        attrs[f"TEXCOORD_{texcoord}"] = 2
        return {
            "material": material,
            "attributes": attrs,
            "extras": {"T6": {"index": surface, "lightmapIndex": lightmap}},
        }

    return {
        "materials": [retail_material, ordinary_material],
        "meshes": [
            {"primitives": [prim(0, 0, 0, 1), prim(1, 1, 0, 1)]},
            {"primitives": [prim(2, 0, 0, 1), prim(3, 31, 0, 1)]},
            {"primitives": [prim(4, 1, 1, 2)]},
        ],
        "extras": {"T6": {
            PREVIEW_ROOT: {"format": PREVIEW_FORMAT},
            "lightmapArchive": {
                "format": "t6-world-lightmap-glb-archive-v3",
                "lightmaps": lightmaps,
                "surfaceBindings": bindings,
            },
        }},
    }


def expect_error(doc: dict, text: str) -> None:
    try:
        specialize.specialize(doc, b"raw")
    except specialize.LightmapMaterialSpecializeError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError(f"expected specialization error containing {text!r}")


def main() -> int:
    source = document()
    original_recipe = copy.deepcopy(source["materials"][0]["extras"]["T6"]["generatedShaderRecipeV1"])
    out, raw, stats = specialize.specialize(source, b"exact-bin")
    assert raw == b"exact-bin"
    assert stats == {
        "sourceMaterialCount": 2,
        "finalMaterialCount": 5,
        "specializedMaterialCount": 3,
        "redirectedLightmappedPrimitiveCount": 4,
        "noLightmapPrimitiveCount": 1,
        "worldSurfacePrimitiveCount": 5,
        "missingPresentPreviewRoleUseCount": 0,
        "binByteIdentical": True,
    }
    # Two generated variants: LM0/TC1 and LM1/TC1. Surface 2 reuses LM0.
    p0 = out["meshes"][0]["primitives"][0]
    p1 = out["meshes"][0]["primitives"][1]
    p2 = out["meshes"][1]["primitives"][0]
    p3 = out["meshes"][1]["primitives"][1]
    p4 = out["meshes"][2]["primitives"][0]
    assert p0["material"] == p2["material"]
    assert p0["material"] != p1["material"]
    assert p3["material"] == 0  # no-lightmap keeps retail shell
    assert p4["material"] not in (0, 1)

    v0 = out["materials"][p0["material"]]
    b0 = v0["extras"]["T6"][specialize.BINDING_KEY]
    assert b0["retailMaterialIndex"] == 0
    assert b0["retailMaterialName"] == "*retail_generated"
    assert b0["lightmapIndex"] == 0
    assert b0["lightmapTexCoord"] == 1
    assert b0["secondary"]["previewAvailable"] is True
    assert b0["secondary"]["previewTextureIndex"] == 10
    # Canonical recipe identity remains retail, even though preview shell name differs.
    assert v0["name"] != "*retail_generated"
    assert v0["extras"]["T6"]["generatedShaderRecipeV1"] == original_recipe
    assert v0["extras"]["T6"]["generatedShaderRecipeV1"]["material"] == "*retail_generated"

    contract = out["extras"]["T6"][specialize.ROOT_KEY]
    assert contract["format"] == specialize.FORMAT
    assert len(contract["variants"]) == 3
    assert contract["stats"]["binByteIdentical"] is True

    # Deterministic from untouched source.
    out2, raw2, stats2 = specialize.specialize(copy.deepcopy(source), b"exact-bin")
    assert raw2 == raw and stats2 == stats and out2 == out

    mismatch = document()
    mismatch["meshes"][0]["primitives"][0]["extras"]["T6"]["lightmapIndex"] = 1
    expect_error(mismatch, "primitive lightmapIndex")

    missing_tc = document()
    del missing_tc["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_1"]
    expect_error(missing_tc, "TEXCOORD_1 is absent")

    missing_surface = document()
    missing_surface["extras"]["T6"]["lightmapArchive"]["surfaceBindings"].append({
        "surfaceIndex": 99, "lightmapIndex": 0, "hasLightmap": True, "lightmapTexCoord": 1
    })
    expect_error(missing_surface, "canonical surface bindings did not match")

    duplicate_surface = document()
    duplicate_surface["meshes"][2]["primitives"].append(copy.deepcopy(duplicate_surface["meshes"][0]["primitives"][0]))
    expect_error(duplicate_surface, "occurs in multiple primitives")

    missing_preview = document()
    del missing_preview["extras"]["T6"][PREVIEW_ROOT]
    expect_error(missing_preview, "is required")

    already = document()
    already["extras"]["T6"][specialize.ROOT_KEY] = {"format": specialize.FORMAT}
    expect_error(already, "already attached")

    print("PASS: exact per-surface T6 lightmap preview material specialization v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
