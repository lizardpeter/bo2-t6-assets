#!/usr/bin/env python3
from __future__ import annotations

import struct

import t6_world_generated_normal_basis_attributes_v1 as v1
import t6_world_generated_normal_basis_attributes_v2 as v2
from test_t6_world_generated_normal_basis_attributes_v1 import fixture


def expect_error(fn, text):
    try:
        fn()
    except v2.GeneratedNormalBasisAttributeV2Error as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError(f"expected v2 error containing {text!r}")


def main() -> int:
    doc, raw, _, _ = fixture()
    doc, raw, _ = v1.apply_contract(doc, raw)
    source_len = len(raw)
    out, out_raw, stats = v2.apply_contract(doc, raw)
    assert out is doc
    assert stats["generatedPrimitiveCount"] == 1
    assert stats["uniqueBasisSourcePairCount"] == 1
    assert stats["derivedBinormalAccessorCount"] == 1
    assert stats["derivedBinormalVertexCount"] == 2
    assert stats["sourceBinBytes"] == source_len
    assert stats["finalBinBytes"] == len(out_raw)
    assert stats["appendedBinBytes"] == 24
    assert stats["alignmentPaddingBytes"] == 0

    attrs = out["meshes"][0]["primitives"][0]["attributes"]
    ordinary = out["meshes"][0]["primitives"][1]["attributes"]
    assert "_T6_WORLD_BINORMAL" in attrs
    assert "_T6_WORLD_BINORMAL" not in ordinary
    accessor = out["accessors"][attrs["_T6_WORLD_BINORMAL"]]
    assert accessor["componentType"] == 5126
    assert accessor["type"] == "VEC3"
    view = out["bufferViews"][accessor["bufferView"]]
    assert view["byteOffset"] == source_len
    assert view["byteLength"] == 24
    b0 = struct.unpack_from("<3f", out_raw, view["byteOffset"])
    b1 = struct.unpack_from("<3f", out_raw, view["byteOffset"] + 12)
    assert b0 == (0.0, 1.0, 0.0), b0
    assert b1 == (-1.0, -0.0, -0.0), b1

    contract = out["extras"]["T6"]["generatedNormalBasisAttributesV2"]
    assert contract["format"] == v2.FORMAT
    assert contract["interpolationTopology"] == "derive per vertex before raster interpolation"
    assert contract["binormalDerivations"][0]["positiveHandednessCount"] == 1
    assert contract["binormalDerivations"][0]["negativeHandednessCount"] == 1
    assert out["meshes"][0]["primitives"][0]["extras"]["T6"]["generatedNormalBasisAttributesV2"] == v2.FORMAT

    expect_error(lambda: v2.apply_contract(out, out_raw), "already attached")

    bad, bad_raw, _, _ = fixture()
    # TANGENT.w=0 violates the retained +/-1 handedness contract.
    tangent_view = bad["bufferViews"][1]
    mutable = bytearray(bad_raw)
    struct.pack_into("<f", mutable, tangent_view["byteOffset"] + 12, 0.0)
    bad_raw = bytes(mutable)
    bad, bad_raw, _ = v1.apply_contract(bad, bad_raw)
    expect_error(lambda: v2.apply_contract(bad, bad_raw), "not +/-1")

    print("PASS: generated normal basis attributes v2 vertex-stage binormal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
