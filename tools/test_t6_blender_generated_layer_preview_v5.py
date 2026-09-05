#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_blender_generated_layer_preview_v4 as v4
import t6_blender_generated_layer_preview_v5 as v5
import t6_blender_height_dag_nodes_v1 as height_nodes
from t6_world_generated_attribute_contract_v1 import FORMAT as ATTRIBUTE_FORMAT


def _recipe():
    shader = "a" * 64
    archive = "b" * 64
    return {
        "heightWeightDagsV1": {"pixelShaderSha256": shader},
        "heightConstantBindingsV1": {
            "dxbcSha256": shader,
            "materialArchiveSha256": archive,
        },
        "heightLeafBindingsV1": {
            "pixelShaderSha256": shader,
            "materialArchiveSha256": archive,
            "constantBindingsKey": height_nodes.HEIGHT_CONSTANT_KEY,
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_blender_v5_") as td:
        root = Path(td)
        good = root / "good.gltf"
        good.write_text(json.dumps({
            "asset": {"version": "2.0"},
            "extras": {"T6": {"generatedAttributeContract": {
                "format": ATTRIBUTE_FORMAT,
                "contractSha256": "c" * 64,
                "stats": {
                    "generatedPrimitiveCount": 7,
                    "generatedColorRetypeCount": 7,
                },
            }}},
        }), encoding="utf-8")
        contract = v5._root_attribute_preflight(good)
        assert contract["format"] == ATTRIBUTE_FORMAT
        assert contract["stats"]["generatedPrimitiveCount"] == 7

        legacy = root / "legacy.gltf"
        legacy.write_text(json.dumps({"asset": {"version": "2.0"}}), encoding="utf-8")
        try:
            v5._root_attribute_preflight(legacy)
        except v5.BlenderLayerPreviewError as exc:
            assert "lacks authoritative" in str(exc)
        else:
            raise AssertionError("legacy pre-v12 glTF was accepted")

        bad_accounting = root / "bad.gltf"
        bad_accounting.write_text(json.dumps({
            "asset": {"version": "2.0"},
            "extras": {"T6": {"generatedAttributeContract": {
                "format": ATTRIBUTE_FORMAT,
                "stats": {
                    "generatedPrimitiveCount": 7,
                    "generatedColorRetypeCount": 6,
                },
            }}},
        }), encoding="utf-8")
        try:
            v5._root_attribute_preflight(bad_accounting)
        except v5.BlenderLayerPreviewError as exc:
            assert "accounting mismatch" in str(exc)
        else:
            raise AssertionError("incomplete generated layer-weight retyping was accepted")

    # Isolate the stricter cross-contract checks from v4's already-tested DAG
    # structure validator; the captured base hook must be called exactly once.
    old_base = v5._BASE_HEIGHT_PREFLIGHT
    calls = []
    try:
        def fake_base(material, technique, recipe, layer):
            calls.append((material, technique, layer))
            return "PLAN"
        v5._BASE_HEIGHT_PREFLIGHT = fake_base
        recipe = _recipe()
        assert v5._strict_height_identity_preflight("*fixture", "lit_sm_fixture", recipe, 1) == "PLAN"
        assert calls == [("*fixture", "lit_sm_fixture", 1)]

        wrong = _recipe()
        wrong[height_nodes.HEIGHT_CONSTANT_KEY]["dxbcSha256"] = "d" * 64
        try:
            v5._strict_height_identity_preflight("*fixture", "lit_sm_fixture", wrong, 1)
        except v5.BlenderLayerPreviewError as exc:
            assert "constant DXBC SHA disagrees" in str(exc)
        else:
            raise AssertionError("constant payload from another DXBC shader was accepted")

        wrong = _recipe()
        wrong[height_nodes.HEIGHT_LEAF_KEY]["pixelShaderSha256"] = "e" * 64
        try:
            v5._strict_height_identity_preflight("*fixture", "lit_sm_fixture", wrong, 1)
        except v5.BlenderLayerPreviewError as exc:
            assert "leaf-binding pixel-shader SHA disagrees" in str(exc)
        else:
            raise AssertionError("leaf payload from another shader was accepted")

        wrong = _recipe()
        wrong[height_nodes.HEIGHT_LEAF_KEY]["materialArchiveSha256"] = "f" * 64
        try:
            v5._strict_height_identity_preflight("*fixture", "lit_sm_fixture", wrong, 1)
        except v5.BlenderLayerPreviewError as exc:
            assert "Material archive identity disagrees" in str(exc)
        else:
            raise AssertionError("height leaves from another generated Material were accepted")
    finally:
        v5._BASE_HEIGHT_PREFLIGHT = old_base

    # apply_preview must patch v4 only for the duration of the call and restore
    # it even when invoked through the new production trust boundary.
    with tempfile.TemporaryDirectory(prefix="t6_blender_v5_apply_") as td:
        root = Path(td)
        inp = root / "fixture.gltf"
        out = root / "fixture.blend"
        inp.write_text(json.dumps({
            "asset": {"version": "2.0"},
            "extras": {"T6": {"generatedAttributeContract": {
                "format": ATTRIBUTE_FORMAT,
                "contractSha256": "1" * 64,
                "stats": {
                    "generatedPrimitiveCount": 1,
                    "generatedColorRetypeCount": 1,
                },
            }}},
        }), encoding="utf-8")
        old_apply = v4.apply_preview
        old_hook = v4._height_identity_preflight
        observed = {}
        try:
            def fake_apply(input_path, output_blend, *, recipes=None, strict=False):
                observed["hook"] = v4._height_identity_preflight
                return {
                    "output": str(output_blend),
                    "generatedMaterialCount": 1,
                    "rebuiltMaterialCount": 1,
                    "skippedMaterialCount": 0,
                    "heightDagCompiledLayerCount": 1,
                }
            v4.apply_preview = fake_apply
            result = v5.apply_preview(inp, out, strict=True)
        finally:
            v4.apply_preview = old_apply
        assert observed["hook"] is v5._strict_height_identity_preflight
        assert v4._height_identity_preflight is old_hook
        assert result["format"] == "t6-blender-generated-layer-preview-v5"
        assert result["attributeContract"] == ATTRIBUTE_FORMAT
        report = out.with_suffix(out.suffix + ".t6_preview.json")
        assert json.loads(report.read_text(encoding="utf-8"))["format"] == result["format"]

    print("PASS: Blender preview v5 production attribute and height identity gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
