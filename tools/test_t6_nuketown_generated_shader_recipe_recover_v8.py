#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v8 as recover


def _dag(channel: str):
    # Structurally representative sample * 2 + -1 forensic DAG.
    nodes = [
        {"id": 0, "kind": "sample", "resource": "normalMapSampler1", "channel": channel, "sampler": "s2"},
        {"id": 1, "kind": "lit", "value": 2.0},
        {"id": 2, "kind": "mul", "args": [0, 1]},
        {"id": 3, "kind": "lit", "value": -1.0},
        {"id": 4, "kind": "add", "args": [2, 3]},
    ]
    return {
        "format": "t6-generated-height-weight-dag-v1",
        "root": 4,
        "nodes": nodes,
        "nodeCount": 5,
        "ordering": "reachable child-before-parent; operation argument order preserved",
        "forensicDagSha256": channel * 64 if channel in "xy" else "f" * 64,
    }


def _manifest(shader_sha: str):
    material = "*65n_82n(wpc/base:wpc/layer)"
    technique = "lit_sm_r0c0n0_b1c1n1"
    return {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": [{
            "material": material,
            "techniqueSet": technique,
            "pixelShaderArchetype": "sha256:" + shader_sha,
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
            recover.v7.SHADER_BINDING_KEY: {
                "format": "t6-generated-normal-transform-recipe-binding-v1",
                "material": material,
                "techniqueSet": technique,
                "crossProofAgreement": True,
                "secondaryNormalBindings": [{
                    "layerIndex": 1,
                    "mode": "transform2x2",
                    "normalTransformIndex": 0,
                    "attribute": "_T6_NORMAL_TRANSFORM_0",
                }],
            },
        }],
        "recovery": {
            "format": "t6-nuketown-generated-shader-recipe-recovery-v7",
            "recipeRowsSha256": "c" * 64,
        },
    }


def _decoded(shader_sha: str, mode="transform2x2"):
    return {
        "format": recover.normal_decode.SET_FORMAT,
        "techniqueSet": "lit_sm_r0c0n0_b1c1n1",
        "pixelShaderSha256": shader_sha,
        "normalLayerCount": 1,
        "allDecodeLeavesSampleOnly": True,
        "layers": [{
            "layerIndex": 1,
            "normalResource": "normalMapSampler1",
            "sampleChannels": ["x", "y"],
            "transformMode": mode,
            "decodePairSha256": "d" * 64,
            "components": [
                {"component": "x", "forensicDagSha256": "e" * 64, "forensicDag": _dag("x")},
                {"component": "y", "forensicDagSha256": "f" * 64, "forensicDag": _dag("y")},
            ],
        }],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_recipe_v8_") as td:
        root = Path(td)
        (root / "shader_bin").mkdir()
        (root / "techniques").mkdir()
        shader = b"DXBC-normal-decode-recipe-fixture"
        shader_sha = hashlib.sha256(shader).hexdigest()
        (root / "shader_bin" / "ps_fixture.cso").write_bytes(shader)
        (root / "techniques" / "fixture.tech").write_text(
            'normalMapSampler1 = material.normalMap1;\n', encoding="utf-8"
        )

        old_resolve = recover.resolve_slot_shader
        old_extract = recover.normal_decode.extract_normal_decode_dags
        try:
            recover.resolve_slot_shader = lambda oat_root, technique, slot_index: {
                "techniqueFile": "techniques/fixture.tech",
                "pixelShaders": [{
                    "asset": "fixture",
                    "relativeFile": "shader_bin/ps_fixture.cso",
                    "sha256": shader_sha,
                }],
            }
            recover.normal_decode.extract_normal_decode_dags = lambda blob, technique: _decoded(shader_sha)
            result = recover._augment_normal_sample_decode(
                _manifest(shader_sha), oat_root=root
            )
        finally:
            recover.resolve_slot_shader = old_resolve
            recover.normal_decode.extract_normal_decode_dags = old_extract

        row = result["materials"][0][recover.NORMAL_DECODE_KEY]
        assert row["pixelShaderArchetype"] == "sha256:" + shader_sha
        assert row["normalLayerCount"] == 1
        assert row["allDecodeLeavesExact"] is True
        layer = row["layers"][0]
        assert layer["normalResource"] == "normalMapSampler1"
        assert layer["sampleChannels"] == ["x", "y"]
        assert layer["materialArgument"] == "normalMap1"
        assert layer["portableDependency"] == {"layerIndex": 1, "role": "normalMap"}
        assert layer["transformMode"] == "transform2x2"
        assert layer["normalTransformIndex"] == 0
        assert layer["normalTransformAttribute"] == "_T6_NORMAL_TRANSFORM_0"
        assert [component["component"] for component in layer["components"]] == ["x", "y"]

        rec = result["recovery"]
        assert rec["format"] == recover.FORMAT
        assert rec["baseRecoveryFormat"] == "t6-nuketown-generated-shader-recipe-recovery-v7"
        assert rec["normalDecodeMaterialCount"] == 1
        assert rec["normalDecodeLayerOccurrenceCount"] == 1
        assert rec["uniqueNormalDecodePairDagCount"] == 1
        assert rec["uniqueNormalDecodeComponentDagCount"] == 2
        assert rec["normalDecodeMaterialArguments"] == ["normalMap1"]
        assert rec["normalSampleDecodeCoverageComplete"] is True

        # Exact .tech sampler assignment is mandatory.
        (root / "techniques" / "fixture.tech").write_text("// no material sampler assignment\n", encoding="utf-8")
        try:
            recover.resolve_slot_shader = lambda oat_root, technique, slot_index: {
                "techniqueFile": "techniques/fixture.tech",
                "pixelShaders": [{"relativeFile": "shader_bin/ps_fixture.cso", "sha256": shader_sha}],
            }
            recover.normal_decode.extract_normal_decode_dags = lambda blob, technique: _decoded(shader_sha)
            try:
                recover._augment_normal_sample_decode(_manifest(shader_sha), oat_root=root)
            except recover.NuketownShaderRecipeRecoveryV8Error as exc:
                assert "has no exact .tech material assignment" in str(exc)
            else:
                raise AssertionError("normal sampler without exact material assignment was accepted")
        finally:
            recover.resolve_slot_shader = old_resolve
            recover.normal_decode.extract_normal_decode_dags = old_extract

        # Decode's own transform mode must agree with the independent v7 proof.
        (root / "techniques" / "fixture.tech").write_text(
            'normalMapSampler1 = material.normalMap1;\n', encoding="utf-8"
        )
        try:
            recover.resolve_slot_shader = lambda oat_root, technique, slot_index: {
                "techniqueFile": "techniques/fixture.tech",
                "pixelShaders": [{"relativeFile": "shader_bin/ps_fixture.cso", "sha256": shader_sha}],
            }
            recover.normal_decode.extract_normal_decode_dags = lambda blob, technique: _decoded(shader_sha, mode="direct")
            try:
                recover._augment_normal_sample_decode(_manifest(shader_sha), oat_root=root)
            except recover.NuketownShaderRecipeRecoveryV8Error as exc:
                assert "decode transform mode 'direct' != dual-proof transform mode 'transform2x2'" in str(exc)
            else:
                raise AssertionError("decode/transform proof disagreement was accepted")
        finally:
            recover.resolve_slot_shader = old_resolve
            recover.normal_decode.extract_normal_decode_dags = old_extract

    print("PASS: Nuketown generated shader recovery v8 exact normal sample decode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
