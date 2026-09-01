#!/usr/bin/env python3
"""Synthetic end-to-end regression for t6_world_mesh_normalize_v1.

This is deliberately not retail proof. It locks the normalized archive contract:
- serialized vertex-group order may differ from original GPU firstVertex order;
- multiple surfaces may share one group and later records may store vertexCount=0;
- surface index slices remain local to the group;
- UV1/UV2/UV3 and packed normal-transform words survive normalization;
- unused positions in the global uint16 index buffer are accounted for.
"""
from __future__ import annotations

import copy
import json
import struct

from t6_world_mesh_normalize_v1 import NormalizeError, normalize
from t6_zone_core import WORLD_VERTEX_FORMATS, MaterialWorldVertexFormat, pack_unit_vec_third_based


def _vd0_row(x: float, y: float, z: float, vi: int, group: int) -> bytes:
    row = bytearray(36)
    struct.pack_into("<3f", row, 0, x, y, z)
    struct.pack_into("<f", row, 12, -1.0 if vi & 1 else 1.0)
    row[16:20] = bytes((20 + group, 30 + vi, 40 + group + vi, 255))
    struct.pack_into("<2e", row, 20, vi / 8.0, group / 8.0)
    struct.pack_into("<I", row, 24, pack_unit_vec_third_based((0.0, 0.0, 1.0)))
    struct.pack_into("<I", row, 28, pack_unit_vec_third_based((1.0, 0.0, 0.0)))
    struct.pack_into("<HH", row, 32, vi * 1000, group * 1000)
    return bytes(row)


def _vd1_row(fmt: int, vi: int, group: int) -> bytes:
    spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(fmt)]
    out = bytearray()
    for fi, field in enumerate(spec.vd1_fields):
        if field.startswith("uv"):
            out.extend(struct.pack("<2e", vi + fi / 10.0, group + fi / 10.0))
        else:
            out.extend(struct.pack("<I", 0xA0000000 | (fmt << 12) | (group << 8) | (vi << 2) | fi))
    assert len(out) == spec.vd1_stride
    return bytes(out)


def _fixture() -> tuple[dict, bytes, bytes, bytes, dict]:
    # Serialized order is intentionally different from GPU firstVertex order:
    # group0 -> GPU 9..12, group1 -> GPU 0..4, group2 -> GPU 5..8.
    groups = [
        {"groupIndex": 0, "fmt": 0, "count": 4, "firstVertex": 9, "surfaces": [0, 1]},
        {"groupIndex": 1, "fmt": 3, "count": 5, "firstVertex": 0, "surfaces": [2]},
        {"groupIndex": 2, "fmt": 8, "count": 4, "firstVertex": 5, "surfaces": [3]},
    ]

    vd0 = bytearray()
    vd1 = bytearray()
    proof_groups = []
    group_offsets = {}
    for group in groups:
        off0 = len(vd0)
        off1 = len(vd1)
        for vi in range(group["count"]):
            vd0.extend(_vd0_row(float(group["groupIndex"]), float(vi), 10.0 + vi, vi, group["groupIndex"]))
            vd1.extend(_vd1_row(group["fmt"], vi, group["groupIndex"]))
        group_offsets[group["groupIndex"]] = (off0, off1)
        proof_groups.append(
            {
                "groupIndex": group["groupIndex"],
                "vd0Offset": off0,
                "vd1Offset": off1,
                "vertexCount": group["count"],
                "worldVertFormat": group["fmt"],
                "surfaceIndices": group["surfaces"],
            }
        )

    # Three intentionally-unused positions (6,7,14) prove accounting is based
    # on surface baseIndex/triCount slices, not merely buffer length.
    index_values = [
        0, 1, 2,          # surface 0
        0, 2, 3,          # surface 1
        65535, 65535,     # unused
        0, 1, 2, 2, 3, 4,# surface 2
        65535,             # unused
        0, 2, 3,          # surface 3
    ]
    indices = struct.pack("<" + "H" * len(index_values), *index_values)

    def surf(index: int, group: int, base: int, tris: int, stored_count: int, material: str) -> dict:
        off0, off1 = group_offsets[group]
        first = groups[group]["firstVertex"]
        return {
            "index": index,
            "vertexDataOffset0": off0,
            "vertexDataOffset1": off1,
            "firstVertex": first,
            "vertexCount": stored_count,
            "triCount": tris,
            "baseIndex": base,
            "material": material,
            "materialIndex": index,
            "materialPointerRaw": f"0x{0x10000000 + index:08x}",
            "lightmapIndex": index % 2,
            "reflectionProbeIndex": index + 10,
            "primaryLightIndex": index + 20,
            "flags": 16,
            "bounds": {"midPoint": [index, 0.0, 0.0], "halfSize": [1.0, 1.0, 1.0]},
        }

    surfaces_doc = {
        "name": "synthetic_world_normalizer",
        "vertexCount": 13,
        "surfaces": [
            surf(0, 0, 0, 1, 4, "synthetic/mat0"),
            surf(1, 0, 3, 1, 0, "synthetic/mat1"),
            surf(2, 1, 8, 2, 5, "synthetic/mat2"),
            surf(3, 2, 15, 1, 4, "synthetic/mat3"),
        ],
    }
    proof = {
        "format": "t6-world-vertex-proof-v1",
        "map": "synthetic_world_normalizer",
        "surfaceCount": 4,
        "uniqueVertexGroups": 3,
        "vd0Bytes": len(vd0),
        "vd1Bytes": len(vd1),
        "badGroupCount": 0,
        "badGroups": [],
        "groups": proof_groups,
    }
    return surfaces_doc, bytes(vd0), bytes(vd1), indices, proof


def main() -> int:
    surfaces, vd0, vd1, indices, proof = _fixture()
    doc = normalize(
        surfaces_doc=surfaces,
        vd0=vd0,
        vd1=vd1,
        index_bytes=indices,
        proof=proof,
        source_meta={"fixture": "synthetic"},
    )

    assert doc["format"] == "t6-world-mesh-normalized-v1"
    assert doc["map"] == "synthetic_world_normalizer"
    stats = doc["stats"]
    assert stats["surfaceCount"] == 4
    assert stats["vertexGroupCount"] == 3
    assert stats["serializedVertexCount"] == 13
    assert stats["topVertexCount"] == 13
    assert stats["triangleCount"] == 5
    assert stats["referencedIndexCount"] == 15
    assert stats["inputIndexCount"] == 18
    assert stats["uniqueReferencedIndexPositions"] == 15
    assert stats["unusedIndexPositions"] == 3
    assert stats["maxLocalIndex"] == 4
    assert stats["worldVertFormatGroupCounts"] == {"0": 1, "3": 1, "8": 1}

    assert [g["firstVertex"] for g in doc["groups"]] == [9, 0, 5]
    assert doc["groups"][0]["surfaceIndices"] == [0, 1]
    assert doc["surfaces"][0]["indices"] == [0, 1, 2]
    assert doc["surfaces"][1]["indices"] == [0, 2, 3]
    assert doc["surfaces"][2]["indices"] == [0, 1, 2, 2, 3, 4]
    assert doc["surfaces"][3]["indices"] == [0, 2, 3]

    attrs0 = doc["groups"][0]["attributes"]
    assert "uv1" not in attrs0
    assert attrs0["normal"][0] == [0.0, 0.0, 1.0]
    assert attrs0["tangent"][0] == [1.0, 0.0, 0.0]

    attrs1 = doc["groups"][1]["attributes"]
    assert len(attrs1["uv1"]) == 5
    assert len(attrs1["uv2"]) == 5
    assert "uv3" not in attrs1

    attrs2 = doc["groups"][2]["attributes"]
    assert len(attrs2["uv1"]) == 4
    assert len(attrs2["uv2"]) == 4
    assert len(attrs2["uv3"]) == 4
    assert len(attrs2["normalTransform0Packed"]) == 4
    assert len(attrs2["normalTransform1Packed"]) == 4
    assert attrs2["normalTransform0Packed"][0] == 0xA0008203
    assert attrs2["normalTransform1Packed"][0] == 0xA0008204

    # Output must be deterministic for identical normalized input.
    doc2 = normalize(
        surfaces_doc=surfaces,
        vd0=vd0,
        vd1=vd1,
        index_bytes=indices,
        proof=proof,
        source_meta={"fixture": "synthetic"},
    )
    assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
        doc2, sort_keys=True, separators=(",", ":")
    )

    # Fail closed on an index that exceeds its group's normalized vertex span.
    broken_values = list(struct.unpack("<" + "H" * (len(indices) // 2), indices))
    broken_values[0] = 4  # group0 contains only vertices 0..3
    broken = struct.pack("<" + "H" * len(broken_values), *broken_values)
    try:
        normalize(
            surfaces_doc=surfaces,
            vd0=vd0,
            vd1=vd1,
            index_bytes=broken,
            proof=proof,
        )
    except NormalizeError as exc:
        assert "outside group vertexCount" in str(exc)
    else:
        raise AssertionError("out-of-range local index was not rejected")

    # Fail closed when surfaces sharing a group disagree on firstVertex.
    bad_surfaces = copy.deepcopy(surfaces)
    bad_surfaces["surfaces"][1]["firstVertex"] = 8
    try:
        normalize(
            surfaces_doc=bad_surfaces,
            vd0=vd0,
            vd1=vd1,
            index_bytes=indices,
            proof=proof,
        )
    except NormalizeError as exc:
        assert "disagree on firstVertex" in str(exc)
    else:
        raise AssertionError("inconsistent firstVertex was not rejected")

    print("PASS t6_world_mesh_normalize_v1 synthetic regression")
    print(json.dumps(stats, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
