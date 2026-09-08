#!/usr/bin/env python3
"""Regression for production pipeline v52 special-Material replay wiring."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v52 as v52
import t6_world_special_render_contract_overlay_v1 as overlay
from t6_glb_parse_v1 import parse_glb
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _contract() -> dict:
    names = [
        overlay.RAW_MATERIAL,
        "wpc/caulk_shadow_primary",
        "wpc/shadowcaster",
        "wpc/special_03",
        "wpc/special_04",
        "wpc/special_05",
        "wpc/special_06",
        "wpc/special_07",
        "wpc/special_08",
        "wpc/special_09",
        "wpc/special_10",
    ]
    special = [
        {
            "material": name,
            "family": (
                "rawnormal_special" if name == overlay.RAW_MATERIAL
                else "shadowcaster" if name in {"wpc/caulk_shadow_primary", "wpc/shadowcaster"}
                else "unlit"
            ),
            "techniqueSet": "fixture/" + str(i),
            "programs": [
                {
                    "techniqueType": "unlit",
                    "technique": "fixture_tech",
                    "groupKey": "fixture_group",
                    "pixelShaderSha256": "1" * 64,
                    "staticMaterialTexture": {"name": "colorMap", "image": "fixture"},
                    "staticMaterialConstants": [],
                    "runtimeConstantLeaves": [],
                }
            ],
        }
        for i, name in enumerate(names)
    ]
    raw = {
        "material": overlay.RAW_MATERIAL,
        "programs": [
            {
                "techniqueType": "lit",
                "technique": "fixture_lit",
                "groupKey": "fixture_lit_group",
                "pixelShaderSha256": "2" * 64,
                "dagSha256": "3" * 64,
                "staticMaterialTextureCount": 3,
                "staticMaterialConstantCount": 3,
                "runtimeTextureBindingCount": 1,
                "runtimeConstantVariableCount": 1,
                "pixelInterpolantSymbolCount": 1,
            }
        ],
        "pixelShaders": [
            {
                "pixelShaderSha256": "2" * 64,
                "asset": "fixture_ps",
                "dagSha256": "3" * 64,
                "controlFlow": False,
                "ifCount": 0,
                "nodeCount": 4,
                "outputRoots": [
                    {"output": "o0.x", "node": 0},
                    {"output": "o0.y", "node": 1},
                    {"output": "o0.z", "node": 2},
                    {"output": "o0.w", "node": 3},
                ],
                "pixelInterpolantSymbols": ["v0.x"],
                "staticMaterialTextures": [
                    {"image": "color", "materialProperty": "ColorMap"},
                    {"image": "normal", "materialProperty": "Normal_Map"},
                    {"image": "spec", "materialProperty": "SpecularAndGloss2"},
                ],
                "staticMaterialConstants": [
                    {"materialProperty": "ReflectionAmount", "literal": [0.0, 0.0, 0.0, 1.0]},
                    {"materialProperty": "SpecularAmount", "literal": [0.0, 0.0, 0.0, 1.0]},
                    {"materialProperty": "NormalHeightMultiplier", "literal": [0.24, 0.0, 0.0, 1.0]},
                ],
                "runtimeTextureBindings": [
                    {"textureRegister": 13, "textureName": "lightmapSamplerSecondary", "samplerRegister": 13, "samplerName": "lightmapSamplerSecondary"}
                ],
                "runtimeConstantVariables": [
                    {"cbRegister": 0, "constantBuffer": "PerSceneConsts", "variable": "sunDiffuse", "variableStartOffset": 304, "variableSizeBytes": 16, "usedSymbols": ["cb0[19].x"]}
                ],
                "rdefDigestSha256": "4" * 64,
            }
        ],
    }
    shadows = [
        {
            "material": name,
            "depthPasses": [
                {"techniqueType": "depth prepass", "stateBits": {"depthWrite": True}},
                {"techniqueType": "build shadowmap depth", "stateBits": {"depthWrite": True}},
            ],
        }
        for name in ("wpc/caulk_shadow_primary", "wpc/shadowcaster")
    ]
    doc = {
        "format": overlay.FORMAT,
        "producer": "fixture",
        "map": overlay.MAP,
        "sourceClosureManifestSha256": "5" * 64,
        "sourceEvidence": {},
        "summary": {
            "rawnormalProgramCount": 1,
            "rawnormalPixelShaderCount": 1,
            "specialMaterialCount": 11,
            "shadowcasterMaterialCount": 2,
            "rawnormalStaticMaterialImageCount": 3,
            "rawnormalRuntimeTextureIdentityCount": 1,
            "rawnormalRuntimeConstantVariableIdentityCount": 1,
        },
        "rawnormal": raw,
        "unlitAndEmissiveSpecialMaterials": special,
        "shadowcasters": shadows,
        "consumerModes": {},
        "proofBoundary": "fixture",
    }
    doc["contractDigestSha256"] = overlay._digest(overlay._contract_core(doc))
    return doc


def _material(name: str) -> dict:
    return {
        "name": "display:" + name,
        "pbrMetallicRoughness": {"baseColorFactor": [0.3, 0.4, 0.5, 1.0]},
        "extras": {"T6": {"sourceMaterial": name, "preexisting": True}},
    }


def main() -> int:
    original_v51 = v52.v51.run_oat_textured_pipeline
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            out.mkdir()
            contract_path = root / "contract.json"
            seal_path = root / "seal.json"
            contract = _contract()
            contract_raw = (json.dumps(contract, indent=2, sort_keys=True) + "\n").encode()
            contract_path.write_bytes(contract_raw)
            seal = {
                "format": v52.SEAL_FORMAT,
                "map": overlay.MAP,
                "generated": {
                    "fileSha256": _sha(contract_raw),
                    "contractDigestSha256": contract["contractDigestSha256"],
                },
            }
            seal_path.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            source_names = [row["material"] for row in contract["unlitAndEmissiveSpecialMaterials"]]
            base_doc = {
                "asset": {"version": "2.0"},
                "buffers": [{"byteLength": 7}],
                "materials": [_material(name) for name in source_names] + [_material("wpc/ordinary")],
                "extras": {"T6": {"generatedShaderRecipeArchive": {"keep": True}}},
            }
            base_raw = b"PAYLOAD"
            base_glb = glb_bytes(base_doc, base_raw)
            base_gltf = gltf_bytes(base_doc, base_raw)

            def fake_v51(**kwargs):
                assert kwargs["map_name"] == overlay.MAP
                kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
                glb_path = kwargs["output_dir"] / f"{overlay.MAP}.world_oat_portable_textured_v51.glb"
                gltf_path = kwargs["output_dir"] / f"{overlay.MAP}.world_oat_portable_textured_v51.gltf"
                glb_path.write_bytes(base_glb)
                gltf_path.write_bytes(base_gltf)
                manifest_path = kwargs["output_dir"] / f"{overlay.MAP}.world_oat_textured_export_manifest_v51.json"
                manifest_path.write_text("{}\n", encoding="utf-8")
                return {
                    "format": v52.BASE_FORMAT,
                    "map": overlay.MAP,
                    "inputs": {"existing": True},
                    "outputs": {
                        "oatPortableTexturedGlb": {"path": str(glb_path), "sha256": _sha(base_glb)},
                        "oatPortableTexturedGltf": {"path": str(gltf_path), "sha256": _sha(base_gltf)},
                        "generatedFinalOutputReplayContract": {"path": str(root / "generated.json"), "sha256": "6" * 64},
                    },
                    "stats": {"generatedFinalOutputReplayContract": {"materialCount": 120}},
                    "validation": {"v51ReplayContractGenerated": True},
                    "policies": {"v51FinalOutputReplayContract": "keep"},
                    "manifest": {"path": str(manifest_path)},
                }

            v52.v51.run_oat_textured_pipeline = fake_v51
            dummy = root / "dummy"
            dummy.write_bytes(b"x")
            result = v52.run_oat_textured_pipeline(
                special_render_contract_path=contract_path,
                special_render_contract_seal_path=seal_path,
                map_name=overlay.MAP,
                surfaces_path=dummy,
                vd0_path=dummy,
                vd1_path=dummy,
                indices_path=dummy,
                materials_path=dummy,
                catalog_path=dummy,
                prefix_path=dummy,
                asset_pointer_array_virtual_base=0x1000,
                oat_material_root=root,
                oat_shader_root=None,
                oat_source_root=None,
                dds_root=root,
                output_dir=out,
                format_registry_path=dummy,
                lightmap_catalog_path=None,
                reflection_probe_catalog_path=None,
                generated_shader_recipe_manifest_path=None,
                generated_shader_expanded_world_path=None,
                generated_normal_basis_proof_path=None,
                write_gltf=True,
                shadowmap_bias=8192,
                shadowmap_scale=2.0,
                allow_unresolved_world_materials=False,
                allow_missing_oat_materials=False,
                allow_missing_dds=False,
                allow_missing_preview_textures=False,
                allow_missing_dependency_textures=False,
                allow_missing_lightmap_dds=False,
                allow_missing_reflection_probe_dds=False,
            )

            assert result["format"] == v52.FORMAT
            assert result["validation"]["v52SpecialRenderContractAllMaterialsMatched"] is True
            assert result["validation"]["v52SpecialRenderContractMaterialCount"] == 11
            assert result["validation"]["v52SpecialRenderContractRawnormalCount"] == 1
            assert result["validation"]["v52SpecialRenderContractShadowcasterCount"] == 2
            assert result["validation"]["v52LogicalGlbBinByteIdenticalToV51"] is True
            assert result["stats"]["specialRenderReplayContract"]["exactContractMatchedMaterialCount"] == 11
            assert result["stats"]["generatedFinalOutputReplayContract"]["materialCount"] == 120
            assert result["policies"]["v51FinalOutputReplayContract"] == "keep"

            final_glb_path = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
            assert final_glb_path.name.endswith("_v52.glb")
            final_doc, final_raw = parse_glb(final_glb_path.read_bytes())
            assert final_raw == base_raw
            assert final_doc["extras"]["T6"]["generatedShaderRecipeArchive"] == {"keep": True}
            overlay_root = final_doc["extras"]["T6"]["renderReplayContractOverlay"]
            assert overlay_root["stats"]["exactContractMatchedMaterialCount"] == 11
            raw_material = next(
                material for material in final_doc["materials"]
                if material["extras"]["T6"]["sourceMaterial"] == overlay.RAW_MATERIAL
            )
            assert raw_material["pbrMetallicRoughness"] == {"baseColorFactor": [0.3, 0.4, 0.5, 1.0]}
            assert "rawnormal" in raw_material["extras"]["T6"]["renderReplayContract"]["exactT6ShaderReplayMetadata"]

            # Seal mismatch is a hard preflight failure before v51 is called.
            bad_seal = copy.deepcopy(seal)
            bad_seal["generated"]["fileSha256"] = "0" * 64
            bad_seal_path = root / "bad_seal.json"
            bad_seal_path.write_text(json.dumps(bad_seal), encoding="utf-8")
            called = False
            def should_not_run(**kwargs):
                nonlocal called
                called = True
                raise AssertionError("v51 should not run after a seal failure")
            v52.v51.run_oat_textured_pipeline = should_not_run
            try:
                v52.run_oat_textured_pipeline(
                    special_render_contract_path=contract_path,
                    special_render_contract_seal_path=bad_seal_path,
                    map_name=overlay.MAP,
                    output_dir=out,
                )
            except v52.OatTexturedPipelineV52Error:
                pass
            else:
                raise AssertionError("tampered contract seal was accepted")
            assert called is False

    finally:
        v52.v51.run_oat_textured_pipeline = original_v51

    print("PASS t6_oat_world_textured_export_pipeline_v52 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
