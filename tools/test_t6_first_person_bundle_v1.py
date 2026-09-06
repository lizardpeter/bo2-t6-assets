#!/usr/bin/env python3
"""Focused deterministic regressions for the first-person benchmark track."""
from __future__ import annotations

import json
import struct
import tempfile
from pathlib import Path

from t6_first_person_bundle_plan_v1 import class_validation, collect_named_records
from t6_oat_xmodel_catalog_v1 import parse_descriptor
from t6_xmodel_target_probe_v1 import FOLLOWING, XMODEL_PC32, probe_name, validate_candidate


class FakeRaw:
    @staticmethod
    def zone_pointer(value, blocks):
        # Synthetic fixture uses only null/FOLLOWING pointers, so any packed
        # pointer is deliberately invalid.
        return {"kind": "packed", "valid": False}


def synthetic_xmodel(name: str) -> bytes:
    data = bytearray(XMODEL_PC32 + len(name) + 1)
    struct.pack_into("<I", data, 0, FOLLOWING)
    data[4] = 2   # numBones
    data[5] = 1   # numRootBones
    data[6] = 1   # numsurfs
    data[7] = 1   # lodRampType skinned
    # LOD0: finite distance, one surface beginning at surface zero.
    struct.pack_into("<fHH", data, 40, 0.0, 1, 0)
    # Remaining LOD records remain zero-filled and finite.
    struct.pack_into("<f", data, 168, 10.0)  # radius
    struct.pack_into("<3f", data, 172, -1.0, -2.0, -3.0)
    struct.pack_into("<3f", data, 184, 1.0, 2.0, 3.0)
    struct.pack_into("<Hh", data, 196, 1, -1)  # numLods, collLod
    data[XMODEL_PC32:] = name.encode("ascii") + b"\0"
    return bytes(data)


def main() -> int:
    name = "c_usa_mp_seal6_shortsleeve_viewhands"
    data = synthetic_xmodel(name)
    candidate = validate_candidate(data, 0, name, FakeRaw, [1024] * 8)
    assert candidate is not None
    assert candidate["status"] == "exact_inline_xmodel"
    assert candidate["numBones"] == 2
    assert candidate["numRootBones"] == 1
    assert candidate["numSurfs"] == 1
    assert candidate["numLods"] == 1

    hit = probe_name(data, {"name": name, "role": "viewhands", "required": True}, FakeRaw, [1024] * 8)
    assert hit["status"] == "exact_inline_xmodel"
    assert hit["role"] == "viewhands"
    miss = probe_name(data, {"name": "not_here", "required": True}, FakeRaw, [1024] * 8)
    assert miss["status"] == "not_inline_locatable"

    assert class_validation("viewhands", [{"evidenceKind": "pinned-oat-xmodel", "type": "viewhands"}])["status"] == "validated"
    assert class_validation("viewhands", [{"evidenceKind": "pinned-oat-xmodel", "type": "animated"}])["status"] == "contradiction"
    assert class_validation("human-third-person", [{"evidenceKind": "direct-raw-xmodel"}])["status"] == "unvalidated"
    assert class_validation("first-person-weapon", [])["status"] == "not-required"

    named = []
    collect_named_records({"outer": [{"name": "viewmodel_mp7_idle", "numframes": 30}]}, Path("proof.json"), named)
    assert [x["name"] for x in named] == ["viewmodel_mp7_idle"]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "xmodel").mkdir()
        (root / "model_export").mkdir()
        lod = root / "model_export" / f"{name}_lod0.gltf"
        lod.write_text('{"asset":{"version":"2.0"}}', encoding="utf-8")
        descriptor = root / "xmodel" / f"{name}.json"
        descriptor.write_text(json.dumps({
            "$schema": "http://openassettools.dev/schema/xmodel.v1.json",
            "_type": "xmodel",
            "_version": 2,
            "_game": "t6",
            "type": "viewhands",
            "lods": [{"file": f"model_export/{name}_lod0.gltf", "distance": 0.0}],
            "flags": 0,
            "lightingOriginOffset": {"x": 0, "y": 0, "z": 0},
            "lightingOriginRange": 0.0,
        }), encoding="utf-8")
        parsed = parse_descriptor(root, root / "xmodel", descriptor)
        assert parsed["name"] == name
        assert parsed["type"] == "viewhands"
        assert parsed["allDeclaredLodFilesPresent"] is True
        assert parsed["lods"][0]["sha256"]

    print("PASS: T6 first-person benchmark v1 regressions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
