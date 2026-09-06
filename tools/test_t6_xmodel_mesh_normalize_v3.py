#!/usr/bin/env python3
import copy
import hashlib
import importlib.util
import struct
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
TOOL = HERE / "t6_xmodel_mesh_normalize_v3.py"

spec = importlib.util.spec_from_file_location("meshv3", TOOL)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot import {TOOL}")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

FOLLOW = 0xFFFFFFFF


def packed(block, off):
    return ((block << 29) | off) + 1


class FakeDecoder:
    def __init__(self, data, start):
        self.data = data
    def decode_vertex(self, start):
        return {"decodedAt": start}


Base = SimpleNamespace(Normalizer=FakeDecoder, PACKED_VERTEX=32)

data = bytearray(1000)
target_start = 0
# target owns its surface array
struct.pack_into("<I", data, target_start + 32, FOLLOW)
# target LOD0 must remain authoritative instead of owner LOD metadata
struct.pack_into("<fHH5I", data, target_start + 40, 321.0, 1, 0, 1, 2, 3, 4, 5)
# one XSurface fixed record at 300
sf = 300
data[sf] = 7                    # tileMode
data[sf + 1] = 1                # vertListCount
struct.pack_into("<H", data, sf + 2, 0)  # flags
struct.pack_into("<H", data, sf + 4, 2)  # verts
struct.pack_into("<H", data, sf + 6, 1)  # tris
struct.pack_into("<H", data, sf + 8, 9)  # baseVertIndex
struct.pack_into("<4h", data, sf + 16, 1, 0, 0, 0)
ptrs = {
    "triIndicesRaw": (12, 0x140),
    "vertsBlendRaw": (24, 0x100),
    "tensionRaw": (28, 0x110),
    "verts0Raw": (32, 0x120),
    "vertListRaw": (40, 0x130),
}
for _, (field_off, virtual_off) in ptrs.items():
    struct.pack_into("<I", data, sf + field_off, packed(5, virtual_off))
raw = bytes(data)
sha = hashlib.sha256(raw).hexdigest()
name = "c_test_mp_unit_smg_fb"
owner_name = "c_test_mp_owner_smg_fb"
comparison_fields = {
    "surfs[0].vertsBlend": 0x100,
    "surfs[0].tensionData": 0x110,
    "surfs[0].verts0": 0x120,
    "surfs[0].vertList": 0x130,
    "surfs[0].triIndices": 0x140,
}
skeleton = {
    "format": "t6-xmodel-skeleton-normalized-v2",
    "source": {"expandedSha256": sha, "xmodelFixedStart": target_start},
    "identity": {"name": name, "xassetIndex": 8},
    "skeleton": {"numBones": 4, "numRootBones": 1},
    "validation": {"allBoneNamesResolved": True, "hierarchyValid": True},
    "skeletonSource": {
        "mode": "packed_reusable_owner",
        "owner": {"xassetIndex": 3, "name": owner_name, "fixedSourceStart": 700},
        "comparisons": [
            {"field": f, "actualOffset": o, "predictedOffset": o, "match": True}
            for f, o in comparison_fields.items()
        ],
    },
}
target_walk = {
    "blockers": [],
    "assetSerializedEnd": 500,
    "assetSerializedBytes": 500,
    "assetSerializedSha256": "a" * 64,
    "xmodel": {
        "name": name, "numBones": 4, "numRootBones": 1, "numSurfs": 1, "numLods": 1,
        "surfaces": [{"rigidVertLists": []}],
    },
    "sections": [{"name": "XModel.surfs.fixed", "start": sf, "end": sf + 80}],
}
owner_mesh = {
    "identity": {"name": owner_name},
    "xmodel": {"numBones": 4, "numRootBones": 1, "numSurfs": 1, "numLods": 1,
               "lods": [{"index": 0, "dist": 999.0, "numSurfs": 1, "surfIndex": 0}]},
    "surfaces": [{
        "index": 0, "tileMode": 7, "flags": 0, "vertCount": 2, "triCount": 1, "baseVertIndex": 9,
        "blendCounts": [1, 0, 0, 0],
        "vertices": [{"ownerV": 0}, {"ownerV": 1}],
        "triangles": [[0, 1, 0]],
        "rigidVertLists": [{"boneOffset": 64, "vertCount": 1, "triOffset": 0, "triCount": 1,
                            "collisionTreePointer": {"kind": "null"}}],
        "joints0": [[1,0,0,0], [2,0,0,0]],
        "weights0": [[1.0,0,0,0], [1.0,0,0,0]],
    }],
}

out = m.merge_mesh(raw, target_start, skeleton, target_walk, owner_mesh, base_module=Base)
assert out["format"] == "t6-xmodel-mesh-normalized-v3"
assert out["reuseProof"]["borrowedFieldCount"] == 5
assert set(out["reuseProof"]["borrowedFields"]) == set(comparison_fields)
assert out["xmodel"]["lods"][0]["dist"] == 321.0
assert out["surfaces"][0]["vertices"] == owner_mesh["surfaces"][0]["vertices"]
assert out["surfaces"][0]["triangles"] == [[0,1,0]]
assert out["surfaces"][0]["joints0"] == [[1,0,0,0], [2,0,0,0]]
assert out["validation"]["targetHeaderAndLodsAuthoritative"] is True

# Missing one explicit packed-field comparison must fail closed.
bad_sk = copy.deepcopy(skeleton)
bad_sk["skeletonSource"]["comparisons"] = [r for r in bad_sk["skeletonSource"]["comparisons"] if r["field"] != "surfs[0].verts0"]
try:
    m.merge_mesh(raw, target_start, bad_sk, target_walk, owner_mesh, base_module=Base)
except ValueError as e:
    assert "no explicit reusable-owner replay comparison" in str(e)
else:
    raise AssertionError("packed vertex payload promoted without explicit replay comparison")

# Comparison offset must agree with the target's actual packed VIRTUAL offset.
bad_sk = copy.deepcopy(skeleton)
for row in bad_sk["skeletonSource"]["comparisons"]:
    if row["field"] == "surfs[0].triIndices":
        row["predictedOffset"] += 4
try:
    m.merge_mesh(raw, target_start, bad_sk, target_walk, owner_mesh, base_module=Base)
except ValueError as e:
    assert "predictedOffset" in str(e)
else:
    raise AssertionError("mismatched replay offset promoted")

# Whole XSurface-array reuse remains explicitly outside v3.
data2 = bytearray(raw); struct.pack_into("<I", data2, target_start + 32, packed(5, 0x222)); raw2 = bytes(data2)
sk2 = copy.deepcopy(skeleton); sk2["source"]["expandedSha256"] = hashlib.sha256(raw2).hexdigest()
try:
    m.merge_mesh(raw2, target_start, sk2, target_walk, owner_mesh, base_module=Base)
except ValueError as e:
    assert "top-level XModel.surfs" in str(e)
else:
    raise AssertionError("packed top-level surface array incorrectly accepted")

# Owner and target surface scalar identity cannot drift.
bad_owner = copy.deepcopy(owner_mesh); bad_owner["surfaces"][0]["triCount"] = 2
try:
    m.merge_mesh(raw, target_start, skeleton, target_walk, bad_owner, base_module=Base)
except ValueError as e:
    assert "scalar signature mismatch" in str(e)
else:
    raise AssertionError("scalar-incompatible owner mesh accepted")

# Inline rigid lists with their own packed collision-tree pointer remain blocked.
data3 = bytearray(raw); struct.pack_into("<I", data3, sf + 40, FOLLOW); raw3 = bytes(data3)
sk3 = copy.deepcopy(skeleton); sk3["source"]["expandedSha256"] = hashlib.sha256(raw3).hexdigest()
walk3 = copy.deepcopy(target_walk)
walk3["xmodel"]["surfaces"][0]["rigidVertLists"] = [{
    "boneOffset": 64, "vertCount": 1, "triOffset": 0, "triCount": 1,
    "collisionTreePointer": {"kind": "packed", "block": 5, "offset": 0x200},
}]
walk3["sections"].append({"name": "XModel.surfs[0].vertList.fixed", "start": 600, "end": 612})
try:
    m.merge_mesh(raw3, target_start, sk3, walk3, owner_mesh, base_module=Base)
except ValueError as e:
    assert "packed nested collision tree" in str(e)
else:
    raise AssertionError("unproven nested collision-tree reuse accepted")

print("PASS t6_xmodel_mesh_normalize_v3")
