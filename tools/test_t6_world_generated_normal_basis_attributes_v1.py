#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import struct

import t6_world_generated_normal_basis_attributes_v1 as contract


def fixture():
    normals = [
        (0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0),
    ]
    tangents = [
        (1.0, 0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, -1.0),
    ]
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
        "materials": [
            {"name": "*generated"},
            {"name": "ordinary"},
        ],
        "meshes": [{
            "primitives": [
                {"material": 0, "attributes": {"NORMAL": 0, "TANGENT": 1}},
                {"material": 1, "attributes": {"NORMAL": 0, "TANGENT": 1}},
            ]
        }],
        "extras": {"T6": {
            "generatedAttributeContract": {
                "format": "t6-world-generated-attribute-contract-v1",
                "stats": {"generatedPrimitiveCount": 1},
            }
        }},
    }
    return doc, raw, normals, tangents


def expect_error(fn, text):
    try:
        fn()
    except contract.GeneratedNormalBasisAttributeError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError(f"expected error containing {text!r}")


def main() -> int:
    doc, raw, normals, tangents = fixture()
    source = copy.deepcopy(doc)
    source_sha = hashlib.sha256(raw).hexdigest()
    out, out_raw, stats = contract.apply_contract(doc, raw)
    assert out is doc
    assert out_raw == raw
    assert hashlib.sha256(out_raw).hexdigest() == source_sha
    assert stats["binByteIdentical"] is True
    assert stats["generatedPrimitiveCount"] == 1
    assert stats["uniqueTangentSourceAccessorCount"] == 1
    assert stats["originalAccessorCount"] == 2
    assert stats["finalAccessorCount"] == 4
    assert stats["originalBufferViewCount"] == 2
    assert stats["finalBufferViewCount"] == 3

    generated = out["meshes"][0]["primitives"][0]["attributes"]
    ordinary = out["meshes"][0]["primitives"][1]["attributes"]
    assert generated["_T6_WORLD_NORMAL"] == generated["NORMAL"] == 0
    tangent_alias = generated["_T6_WORLD_TANGENT"]
    handed_alias = generated["_T6_TANGENT_HANDEDNESS"]
    assert tangent_alias == 2
    assert handed_alias == 3
    assert "_T6_WORLD_NORMAL" not in ordinary
    assert "_T6_WORLD_TANGENT" not in ordinary
    assert "_T6_TANGENT_HANDEDNESS" not in ordinary

    tangent_acc = out["accessors"][tangent_alias]
    hand_acc = out["accessors"][handed_alias]
    alias_view = out["bufferViews"][tangent_acc["bufferView"]]
    assert tangent_acc["type"] == "VEC3" and tangent_acc["byteOffset"] == 0
    assert hand_acc["type"] == "SCALAR" and hand_acc["byteOffset"] == 12
    assert alias_view["byteStride"] == 16
    assert alias_view["byteOffset"] == len(raw) - 32
    assert alias_view["byteLength"] == 32

    base = alias_view["byteOffset"]
    decoded_tangent = []
    decoded_hand = []
    for i in range(2):
        decoded_tangent.append(struct.unpack_from("<3f", raw, base + i * 16))
        decoded_hand.append(struct.unpack_from("<f", raw, base + i * 16 + 12)[0])
    assert decoded_tangent == [row[:3] for row in tangents]
    assert decoded_hand == [row[3] for row in tangents]

    root_contract = out["extras"]["T6"]["generatedNormalBasisAttributes"]
    assert root_contract["format"] == contract.FORMAT
    assert root_contract["stats"] == stats
    assert root_contract["contractSha256"]
    assert out["meshes"][0]["primitives"][0]["extras"]["T6"]["generatedNormalBasisAttributes"] == contract.FORMAT

    expect_error(lambda: contract.apply_contract(out, raw), "already attached")

    bad, bad_raw, _, _ = fixture()
    bad["accessors"][1]["type"] = "VEC3"
    expect_error(lambda: contract.apply_contract(bad, bad_raw), "TANGENT is not FLOAT VEC4")

    missing, missing_raw, _, _ = fixture()
    del missing["extras"]["T6"]["generatedAttributeContract"]
    expect_error(lambda: contract.apply_contract(missing, missing_raw), "lacks authoritative")

    # Input bytes and the pre-existing source document fixture itself remain a
    # useful independent reference; only the passed document is mutated.
    assert source["accessors"] == fixture()[0]["accessors"]

    print("PASS: zero-copy generated normal basis attributes v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
