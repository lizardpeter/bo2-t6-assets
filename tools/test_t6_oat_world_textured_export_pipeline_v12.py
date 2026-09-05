#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v12 as pipeline
from t6_world_generated_attribute_contract_v1 import FORMAT as ATTRIBUTE_FORMAT
from t6_world_gltf_export_v1 import glb_bytes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": _sha(data)}


def _base_document():
    # One stored-order transform row at offset 0. Other accessors are references
    # only; the semantic postpass intentionally does not rewrite their payloads.
    raw = bytes((10, 20, 30, 40))
    accessors = [{
        "bufferView": 0,
        "componentType": 5121,
        "count": 1,
        "type": "VEC4",
        "normalized": False,
    }]
    for _ in range(5):
        accessors.append({
            "bufferView": 0,
            "componentType": 5121,
            "count": 1,
            "type": "VEC4",
            "normalized": False,
        })
    attrs = {
        "POSITION": 5,
        "COLOR_0": 4,
        "TEXCOORD_0": 1,
        "TEXCOORD_1": 2,
        "TEXCOORD_2": 3,
        "_T6_NORMAL_TRANSFORM_0": 0,
    }
    doc = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "buffers": [{"byteLength": len(raw)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4, "target": 34962}],
        "accessors": accessors,
        "materials": [{"name": "*fixture(base:layer)", "extras": {"T6": {}}}],
        "meshes": [{
            "name": "group0",
            "extras": {"T6": {
                "uvCount": 2,
                "lightmapTexCoord": 2,
                "texCoordMapping": {
                    "TEXCOORD_0": "uv0",
                    "TEXCOORD_1": "uv1",
                    "TEXCOORD_2": "lightmapUV",
                },
            }},
            "primitives": [{"attributes": attrs, "material": 0, "mode": 4}],
        }],
        "extras": {"T6": {"sentinel": "v11-preserved"}},
    }
    return doc, raw


def main() -> int:
    doc, raw = _base_document()
    base_glb = glb_bytes(doc, raw)
    normalized, normalized_raw, stats = pipeline._normalize_once(base_glb)
    assert normalized_raw[:len(raw)] == raw
    assert normalized_raw[4:8] == bytes((10, 30, 40, 20))
    assert stats["generatedPrimitiveCount"] == 1
    assert stats["generatedColorRetypeCount"] == 1
    assert stats["logicalNormalTransformAccessorCount"] == 1
    attrs = normalized["meshes"][0]["primitives"][0]["attributes"]
    assert "COLOR_0" not in attrs
    assert attrs["_T6_LAYER_WEIGHTS"] == 4
    assert attrs["TEXCOORD_0"] == 1
    assert attrs["TEXCOORD_1"] == 3
    assert attrs["TEXCOORD_2"] == 2
    assert attrs["_T6_NORMAL_TRANSFORM_0_RAW"] == 0
    logical = normalized["accessors"][attrs["_T6_NORMAL_TRANSFORM_0"]]
    assert logical["normalized"] is True
    assert normalized["extras"]["T6"]["sentinel"] == "v11-preserved"
    assert normalized["extras"]["T6"]["generatedAttributeContract"]["format"] == ATTRIBUTE_FORMAT

    with tempfile.TemporaryDirectory(prefix="t6_v12_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        v11_glb = out / "mp_nuketown_2020.world_oat_portable_textured_v11.glb"
        v11_glb.write_bytes(base_glb)
        old_manifest = out / "mp_nuketown_2020.world_oat_textured_export_manifest_v11.json"
        old_manifest.write_text("{}\n", encoding="utf-8")

        original = pipeline.v11.run_oat_textured_pipeline
        calls = []
        try:
            def fake_v11(**kwargs):
                calls.append(kwargs)
                return {
                    "format": "t6-oat-world-textured-export-pipeline-manifest-v11",
                    "map": "mp_nuketown_2020",
                    "inputs": {"fixture": True},
                    "outputs": {"oatPortableTexturedGlb": _record(v11_glb)},
                    "stats": {"generatedShaderRecipeRecovery": {"format": "v4"}},
                    "validation": {"canonicalGeneratedShaderRecipesAttached": True},
                    "policies": {"v11Sentinel": "preserved"},
                    "manifest": _record(old_manifest),
                }
            pipeline.v11.run_oat_textured_pipeline = fake_v11
            result = pipeline.run_oat_textured_pipeline(
                map_name="mp_nuketown_2020",
                surfaces_path=root / "unused.surfaces",
                vd0_path=root / "unused.vd0",
                vd1_path=root / "unused.vd1",
                indices_path=root / "unused.indices",
                materials_path=root / "unused.materials",
                catalog_path=root / "unused.catalog",
                prefix_path=root / "unused.prefix",
                asset_pointer_array_virtual_base=0,
                oat_material_root=root / "unused_oat",
                dds_root=root / "unused_dds",
                output_dir=out,
                format_registry_path=root / "unused_registry",
            )
        finally:
            pipeline.v11.run_oat_textured_pipeline = original

        assert len(calls) == 1
        assert result["format"] == pipeline.FORMAT
        assert result["policies"]["v11Sentinel"] == "preserved"
        assert result["validation"]["canonicalGeneratedShaderRecipesAttached"] is True
        assert result["validation"]["v12GeneratedAttributeContract"] == ATTRIBUTE_FORMAT
        assert result["validation"]["v12GeneratedAttributeRegenerationByteIdentical"] is True
        assert result["validation"]["v12ExistingBinaryPrefixPreserved"] is True
        assert result["validation"]["v12GeneratedPrimitiveCount"] == 1
        assert result["validation"]["v12GeneratedLayerWeightRetypeCount"] == 1
        assert result["validation"]["v12LogicalNormalTransformAccessorCount"] == 1
        assert result["stats"]["generatedAttributeContract"]["generatedPrimitiveCount"] == 1
        final_glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        assert final_glb.name.endswith("_v12.glb")
        assert final_glb.is_file()
        assert not v11_glb.exists()
        assert not old_manifest.exists()
        final_manifest = Path(result["manifest"]["path"])
        assert final_manifest.name.endswith("_v12.json")
        persisted = json.loads(final_manifest.read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT

    print("PASS: production T6 OAT world textured pipeline v12 attribute promotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
