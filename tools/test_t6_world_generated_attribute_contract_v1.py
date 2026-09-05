#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib

import t6_world_generated_attribute_contract_v1 as contract


def _fixture():
    # Deliberately leave a one-byte tail after the source transform payload so
    # appending the logical accessor must add alignment padding.
    raw = b"HEAD" + bytes((10, 20, 30, 40, 50, 60, 70, 80)) + b"X"
    view = {
        "buffer": 0,
        "byteOffset": 4,
        "byteLength": 8,
        "target": 34962,
        "name": "raw-transform",
    }
    accessors = [
        {
            "bufferView": 0,
            "componentType": 5121,
            "count": 2,
            "type": "VEC4",
            "normalized": False,
            "name": "raw-transform",
        },
    ]
    # Other attribute accessor indices are provenance-only for this pure postpass
    # fixture. Duplicate lightweight accessor descriptors keep all refs in range.
    for i in range(1, 6):
        accessors.append({
            "bufferView": 0,
            "componentType": 5121,
            "count": 2,
            "type": "VEC4",
            "normalized": False,
            "name": f"dummy-{i}",
        })

    attrs = {
        "POSITION": 5,
        "NORMAL": 5,
        "TANGENT": 5,
        "COLOR_0": 4,
        "TEXCOORD_0": 1,  # uv0
        "TEXCOORD_1": 2,  # uv1
        "TEXCOORD_2": 3,  # legacy dynamic lightmap slot
        "_T6_NORMAL_TRANSFORM_0": 0,
    }
    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(raw)}],
        "bufferViews": [view],
        "accessors": accessors,
        "materials": [
            {"name": "*generated(base:layer)"},
            {"name": "ordinary/wall"},
        ],
        "meshes": [{
            "name": "shared-world-group",
            "extras": {"T6": {
                "uvCount": 2,
                "lightmapTexCoord": 2,
                "texCoordMapping": {
                    "TEXCOORD_0": "uv0",
                    "TEXCOORD_1": "uv1",
                    "TEXCOORD_2": "lightmapUV",
                },
            }},
            "primitives": [
                {"attributes": dict(attrs), "material": 0},
                {"attributes": dict(attrs), "material": 1},
            ],
        }],
        "extras": {"T6": {}},
    }
    return doc, raw


def main() -> int:
    doc, raw = _fixture()
    original_doc = copy.deepcopy(doc)
    original_raw = bytes(raw)

    out, out_raw, stats = contract.normalize_generated_attributes(doc, raw)
    assert out is doc
    assert out_raw[:len(original_raw)] == original_raw
    assert stats["meshCount"] == 1
    assert stats["primitiveCount"] == 2
    assert stats["generatedPrimitiveCount"] == 1
    assert stats["ordinaryPrimitiveCount"] == 1
    assert stats["generatedColorRetypeCount"] == 1
    assert stats["texcoordNormalizedPrimitiveCount"] == 2
    assert stats["logicalNormalTransformAccessorCount"] == 1
    assert stats["normalTransformPrimitiveBindingCount"] == 2
    assert stats["originalAccessorCount"] == 6
    assert stats["finalAccessorCount"] == 7
    assert stats["originalBufferViewCount"] == 1
    assert stats["finalBufferViewCount"] == 2
    assert stats["originalRawBytes"] == 13
    assert stats["finalRawBytes"] == 24  # 13 -> align16 + 8 logical bytes
    assert out["buffers"][0]["byteLength"] == 24

    generated = out["meshes"][0]["primitives"][0]["attributes"]
    ordinary = out["meshes"][0]["primitives"][1]["attributes"]

    # Fixed renderer UV contract: native uv0, lightmap, native uv1.
    assert generated["TEXCOORD_0"] == 1
    assert generated["TEXCOORD_1"] == 3
    assert generated["TEXCOORD_2"] == 2
    assert ordinary["TEXCOORD_0"] == 1
    assert ordinary["TEXCOORD_1"] == 3
    assert ordinary["TEXCOORD_2"] == 2

    # The same source COLOR accessor is retyped only for generated material use.
    assert generated["_T6_LAYER_WEIGHTS"] == 4
    assert "COLOR_0" not in generated
    assert ordinary["COLOR_0"] == 4
    assert "_T6_LAYER_WEIGHTS" not in ordinary

    # Both primitives share one newly appended logical transform accessor.
    logical_index = generated["_T6_NORMAL_TRANSFORM_0"]
    assert logical_index == ordinary["_T6_NORMAL_TRANSFORM_0"] == 6
    assert generated["_T6_NORMAL_TRANSFORM_0_RAW"] == 0
    assert ordinary["_T6_NORMAL_TRANSFORM_0_RAW"] == 0
    logical_accessor = out["accessors"][logical_index]
    assert logical_accessor["componentType"] == 5121
    assert logical_accessor["type"] == "VEC4"
    assert logical_accessor["normalized"] is True
    logical_view = out["bufferViews"][logical_accessor["bufferView"]]
    assert logical_view["byteOffset"] == 16
    assert logical_view["byteLength"] == 8
    assert out_raw[16:24] == bytes((10, 30, 40, 20, 50, 70, 80, 60))

    # Original source accessor/view and source payload remain unchanged.
    assert out["accessors"][0] == original_doc["accessors"][0]
    assert out["bufferViews"][0] == original_doc["bufferViews"][0]
    assert hashlib.sha256(out_raw[:13]).hexdigest() == hashlib.sha256(original_raw).hexdigest()

    mesh_t6 = out["meshes"][0]["extras"]["T6"]
    assert mesh_t6["lightmapTexCoord"] == 1
    assert mesh_t6["texCoordMapping"] == {
        "TEXCOORD_0": "materialUV0",
        "TEXCOORD_1": "lightmapUV",
        "TEXCOORD_2": "materialUV1",
    }
    root = out["extras"]["T6"]["generatedAttributeContract"]
    assert root["format"] == contract.FORMAT
    assert root["stats"] == stats
    assert len(root["normalTransformConversions"]) == 1
    assert root["normalTransformConversions"][0]["sourceAccessor"] == 0
    assert root["normalTransformConversions"][0]["logicalAccessor"] == 6
    assert len(root["contractSha256"]) == 64

    # Running the postpass twice is an ambiguity, not an idempotent rewrite.
    try:
        contract.normalize_generated_attributes(out, out_raw)
    except contract.GeneratedAttributeContractError as exc:
        assert "already normalized" in str(exc)
    else:
        raise AssertionError("second generated-attribute normalization was accepted")

    # A generated primitive without source COLOR cannot silently receive weights.
    bad, bad_raw = _fixture()
    del bad["meshes"][0]["primitives"][0]["attributes"]["COLOR_0"]
    try:
        contract.normalize_generated_attributes(bad, bad_raw)
    except contract.GeneratedAttributeContractError as exc:
        assert "lacks legacy COLOR_0" in str(exc)
    else:
        raise AssertionError("generated material without exact source layer controls was accepted")

    print("PASS: production T6 generated-world attribute contract v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
