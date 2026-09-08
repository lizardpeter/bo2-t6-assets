#!/usr/bin/env python3
"""Regression tests for the non-invasive special-render glTF contract overlay."""
from __future__ import annotations

import copy
import json

import t6_world_special_render_contract_overlay_v1 as overlay


def _contract() -> dict:
    raw_name = overlay.RAW_MATERIAL
    special = [
        {"material": raw_name, "family": "rawnormal_special", "programs": [{"techniqueType": "unlit", "runtimeConstantLeaves": []}]},
        {"material": "wpc/caulk_shadow_primary", "family": "shadowcaster", "programs": [{"techniqueType": "unlit", "runtimeConstantLeaves": []}]},
        {"material": "wpc/shadowcaster", "family": "shadowcaster", "programs": [{"techniqueType": "unlit", "runtimeConstantLeaves": []}]},
        {"material": "wpc/test_unlit", "family": "unlit", "programs": [{"techniqueType": "unlit", "runtimeConstantLeaves": [{"constantBuffer": "PerSceneConsts", "variable": "hdrControl0", "symbol": "cb0[20].x", "absoluteByteOffset": 320}]}]},
    ]
    raw = {
        "material": raw_name,
        "programs": [{"techniqueType": "lit", "pixelShaderSha256": "a" * 64, "dagSha256": "b" * 64}],
        "pixelShaders": [
            {
                "pixelShaderSha256": "a" * 64,
                "dagSha256": "b" * 64,
                "staticMaterialTextures": [{"image": "color"}],
                "staticMaterialConstants": [{"materialProperty": "ReflectionAmount", "literal": [0.0, 0.0, 0.0, 1.0]}],
                "runtimeTextureBindings": [{"textureRegister": 13, "textureName": "lightmapSamplerSecondary", "samplerRegister": 13, "samplerName": "lightmapSamplerSecondary"}],
                "runtimeConstantVariables": [{"cbRegister": 0, "constantBuffer": "PerSceneConsts", "variable": "sunDiffuse", "variableStartOffset": 304, "variableSizeBytes": 16, "usedSymbols": ["cb0[19].x"]}],
                "pixelInterpolantSymbols": ["v0.x"],
                "outputRoots": [{"output": "o0.x", "node": 1}, {"output": "o0.y", "node": 2}, {"output": "o0.z", "node": 3}, {"output": "o0.w", "node": 4}],
            }
        ],
    }
    shadows = [
        {"material": "wpc/caulk_shadow_primary", "depthPasses": [{"techniqueType": "depth prepass"}, {"techniqueType": "build shadowmap depth"}]},
        {"material": "wpc/shadowcaster", "depthPasses": [{"techniqueType": "depth prepass"}, {"techniqueType": "build shadowmap depth"}]},
    ]
    doc = {
        "format": overlay.FORMAT,
        "map": overlay.MAP,
        "rawnormal": raw,
        "unlitAndEmissiveSpecialMaterials": special,
        "shadowcasters": shadows,
    }
    doc["contractDigestSha256"] = overlay._digest(overlay._contract_core(doc))
    return doc


def _material(name: str) -> dict:
    return {
        "name": "display:" + name,
        "pbrMetallicRoughness": {
            "baseColorFactor": [0.2, 0.3, 0.4, 1.0],
            "metallicFactor": 0.0,
            "roughnessFactor": 1.0,
            "baseColorTexture": {"index": 3, "texCoord": 0},
        },
        "normalTexture": {"index": 4, "texCoord": 0},
        "extras": {"T6": {"sourceMaterial": name, "preexisting": {"keep": True}}},
    }


def _strip_overlay(material: dict) -> dict:
    out = copy.deepcopy(material)
    out.get("extras", {}).get("T6", {}).pop("renderReplayContract", None)
    return out


def main() -> int:
    contract = _contract()
    names = [
        overlay.RAW_MATERIAL,
        "wpc/caulk_shadow_primary",
        "wpc/shadowcaster",
        "wpc/test_unlit",
    ]
    gltf = {
        "asset": {"version": "2.0"},
        "materials": [_material(name) for name in names] + [_material("wpc/ordinary")],
        "images": [{"name": "preexisting-image"}],
        "textures": [{"source": 0}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987}],
        "extras": {"T6": {"preexistingRoot": 7}},
    }
    original = copy.deepcopy(gltf)
    out = overlay.apply_special_render_contract(
        gltf,
        contract,
        require_all_contract_materials=True,
    )

    # Caller input and every core/pre-existing Material field must be untouched.
    assert gltf == original
    assert out["images"] == original["images"]
    assert out["textures"] == original["textures"]
    assert out["samplers"] == original["samplers"]
    for before, after in zip(original["materials"], out["materials"]):
        assert _strip_overlay(after) == before

    root = out["extras"]["T6"]["renderReplayContractOverlay"]
    stats = root["stats"]
    assert stats["exactContractSpecialMaterialCount"] == 4
    assert stats["exactContractMatchedMaterialCount"] == 4
    assert stats["exactContractRawnormalCount"] == 1
    assert stats["exactContractShadowcasterCount"] == 2
    assert stats["portablePreviewOnlyMaterialCount"] == 1
    assert stats["exactRuntimeInputRequirementCount"] == 3
    assert root["unmatchedContractMaterials"] == []

    raw_meta = out["materials"][0]["extras"]["T6"]["renderReplayContract"]
    assert raw_meta["contractDigestSha256"] == contract["contractDigestSha256"]
    assert raw_meta["sourceMaterial"] == overlay.RAW_MATERIAL
    assert raw_meta["exactT6ShaderReplayMetadata"]["rawnormal"]["pixelShaders"][0]["dagSha256"] == "b" * 64
    assert out["materials"][4]["extras"]["T6"].get("renderReplayContract") is None

    # A display name is never accepted as provenance when sourceMaterial is absent.
    no_provenance = copy.deepcopy(original)
    no_provenance["materials"][0]["extras"]["T6"].pop("sourceMaterial")
    no_provenance["materials"][0]["name"] = overlay.RAW_MATERIAL
    partial = overlay.apply_special_render_contract(no_provenance, contract)
    assert overlay.RAW_MATERIAL in partial["extras"]["T6"]["renderReplayContractOverlay"]["unmatchedContractMaterials"]
    try:
        overlay.apply_special_render_contract(no_provenance, contract, require_all_contract_materials=True)
    except overlay.RenderContractOverlayError:
        pass
    else:
        raise AssertionError("require-all accepted a display-name-only Material")

    duplicate = copy.deepcopy(original)
    duplicate["materials"].append(_material(overlay.RAW_MATERIAL))
    try:
        overlay.apply_special_render_contract(duplicate, contract)
    except overlay.RenderContractOverlayError:
        pass
    else:
        raise AssertionError("duplicate sourceMaterial provenance was accepted")

    damaged = copy.deepcopy(contract)
    damaged["rawnormal"]["material"] = "wrong"
    try:
        overlay.apply_special_render_contract(original, damaged)
    except overlay.RenderContractOverlayError:
        pass
    else:
        raise AssertionError("damaged contract digest/identity was accepted")

    print("PASS t6_world_special_render_contract_overlay_v1 regression")
    print(json.dumps(stats, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
