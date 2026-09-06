#!/usr/bin/env python3
import hashlib
import importlib.util
import struct
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
TOOL = HERE / "t6_xmodel_mesh_normalize_v2.py"

spec = importlib.util.spec_from_file_location("meshv2", TOOL)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot import {TOOL}")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

FOLLOW = 0xFFFFFFFF


def packed(block, off):
    return ((block << 29) | off) + 1


class FakeBaseNormalizer:
    def __init__(self, data, start):
        self.data = data
        self.start = start

    def u32(self, b, o):
        return struct.unpack_from("<I", self.data, b + o)[0]

    def normalize(self):
        vals = {o: self.u32(self.start, o) for o in (8, 12, 16, 20, 24, 28)}
        if any(v not in (0, FOLLOW, 0xFFFFFFFE) for v in vals.values()):
            raise ValueError("v1 requires inline skeleton arrays")
        if self.u32(self.start, 32) != FOLLOW:
            raise ValueError("verts/surfs packed unsupported")
        return {
            "format": "t6-xmodel-mesh-normalized-v1",
            "identity": {"name": "c_test_mp_unit_smg_fb"},
            "source": {"assetFixedStart": self.start},
            "xmodel": {"numBones": 3, "numRootBones": 1, "numSurfs": 1, "numLods": 1},
            "surfaces": [{"vertCount": 3, "triCount": 1, "vertices": [{}, {}, {}], "triangles": [[0, 1, 2]]}],
            "validation": {"allLocalTriangleIndicesInRange": True},
        }


Base = SimpleNamespace(Normalizer=FakeBaseNormalizer)

data = bytearray(300)
for o in (8, 12, 16, 20, 24, 28):
    struct.pack_into("<I", data, o, packed(5, 0x100 + o))
struct.pack_into("<I", data, 32, FOLLOW)
raw = bytes(data)
sha = hashlib.sha256(raw).hexdigest()
skeleton = {
    "format": "t6-xmodel-skeleton-normalized-v2",
    "source": {"expandedSha256": sha, "xmodelFixedStart": 0},
    "identity": {"name": "c_test_mp_unit_smg_fb", "xassetIndex": 7},
    "skeletonSource": {"mode": "packed_reusable_owner"},
    "skeleton": {"numBones": 3, "numRootBones": 1},
    "validation": {"allBoneNamesResolved": True, "hierarchyValid": True},
}

out = m.normalize_mesh(raw, 0, skeleton, base_module=Base)
assert out["format"] == "t6-xmodel-mesh-normalized-v2"
assert set(out["skeletonDependency"]["packedSkeletonPointers"]) == {
    "boneNames", "parentList", "quats", "trans", "partClassification", "baseMat"
}
assert out["validation"]["packedSkeletonArraysIndependentlyResolved"] is True

bad = dict(skeleton); bad["skeletonSource"] = {"mode": "inline_owned"}
try:
    m.normalize_mesh(raw, 0, bad, base_module=Base)
except ValueError as e:
    assert "packed_reusable_owner" in str(e)
else:
    raise AssertionError("packed skeleton accepted without reusable-owner proof")

bad = dict(skeleton); bad["source"] = dict(skeleton["source"]); bad["source"]["expandedSha256"] = "0" * 64
try:
    m.normalize_mesh(raw, 0, bad, base_module=Base)
except ValueError as e:
    assert "expandedSha256 mismatch" in str(e)
else:
    raise AssertionError("cross-stream skeleton accepted")

data2 = bytearray(raw)
struct.pack_into("<I", data2, 32, packed(5, 0x999))
raw2 = bytes(data2)
sha2 = hashlib.sha256(raw2).hexdigest()
sk2 = dict(skeleton); sk2["source"] = dict(skeleton["source"]); sk2["source"]["expandedSha256"] = sha2
try:
    m.normalize_mesh(raw2, 0, sk2, base_module=Base)
except ValueError as e:
    assert "packed unsupported" in str(e)
else:
    raise AssertionError("packed render surface reuse incorrectly accepted")

print("PASS t6_xmodel_mesh_normalize_v2")
