#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_blender_generated_layer_preview_v4 as v4
import t6_blender_generated_layer_preview_v5 as v5
import t6_blender_generated_layer_preview_v6 as v6
from t6_generated_shader_recipe_contract_v1 import canonical_layer_program

TECH = "lit_sm_r0c0n0_b1c1n1"
PS = "1" * 64
VS = "2" * 64


def recipe(*, transformed=False):
    layer = {
        "layerIndex": 1,
        "normalResource": "normalMapSampler1",
        "components": [],
        "materialArgument": "normalMap1",
        "portableDependency": {"layerIndex": 1, "role": "normalMap"},
        "transformMode": "transform2x2" if transformed else "direct",
        "normalTransformIndex": 0 if transformed else None,
        "normalTransformAttribute": "_T6_NORMAL_TRANSFORM_0" if transformed else None,
    }
    return {
        "material": "*fixture",
        "techniqueSet": TECH,
        "pixelShaderArchetype": f"sha256:{PS}",
        "vertexShaderArchetype": f"sha256:{VS}",
        "worldVertFormats": [0],
        "layerProgram": canonical_layer_program(TECH),
        "proof": {"kind": "synthetic v6 trust boundary"},
        "normalSampleDecodeV2": {
            "format": "t6-generated-normal-sample-decode-recipe-v2",
            "material": "*fixture",
            "techniqueSet": TECH,
            "pixelShaderArchetype": f"sha256:{PS}",
            "baseline": {"mode": "zero", "normalResource": None, "components": []},
            "layers": [layer],
            "allDecodeLeavesExact": True,
        },
        "normalTransformShaderBindingsV1": {
            "secondaryNormalBindings": [{
                "layerIndex": 1,
                "mode": layer["transformMode"],
                "normalTransformIndex": layer["normalTransformIndex"],
                "attribute": layer["normalTransformAttribute"],
            }],
            "crossProofAgreement": True,
        },
        "layeredNormalBasisV1": {
            "format": "t6-generated-layered-normal-basis-recipe-v1",
            "material": "*fixture",
            "techniqueSet": TECH,
            "secondaryNormalLayers": [1],
            "directRoleMatches": {
                "baseIsWorldNormalFromNormal0": True,
                "xBasisIsWorldTangentFromTangent0": True,
                "yBasisExactCrossHandedness": True,
                "yBasisPhysicalRole": "worldBinormal",
            },
        },
    }


def document(*, transformed=False):
    attrs = {
        "POSITION": 0,
        "_T6_LAYER_WEIGHTS": 1,
        "_T6_WORLD_NORMAL": 2,
        "_T6_WORLD_TANGENT": 3,
        "_T6_WORLD_BINORMAL": 4,
    }
    if transformed:
        attrs["_T6_NORMAL_TRANSFORM_0"] = 5
    return {
        "asset": {"version": "2.0"},
        "materials": [{
            "name": "*fixture",
            "extras": {"T6": {"generatedShaderRecipeV1": recipe(transformed=transformed)}},
        }],
        "meshes": [{"primitives": [{"material": 0, "attributes": attrs}]}],
        "extras": {"T6": {
            "generatedAttributeContract": {
                "format": "t6-world-generated-attribute-contract-v1",
                "stats": {"generatedPrimitiveCount": 1, "generatedColorRetypeCount": 1},
            },
            "generatedNormalBasisAttributesV2": {
                "format": "t6-generated-normal-basis-attributes-v2",
                "stats": {"generatedPrimitiveCount": 1},
                "contractSha256": "a" * 64,
            },
        }},
    }


def write_doc(root: Path, doc: dict, name="fixture.gltf") -> Path:
    path = root / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def expect_error(path: Path, text: str):
    try:
        v6._root_v20_preflight(path)
    except v6.BlenderLayerPreviewError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError(f"expected v6 preflight error containing {text!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_blender_v6_") as td:
        root = Path(td)
        path = write_doc(root, document())
        contract = v6._root_v20_preflight(path)
        assert contract["format"] == "t6-generated-normal-basis-attributes-v2"
        assert contract["contractSha256"] == "a" * 64

        missing = document()
        del missing["meshes"][0]["primitives"][0]["attributes"]["_T6_WORLD_BINORMAL"]
        expect_error(write_doc(root, missing, "missing.gltf"), "lacks v20 attributes")

        transformed = document(transformed=True)
        transformed_path = write_doc(root, transformed, "transformed.gltf")
        v6._root_v20_preflight(transformed_path)
        del transformed["meshes"][0]["primitives"][0]["attributes"]["_T6_NORMAL_TRANSFORM_0"]
        expect_error(write_doc(root, transformed, "missing_transform.gltf"), "normal transform attribute")

        wrong_count = document()
        wrong_count["extras"]["T6"]["generatedNormalBasisAttributesV2"]["stats"]["generatedPrimitiveCount"] = 2
        expect_error(write_doc(root, wrong_count, "count.gltf"), "generated primitive accounting")

        # Wrapper must patch v4 only for the v5 invocation and restore it even
        # after the downstream call returns.
        old_apply = v5.apply_preview
        old_builder = v4._build_material_v4
        output = root / "fixture.blend"
        observed = {"patched": False}
        def fake_apply(input_path, output_blend, *, recipes=None, strict=False):
            observed["patched"] = v4._build_material_v4 is v6._build_material_v6
            return {
                "output": str(output_blend),
                "generatedMaterialCount": 1,
                "rebuiltMaterialCount": 1,
                "skippedMaterialCount": 0,
                "heightDagCompiledLayerCount": 0,
                "rebuilt": [{"normalPlayback": True, "normalLayerCount": 1}],
            }
        try:
            v5.apply_preview = fake_apply
            result = v6.apply_preview(path, output, strict=True)
        finally:
            v5.apply_preview = old_apply
        assert observed["patched"] is True
        assert v4._build_material_v4 is old_builder
        assert result["format"] == "t6-blender-generated-layer-preview-v6"
        assert result["normalPlaybackMaterialCount"] == 1
        assert result["normalPlaybackLayerCount"] == 1
        assert result["normalBasisAttributeContractSha256"] == "a" * 64
        report = json.loads(output.with_suffix(".blend.t6_preview.json").read_text(encoding="utf-8"))
        assert report["normalPlaybackMaterialCount"] == 1

    print("PASS: Blender generated-layer preview v6 production trust boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
