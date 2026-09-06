#!/usr/bin/env python3
import importlib.util
import struct
from pathlib import Path

HERE = Path(__file__).parent


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v2 = load(HERE / "t6_weapon_xasset_structural_probe_v2.py", "weaponprobev2")
frontmap = load(HERE / "t6_virtual_front_map_v1.py", "frontmap")
FOLLOWING = 0xFFFFFFFF


def packed(block: int, offset: int) -> int:
    return (((block << 29) | offset) + 1) & 0xFFFFFFFF


def fixture() -> bytes:
    b = bytearray(256)
    struct.pack_into("<II", b, 0, 256, 0)
    struct.pack_into("<8I", b, 8, *([4096] * 8))
    struct.pack_into("<6I", b, 40, 2, FOLLOWING, 0, 0, 1, FOLLOWING)
    pos = 64
    struct.pack_into("<2I", b, pos, FOLLOWING, FOLLOWING)
    pos += 8
    b[pos:pos + 6] = b"alpha\0"
    pos += 6
    b[pos:pos + 15] = b"peacekeeper_mp\0"
    pos += 15
    # Destination VIRTUAL aligns from 29 to 32 before the XAsset array. No
    # source bytes are consumed by that destination-only alignment.
    struct.pack_into("<II", b, pos, 25, FOLLOWING)
    pos += 8
    return bytes(b[:pos])


data = fixture()
front = frontmap.build_front_map(data)
peace = next(a for a in front["allocations"] if a["kind"] == "script-string" and a["text"] == "peacekeeper_mp")


class FakeRaw:
    pass


class FakeV1:
    pointer_raw = packed(5, peace["virtualStart"])

    @classmethod
    def probe(cls, data, rawmod):
        candidate = {
            "internalName": None,
            "internalNameStatus": "unresolved-packed-name-pointer",
            "internalNamePointer": {
                "raw_u32": cls.pointer_raw,
                "decoded": {"kind": "packed", "block": 5, "offset": (cls.pointer_raw - 1) & 0x1FFFFFFF},
            },
            "selector": {"status": "exact-direct-weapdef-prefix"},
        }
        return {
            "format": "t6-weapon-xasset-structural-probe-v1",
            "front": {
                "assetCount": front["assetCount"],
                "assetBodyStreamRawOffset": front["assetBodyRawOffset"],
            },
            "structuralCandidates": [candidate],
            "bindableStructuralCandidates": [candidate],
            "bindings": [{
                "status": "exact-by-single-inline-weapon-cardinality",
                "assetIndex": 0,
                "weaponVariantDef": candidate,
            }],
            "summary": {"exactInternalNames": 0},
        }


out = v2.probe(data, FakeRaw, FakeV1, frontmap)
bound = out["bindings"][0]["weaponVariantDef"]
assert out["format"] == "t6-weapon-xasset-structural-probe-v2", out["format"]
assert bound["internalName"] == "peacekeeper_mp", bound
assert bound["internalNameStatus"] == "exact-packed-front-xstring", bound
assert out["summary"]["exactInternalNames"] == 1, out["summary"]
assert out["summary"]["exactPackedFrontInternalNames"] == 1, out["summary"]
assert out["packedXStringFrontReplay"]["exactFrontXStrings"] == 1, out["packedXStringFrontReplay"]

# A valid packed VIRTUAL pointer beyond the proven front must remain unresolved.
FakeV1.pointer_raw = packed(5, front["virtualOffsetAfterAssetArray"] + 100)
out2 = v2.probe(data, FakeRaw, FakeV1, frontmap)
bound2 = out2["bindings"][0]["weaponVariantDef"]
assert bound2["internalName"] is None, bound2
assert bound2["internalNameStatus"] == "unresolved-packed-name-pointer", bound2
assert bound2["packedInternalNameResolution"]["status"] == "later-virtual-allocation", bound2
assert out2["summary"]["exactInternalNames"] == 0, out2["summary"]
assert out2["summary"]["exactPackedFrontInternalNames"] == 0, out2["summary"]

print("test_t6_weapon_xasset_structural_probe_v2: PASS")
