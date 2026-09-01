#!/usr/bin/env python3
"""Synthetic regression for t6_world_gltf_export_v1.

This is a format/serializer regression, not retail byte proof.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import struct

from t6_world_gltf_export_v1 import (
    Builder,
    ExportError,
    export,
    glb_bytes,
    gltf_bytes,
    validate,
)


def _attributes(count: int, group: int, uv_count: int, normal_count: int) -> dict:
    attrs = {
        "position": [[float(group), float(i), 10.0 + i] for i in range(count)],
        "binormalSign": [1.0 if i % 2 == 0 else -1.0 for i in range(count)],
        "colorRGBA8": [
            [20 + group, 30 + i, 40 + group + i, 255] for i in range(count)
        ],
        "color": [
            [
                (20 + group) / 255.0,
                (30 + i) / 255.0,
                (40 + group + i) / 255.0,
                1.0,
            ]
            for i in range(count)
        ],
        "uv0": [[i / 8.0, group / 8.0] for i in range(count)],
        "normal": [[0.0, 0.0, 1.0] for _ in range(count)],
        "normalPacked": [0x1FF00000 for _ in range(count)],
        "tangent": [[1.0, 0.0, 0.0] for _ in range(count)],
        "tangentPacked": [0x000001FF for _ in range(count)],
        "lightmapUV": [[i / 65535.0, group / 65535.0] for i in range(count)],
        "lightmapUVRaw": [[i, group] for i in range(count)],
    }
    for uv_index in range(1, uv_count):
        attrs[f"uv{uv_index}"] = [
            [i + uv_index / 10.0, group + uv_index / 10.0]
            for i in range(count)
        ]
    if normal_count >= 2:
        attrs["normalTransform0Packed"] = [
            0xA0000000 + i for i in range(count)
        ]
    if normal_count >= 3:
        attrs["normalTransform1Packed"] = [
            0xB0000000 + i for i in range(count)
        ]
    return attrs


def _world() -> dict:
    groups = [
        {
            "groupIndex": 0,
            "vd0Offset": 0,
            "vd1Offset": 0,
            "vertexCount": 4,
            "worldVertFormat": 0,
            "formatName": "TEX_1_NRM_1",
            "uvCount": 1,
            "normalCount": 1,
            "vd1Stride": 0,
            "vd1Fields": [],
            "firstVertex": 9,
            "surfaceIndices": [0, 1],
            "attributes": _attributes(4, 0, 1, 1),
        },
        {
            "groupIndex": 1,
            "vd0Offset": 144,
            "vd1Offset": 0,
            "vertexCount": 5,
            "worldVertFormat": 3,
            "formatName": "TEX_3_NRM_1",
            "uvCount": 3,
            "normalCount": 1,
            "vd1Stride": 8,
            "vd1Fields": ["uv1", "uv2"],
            "firstVertex": 0,
            "surfaceIndices": [2],
            "attributes": _attributes(5, 1, 3, 1),
        },
        {
            "groupIndex": 2,
            "vd0Offset": 324,
            "vd1Offset": 40,
            "vertexCount": 4,
            "worldVertFormat": 8,
            "formatName": "TEX_4_NRM_3",
            "uvCount": 4,
            "normalCount": 3,
            "vd1Stride": 20,
            "vd1Fields": [
                "uv1",
                "uv2",
                "uv3",
                "normalTransform0",
                "normalTransform1",
            ],
            "firstVertex": 5,
            "surfaceIndices": [3],
            "attributes": _attributes(4, 2, 4, 3),
        },
    ]
    surfaces = [
        {
            "index": 0,
            "groupIndex": 0,
            "baseIndex": 0,
            "triCount": 1,
            "firstVertex": 9,
            "storedVertexCount": 4,
            "indices": [0, 1, 2],
            "material": "synthetic/mat_a",
            "materialIndex": 0,
            "materialPointerRaw": "0x10000000",
            "lightmapIndex": 0,
            "reflectionProbeIndex": 10,
            "primaryLightIndex": 20,
            "flags": 16,
            "bounds": None,
        },
        {
            "index": 1,
            "groupIndex": 0,
            "baseIndex": 3,
            "triCount": 1,
            "firstVertex": 9,
            "storedVertexCount": 0,
            "indices": [0, 2, 3],
            "material": "synthetic/mat_b",
            "materialIndex": 1,
            "materialPointerRaw": "0x10000001",
            "lightmapIndex": 1,
            "reflectionProbeIndex": 11,
            "primaryLightIndex": 21,
            "flags": 16,
            "bounds": None,
        },
        {
            "index": 2,
            "groupIndex": 1,
            "baseIndex": 8,
            "triCount": 2,
            "firstVertex": 0,
            "storedVertexCount": 5,
            "indices": [0, 1, 2, 2, 3, 4],
            "material": "synthetic/mat_c",
            "materialIndex": 2,
            "materialPointerRaw": "0x10000002",
            "lightmapIndex": 0,
            "reflectionProbeIndex": 12,
            "primaryLightIndex": 22,
            "flags": 16,
            "bounds": None,
        },
        {
            "index": 3,
            "groupIndex": 2,
            "baseIndex": 15,
            "triCount": 1,
            "firstVertex": 5,
            "storedVertexCount": 4,
            "indices": [0, 2, 3],
            "material": "synthetic/mat_d",
            "materialIndex": 3,
            "materialPointerRaw": "0x10000003",
            "lightmapIndex": 1,
            "reflectionProbeIndex": 13,
            "primaryLightIndex": 23,
            "flags": 16,
            "bounds": None,
        },
    ]
    return {
        "format": "t6-world-mesh-normalized-v1",
        "map": "synthetic_world_gltf",
        "normalTransformPolicy": "preserve packed until source-closed",
        "stats": {
            "surfaceCount": 4,
            "vertexGroupCount": 3,
            "serializedVertexCount": 13,
            "triangleCount": 5,
        },
        "groups": groups,
        "surfaces": surfaces,
    }


def _decode_accessor(gltf: dict, raw: bytes, accessor_index: int) -> list:
    accessor = gltf["accessors"][accessor_index]
    view = gltf["bufferViews"][accessor["bufferView"]]
    offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    count = int(accessor["count"])
    component = int(accessor["componentType"])
    accessor_type = accessor["type"]
    component_format = {5121: "B", 5123: "H", 5125: "I", 5126: "f"}[
        component
    ]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[
        accessor_type
    ]
    values = struct.unpack_from(
        "<" + component_format * count * width,
        raw,
        offset,
    )
    if width == 1:
        return list(values)
    return [
        list(values[i * width : (i + 1) * width]) for i in range(count)
    ]


def main() -> int:
    world = _world()
    gltf, raw = export(world)
    assert validate(gltf, raw)

    stats = gltf["extras"]["T6"]["exportStats"]
    assert stats["groupCount"] == 3
    assert stats["primitiveCount"] == 4
    assert stats["materialCount"] == 4
    assert stats["vertexCount"] == 13
    assert stats["triangleCount"] == 5
    assert stats["boundsMeters"]["min"] == [0.0, 0.254, -0.1016]
    assert stats["boundsMeters"]["max"] == [
        0.0508,
        0.35559999999999997,
        -0.0,
    ]

    assert len(gltf["meshes"]) == 3
    assert len(gltf["nodes"]) == 3
    assert len(gltf["meshes"][0]["primitives"]) == 2

    # Surfaces sharing one T6 vertex group share the same standard/custom
    # attribute accessors instead of duplicating vertices per primitive.
    primitive0 = gltf["meshes"][0]["primitives"][0]
    primitive1 = gltf["meshes"][0]["primitives"][1]
    assert primitive0["attributes"] == primitive1["attributes"]

    # T6 Z-up inches -> glTF Y-up meters, determinant +1.
    positions = _decode_accessor(
        gltf,
        raw,
        primitive0["attributes"]["POSITION"],
    )
    normals = _decode_accessor(
        gltf,
        raw,
        primitive0["attributes"]["NORMAL"],
    )
    tangents = _decode_accessor(
        gltf,
        raw,
        primitive0["attributes"]["TANGENT"],
    )
    assert positions[0] == [0.0, 0.2540000081062317, -0.0]
    assert normals[0] == [0.0, 1.0, -0.0]
    assert tangents[0] == [1.0, 0.0, -0.0, 1.0]
    assert tangents[1][3] == -1.0

    # Native UVs are consecutive and lightmapUV follows the native T6 sets.
    expected_texcoord_sets = [
        ["TEXCOORD_0", "TEXCOORD_1"],
        ["TEXCOORD_0", "TEXCOORD_1", "TEXCOORD_2", "TEXCOORD_3"],
        [
            "TEXCOORD_0",
            "TEXCOORD_1",
            "TEXCOORD_2",
            "TEXCOORD_3",
            "TEXCOORD_4",
        ],
    ]
    for mesh, expected in zip(gltf["meshes"], expected_texcoord_sets):
        actual = sorted(
            (
                key
                for key in mesh["primitives"][0]["attributes"]
                if key.startswith("TEXCOORD_")
            ),
            key=lambda key: int(key.split("_")[1]),
        )
        assert actual == expected
    assert gltf["meshes"][0]["extras"]["T6"]["lightmapTexCoord"] == 1
    assert gltf["meshes"][1]["extras"]["T6"]["lightmapTexCoord"] == 3
    assert gltf["meshes"][2]["extras"]["T6"]["lightmapTexCoord"] == 4

    # Packed T6 provenance survives as legal application-specific attributes.
    attributes2 = gltf["meshes"][2]["primitives"][0]["attributes"]
    assert "_T6_NORMAL_PACKED" in attributes2
    assert "_T6_TANGENT_PACKED" in attributes2
    assert "_T6_LIGHTMAP_UV_RAW" in attributes2
    assert "_T6_NORMAL_TRANSFORM_0" in attributes2
    assert "_T6_NORMAL_TRANSFORM_1" in attributes2

    # Original surface metadata remains attached to each primitive.
    assert primitive1["extras"]["T6"]["baseIndex"] == 3
    assert primitive1["extras"]["T6"]["firstVertex"] == 9
    assert primitive1["extras"]["T6"]["storedVertexCount"] == 0
    assert primitive1["extras"]["T6"]["lightmapIndex"] == 1

    # GLB serialization is deterministic and chunk-valid.
    blob1 = glb_bytes(gltf, raw)
    blob2 = glb_bytes(*export(copy.deepcopy(world)))
    assert blob1 == blob2
    magic, version, total_length = struct.unpack_from("<4sII", blob1, 0)
    assert magic == b"glTF"
    assert version == 2
    assert total_length == len(blob1)
    json_length, json_type = struct.unpack_from("<II", blob1, 12)
    assert json_type == 0x4E4F534A
    json_doc = json.loads(
        blob1[20 : 20 + json_length].decode("utf-8").rstrip(" ")
    )
    assert json_doc["buffers"][0]["byteLength"] == len(raw)
    bin_header = 20 + json_length
    bin_length, bin_type = struct.unpack_from("<II", blob1, bin_header)
    assert bin_type == 0x004E4942
    assert bin_length >= len(raw)
    assert blob1[bin_header + 8 : bin_header + 8 + len(raw)] == raw

    # Embedded .gltf serialization contains byte-identical binary payload.
    text_blob = gltf_bytes(gltf, raw)
    text_doc = json.loads(text_blob.decode("utf-8"))
    uri = text_doc["buffers"][0]["uri"]
    prefix = "data:application/octet-stream;base64,"
    assert uri.startswith(prefix)
    assert base64.b64decode(uri[len(prefix) :]) == raw

    # A source 0xffff index is promoted to uint32 because glTF forbids using
    # the maximum value of an index component type.
    builder = Builder()
    accessor_index = builder.indices([0, 65535, 1], "promoted")
    assert builder.accessors[accessor_index]["componentType"] == 5125
    assert builder.accessors[accessor_index]["max"] == [65535]

    # Validation must reject a nonconsecutive TEXCOORD set.
    broken = copy.deepcopy(gltf)
    del broken["meshes"][2]["primitives"][0]["attributes"]["TEXCOORD_1"]
    try:
        validate(broken, raw)
    except ExportError as exc:
        assert "nonconsecutive TEXCOORD" in str(exc)
    else:
        raise AssertionError("nonconsecutive TEXCOORD sets were not rejected")

    print("PASS t6_world_gltf_export_v1 synthetic regression")
    print(json.dumps(stats, indent=2, sort_keys=True))
    print("glbSha256=" + hashlib.sha256(blob1).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
