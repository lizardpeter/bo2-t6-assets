#!/usr/bin/env python3
"""Synthetic all-format end-to-end regression for the T6 world export pipeline.

This fixture intentionally exercises MaterialWorldVertexFormat 0..8 in one run.
It validates tool integration only; it does not upgrade formula-only formats to
retail proof.
"""
from __future__ import annotations

import base64
import hashlib
import json
import struct
import tempfile
from pathlib import Path

from t6_world_export_pipeline_v1 import run_pipeline
from t6_zone_core import (
    WORLD_VERTEX_FORMATS,
    MaterialWorldVertexFormat,
    pack_unit_vec_third_based,
)


def _write_json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _vd0_row(fmt: int, vertex: int) -> bytes:
    row = bytearray(36)
    struct.pack_into("<3f", row, 0, float(fmt), float(vertex), float(fmt + vertex + 1))
    struct.pack_into("<f", row, 12, -1.0 if vertex & 1 else 1.0)
    row[16:20] = bytes((20 + fmt, 40 + vertex, 60 + fmt, 255))
    struct.pack_into("<2e", row, 20, vertex / 4.0, fmt / 8.0)
    struct.pack_into(
        "<I",
        row,
        24,
        pack_unit_vec_third_based((0.0, 0.0, 1.0)),
    )
    struct.pack_into(
        "<I",
        row,
        28,
        pack_unit_vec_third_based((1.0, 0.0, 0.0)),
    )
    struct.pack_into("<HH", row, 32, vertex * 1000, fmt * 1000)
    return bytes(row)


def _vd1_row(fmt: int, vertex: int) -> bytes:
    spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(fmt)]
    out = bytearray()
    for field_index, field in enumerate(spec.vd1_fields):
        if field.startswith("uv"):
            out.extend(
                struct.pack(
                    "<2e",
                    float(vertex) + field_index / 10.0,
                    float(fmt) + field_index / 10.0,
                )
            )
        else:
            out.extend(
                struct.pack(
                    "<I",
                    0xA0000000
                    | (fmt << 12)
                    | (vertex << 4)
                    | field_index,
                )
            )
    assert len(out) == spec.vd1_stride
    return bytes(out)


def _build_fixture(root: Path) -> dict:
    pointer_base = 0x4000
    vertex_count_per_group = 4
    surface_count = 9

    surfaces = []
    vd0 = bytearray()
    vd1 = bytearray()
    indices: list[int] = []
    material_details = []
    catalog = []
    prefix = []

    # GPU firstVertex order is deliberately reversed relative to serialized
    # vd0 order, proving that the pipeline keeps the two coordinate systems
    # separate instead of assuming firstVertex == serialized group order.
    for fmt in range(9):
        spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(fmt)]
        off0 = len(vd0)
        off1 = len(vd1)
        first_vertex = (8 - fmt) * vertex_count_per_group
        material_name = f"synthetic/world_material_{fmt}"
        material_pointer = 0x10000000 + fmt * 0x100
        technique_asset_index = len(prefix)

        for vertex in range(vertex_count_per_group):
            vd0.extend(_vd0_row(fmt, vertex))
            vd1.extend(_vd1_row(fmt, vertex))

        base_index = len(indices)
        indices.extend([0, 1, 2, 0, 2, 3])
        surfaces.append(
            {
                "index": fmt,
                "vertexDataOffset0": off0,
                "vertexDataOffset1": off1,
                "firstVertex": first_vertex,
                "vertexCount": vertex_count_per_group,
                "triCount": 2,
                "baseIndex": base_index,
                "materialPointerRaw": f"0x{material_pointer:08x}",
                "lightmapIndex": fmt % 2,
                "reflectionProbeIndex": fmt + 10,
                "primaryLightIndex": fmt + 20,
                "flags": 16,
                "bounds": {
                    "midPoint": [float(fmt), 0.0, 0.0],
                    "halfSize": [1.0, 1.0, 1.0],
                },
            }
        )

        catalog.append(
            {
                "index": fmt,
                "surfacePointerHex": f"0x{material_pointer:08x}",
                "name": material_name,
            }
        )
        material_details.append(
            {
                "name": material_name,
                "techniqueSet": {
                    "pointer": {
                        "kind": "offset",
                        "block": 5,
                        "offset": pointer_base + 4 + 8 * technique_asset_index,
                    }
                },
            }
        )
        prefix.append(
            {
                "type": "techniqueset",
                "name": f"synthetic/world_techset_{fmt}",
                "details": {"worldVertFormat": fmt},
            }
        )

    surfaces_doc = {
        "name": "synthetic_world_all_formats",
        "vertexCount": surface_count * vertex_count_per_group,
        "surfaces": surfaces,
    }

    paths = {
        "surfaces": root / "surfaces.json",
        "vd0": root / "vd0.bin",
        "vd1": root / "vd1.bin",
        "indices": root / "indices.bin",
        "materials": root / "materials.json",
        "catalog": root / "catalog.json",
        "prefix": root / "prefix.json",
        "output": root / "out",
    }
    _write_json(paths["surfaces"], surfaces_doc)
    paths["vd0"].write_bytes(vd0)
    paths["vd1"].write_bytes(vd1)
    paths["indices"].write_bytes(
        struct.pack("<" + "H" * len(indices), *indices)
    )
    _write_json(paths["materials"], {"materials": material_details})
    _write_json(paths["catalog"], {"materials": catalog})
    _write_json(paths["prefix"], {"walkedAssets": prefix})
    paths["assetPointerBase"] = pointer_base
    paths["expectedVd0Bytes"] = len(vd0)
    paths["expectedVd1Bytes"] = len(vd1)
    return paths


def _parse_glb(path: Path) -> tuple[dict, bytes]:
    blob = path.read_bytes()
    magic, version, total_length = struct.unpack_from("<4sII", blob, 0)
    assert magic == b"glTF"
    assert version == 2
    assert total_length == len(blob)

    json_length, json_type = struct.unpack_from("<II", blob, 12)
    assert json_type == 0x4E4F534A
    document = json.loads(
        blob[20 : 20 + json_length].decode("utf-8").rstrip(" ")
    )
    bin_header = 20 + json_length
    bin_length, bin_type = struct.unpack_from("<II", blob, bin_header)
    assert bin_type == 0x004E4942
    raw = blob[bin_header + 8 : bin_header + 8 + bin_length]
    return document, raw


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        fixture = _build_fixture(root)
        manifest = run_pipeline(
            map_name="synthetic_world_all_formats",
            surfaces_path=fixture["surfaces"],
            vd0_path=fixture["vd0"],
            vd1_path=fixture["vd1"],
            indices_path=fixture["indices"],
            materials_path=fixture["materials"],
            catalog_path=fixture["catalog"],
            prefix_path=fixture["prefix"],
            asset_pointer_array_virtual_base=fixture["assetPointerBase"],
            output_dir=fixture["output"],
            write_gltf=True,
        )

        validation = manifest["validation"]
        assert validation["vertexAuditBadGroups"] == 0
        assert validation["observedWorldVertFormats"] == list(range(9))
        assert validation["allSurfaceMaterialsResolved"] is True
        assert validation["unresolvedSurfaceMaterials"] == 0
        assert validation["glbRegenerationByteIdentical"] is True
        assert validation["gltfRegenerationByteIdentical"] is True

        audit_stats = manifest["stats"]["vertexAudit"]
        assert audit_stats["surfaceCount"] == 9
        assert audit_stats["uniqueVertexGroups"] == 9
        assert audit_stats["vd0Bytes"] == fixture["expectedVd0Bytes"]
        assert audit_stats["vd1Bytes"] == fixture["expectedVd1Bytes"]
        assert audit_stats["observedFormatGroupCounts"] == {
            str(fmt): 1 for fmt in range(9)
        }

        material_stats = manifest["stats"]["materialResolution"]
        assert material_stats["resolvedSurfaceCount"] == 9
        assert material_stats["unresolvedSurfaceCount"] == 0

        normalized_stats = manifest["stats"]["normalizedWorld"]
        assert normalized_stats["surfaceCount"] == 9
        assert normalized_stats["vertexGroupCount"] == 9
        assert normalized_stats["serializedVertexCount"] == 36
        assert normalized_stats["topVertexCount"] == 36
        assert normalized_stats["triangleCount"] == 18
        assert normalized_stats["worldVertFormatGroupCounts"] == {
            str(fmt): 1 for fmt in range(9)
        }

        gltf_stats = manifest["stats"]["gltf"]
        assert gltf_stats["groupCount"] == 9
        assert gltf_stats["primitiveCount"] == 9
        assert gltf_stats["materialCount"] == 9
        assert gltf_stats["vertexCount"] == 36
        assert gltf_stats["triangleCount"] == 18

        # Every recorded output hash must match the file actually written.
        for record in manifest["outputs"].values():
            path = Path(record["path"])
            payload = path.read_bytes()
            assert len(payload) == record["bytes"]
            assert hashlib.sha256(payload).hexdigest() == record["sha256"]

        glb_path = Path(manifest["outputs"]["glb"]["path"])
        gltf_doc, raw = _parse_glb(glb_path)
        assert len(gltf_doc["meshes"]) == 9
        assert len(gltf_doc["materials"]) == 9
        assert [material["name"] for material in gltf_doc["materials"]] == [
            f"synthetic/world_material_{fmt}" for fmt in range(9)
        ]

        expected_uv_counts = [1, 2, 2, 3, 3, 3, 4, 4, 4]
        for fmt, (mesh, uv_count) in enumerate(
            zip(gltf_doc["meshes"], expected_uv_counts)
        ):
            primitive = mesh["primitives"][0]
            texcoords = sorted(
                int(key.split("_")[1])
                for key in primitive["attributes"]
                if key.startswith("TEXCOORD_")
            )
            assert texcoords == list(range(uv_count + 1))
            assert mesh["extras"]["T6"]["lightmapTexCoord"] == uv_count
            assert mesh["extras"]["T6"]["worldVertFormat"] == fmt

        fmt8_attrs = gltf_doc["meshes"][8]["primitives"][0]["attributes"]
        assert "_T6_NORMAL_TRANSFORM_0" in fmt8_attrs
        assert "_T6_NORMAL_TRANSFORM_1" in fmt8_attrs

        # Embedded glTF carries the exact same binary buffer as the GLB.
        gltf_path = Path(manifest["outputs"]["gltf"]["path"])
        embedded = json.loads(gltf_path.read_text(encoding="utf-8"))
        uri = embedded["buffers"][0]["uri"]
        prefix = "data:application/octet-stream;base64,"
        assert uri.startswith(prefix)
        embedded_raw = base64.b64decode(uri[len(prefix) :])
        assert embedded_raw == raw[: len(embedded_raw)]

        print("PASS t6_world_export_pipeline_v1 synthetic all-format regression")
        print(json.dumps(validation, indent=2, sort_keys=True))
        print("glbSha256=" + manifest["outputs"]["glb"]["sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
