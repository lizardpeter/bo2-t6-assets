#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v20 as pipeline
from t6_glb_parse_v1 import parse_glb
from t6_world_gltf_export_v1 import glb_bytes


def _record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def fixture_document() -> tuple[dict, bytes]:
    normals = [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0)]
    tangents = [(1.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, -1.0)]
    normal_bytes = struct.pack("<6f", *(v for row in normals for v in row))
    tangent_bytes = struct.pack("<8f", *(v for row in tangents for v in row))
    raw = normal_bytes + tangent_bytes
    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(raw)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(normal_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(normal_bytes), "byteLength": len(tangent_bytes), "target": 34962},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 2, "type": "VEC3"},
            {"bufferView": 1, "componentType": 5126, "count": 2, "type": "VEC4"},
        ],
        "materials": [{"name": "*fixture"}],
        "meshes": [{
            "primitives": [{
                "material": 0,
                "attributes": {
                    "NORMAL": 0,
                    "TANGENT": 1,
                    "_T6_LAYER_WEIGHTS": 0,
                    "_T6_WORLD_NORMAL": 0,
                    "_T6_WORLD_TANGENT": 2,
                    "_T6_TANGENT_HANDEDNESS": 3,
                },
            }]
        }],
        "extras": {"T6": {
            "generatedAttributeContract": {
                "format": "t6-world-generated-attribute-contract-v1",
                "stats": {"generatedPrimitiveCount": 1, "generatedColorRetypeCount": 1},
            },
            "generatedNormalBasisAttributes": {
                "format": "t6-generated-normal-basis-attributes-v1",
                "stats": {"generatedPrimitiveCount": 1},
                "contractSha256": "a" * 64,
            },
        }},
    }
    # v19 has already added zero-copy tangent aliases. Reproduce their metadata
    # here without changing the source bytes.
    alias_view = len(doc["bufferViews"])
    doc["bufferViews"].append({
        "buffer": 0,
        "byteOffset": len(normal_bytes),
        "byteLength": len(tangent_bytes),
        "byteStride": 16,
        "target": 34962,
    })
    tangent_alias = len(doc["accessors"])
    doc["accessors"].append({
        "bufferView": alias_view,
        "componentType": 5126,
        "count": 2,
        "type": "VEC3",
        "byteOffset": 0,
    })
    hand_alias = len(doc["accessors"])
    doc["accessors"].append({
        "bufferView": alias_view,
        "componentType": 5126,
        "count": 2,
        "type": "SCALAR",
        "byteOffset": 12,
    })
    attrs = doc["meshes"][0]["primitives"][0]["attributes"]
    attrs["_T6_WORLD_TANGENT"] = tangent_alias
    attrs["_T6_TANGENT_HANDEDNESS"] = hand_alias
    return doc, raw


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_v20_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        doc, source_raw = fixture_document()
        old_glb = out / "fixture.world_oat_portable_textured_v19.glb"
        old_glb.write_bytes(glb_bytes(doc, source_raw))
        old_manifest = out / "fixture_v19.json"
        old_manifest.write_text("{}\n", encoding="utf-8")

        original = pipeline.v19.run_oat_textured_pipeline
        try:
            pipeline.v19.run_oat_textured_pipeline = lambda **kwargs: {
                "format": "t6-oat-world-textured-export-pipeline-manifest-v19",
                "map": "fixture",
                "outputs": {"oatPortableTexturedGlb": _record(old_glb)},
                "inputs": {},
                "stats": {},
                "validation": {"v19GeneratedNormalBasisBinByteIdentical": True},
                "policies": {"v19Sentinel": "preserved"},
                "manifest": _record(old_manifest),
            }
            result = pipeline.run_oat_textured_pipeline(
                map_name="fixture",
                output_dir=out,
            )
        finally:
            pipeline.v19.run_oat_textured_pipeline = original

        assert result["format"] == pipeline.FORMAT
        assert result["validation"]["v19GeneratedNormalBasisBinByteIdentical"] is True
        assert result["validation"]["v20GeneratedNormalBasisV2Attached"] is True
        assert result["validation"]["v20V19BinExactPrefix"] is True
        assert result["validation"]["v20DerivedBinormalAccessorCount"] == 1
        assert result["validation"]["v20DerivedBinormalVertexCount"] == 2
        assert result["policies"]["v19Sentinel"] == "preserved"

        final_glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        assert final_glb.name.endswith("_v20.glb")
        final_doc, final_raw = parse_glb(final_glb.read_bytes())
        assert final_raw[:len(source_raw)] == source_raw
        assert len(final_raw) - len(source_raw) == 24
        attrs = final_doc["meshes"][0]["primitives"][0]["attributes"]
        binormal_accessor = final_doc["accessors"][attrs["_T6_WORLD_BINORMAL"]]
        view = final_doc["bufferViews"][binormal_accessor["bufferView"]]
        assert view["byteOffset"] == len(source_raw)
        assert view["byteLength"] == 24
        b0 = struct.unpack_from("<3f", final_raw, view["byteOffset"])
        b1 = struct.unpack_from("<3f", final_raw, view["byteOffset"] + 12)
        assert b0 == (0.0, 1.0, 0.0), b0
        assert b1 == (-1.0, -0.0, -0.0), b1
        root_contract = final_doc["extras"]["T6"]["generatedNormalBasisAttributesV2"]
        assert root_contract["format"] == "t6-generated-normal-basis-attributes-v2"
        assert root_contract["stats"]["sourceBinBytes"] == len(source_raw)
        assert root_contract["stats"]["appendedBinBytes"] == 24

        assert not old_glb.exists()
        assert not old_manifest.exists()
        persisted = json.loads(Path(result["manifest"]["path"]).read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT
        assert persisted["validation"]["v20V19BinExactPrefix"] is True
        assert persisted["stats"]["generatedNormalBasisAttributesV2"]["derivedBinormalVertexCount"] == 2

    print("PASS: production v20 vertex-stage binormal orchestration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
