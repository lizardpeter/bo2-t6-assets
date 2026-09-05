#!/usr/bin/env python3
from __future__ import annotations

import struct

import t6_dxbc_material_constant_binding_v1 as binding


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<I", len(payload)) + payload


def _fixture_dxbc() -> bytes:
    # Synthetic shader-model 4.0 RDEF with one cbuffer bound at b1 and one
    # float4 variable at byte 0x3b0 (cb1[59]). The production parser does not
    # depend on compiler text/disassembly for this mapping.
    resource_offset = 28
    cbuffer_offset = resource_offset + 32
    variables_offset = cbuffer_offset + 24
    strings_offset = variables_offset + 24
    names = b"PerMaterial\0alphaRevealParms1\0fixture-creator\0"
    per_material_name = strings_offset
    alpha_name = per_material_name + len(b"PerMaterial\0")
    creator_name = alpha_name + len(b"alphaRevealParms1\0")

    header = struct.pack(
        "<IIII", 1, cbuffer_offset, 1, resource_offset
    ) + struct.pack("<H", 0x0400) + struct.pack("<H", 0) + struct.pack("<I", 0) + struct.pack("<I", creator_name)
    assert len(header) == 28
    resource = struct.pack(
        "<IIIIIIII",
        per_material_name,  # name
        0,                  # CBUFFER
        0, 0, 0,
        1,                  # bind point b1
        1,                  # bind count
        0,
    )
    cbuffer = struct.pack(
        "<IIIIII",
        per_material_name,
        1,                  # variable count
        variables_offset,
        0x3C0,              # 960 bytes, includes register 59
        0,
        0,
    )
    variable = struct.pack(
        "<IIIIII",
        alpha_name,
        0x3B0,
        16,
        0,
        0,
        0,
    )
    rdef = header + resource + cbuffer + variable + names

    shdr = struct.pack("<II", 0x40, 2)  # ps_4_0, two DWORDs total
    chunks = [_chunk(b"RDEF", rdef), _chunk(b"SHDR", shdr)]
    table_bytes = 4 * len(chunks)
    first = 32 + table_bytes
    offsets = []
    cursor = first
    for raw in chunks:
        offsets.append(cursor)
        cursor += len(raw)
    total = cursor
    dxbc = (
        b"DXBC"
        + b"\0" * 16
        + struct.pack("<I", 1)
        + struct.pack("<I", total)
        + struct.pack("<I", len(chunks))
        + b"".join(struct.pack("<I", value) for value in offsets)
        + b"".join(chunks)
    )
    assert len(dxbc) == total
    return dxbc


def main() -> int:
    assert binding.t6_r_hash_string("alphaRevealParms1", 0) == 0x88BEFC31

    dxbc = _fixture_dxbc()
    rdef = binding.parse_rdef_constant_buffers(dxbc)
    assert rdef["shaderModel"] == "4.0"
    assert rdef["constantBufferCount"] == 1
    cb = rdef["constantBuffers"][0]
    assert cb["name"] == "PerMaterial" and cb["bindPoint"] == 1
    assert cb["variables"][0]["name"] == "alphaRevealParms1"
    assert cb["variables"][0]["startOffset"] == 0x3B0

    technique = """
    pixelShader 4.0 "fixture"
    {
      alphaRevealParms1 = material.alphaRevealParms1;
    }
    """
    constants = [{
        "nameHash": 0x88BEFC31,
        "nameHashHex": "0x88befc31",
        "nameFragment": "alphaRevealP",
        "literal": [0.25, 2.0, 7.0, 9.0],
        "serializedSha256": "a" * 64,
    }]
    result = binding.bind_cb_leaves(
        ["cb1[59].y", "cb1[59].x"],
        dxbc=dxbc,
        technique_text=technique,
        material_constants=constants,
    )
    assert result["allLeavesExact"] is True
    rows = {row["leaf"]: row for row in result["bindings"]}
    assert rows["cb1[59].x"]["materialConstant"]["name"] == "alphaRevealParms1"
    assert rows["cb1[59].x"]["materialConstant"]["value"] == 0.25
    assert rows["cb1[59].x"]["materialConstant"]["literalComponent"] == 0
    assert rows["cb1[59].y"]["materialConstant"]["value"] == 2.0
    assert rows["cb1[59].y"]["materialConstant"]["literalComponent"] == 1
    assert rows["cb1[59].y"]["cbuffer"]["byteOffset"] == 0x3B4

    wrong_fragment = [dict(constants[0], nameFragment="alphaRevealX")]
    try:
        binding.bind_cb_leaves(
            ["cb1[59].x"],
            dxbc=dxbc,
            technique_text=technique,
            material_constants=wrong_fragment,
        )
    except binding.MaterialConstantBindingError as exc:
        assert "hash matched but fragment" in str(exc)
    else:
        raise AssertionError("hash-only constant join accepted a bad serialized name fragment")

    try:
        binding.bind_cb_leaves(
            ["cb1[59].x"],
            dxbc=dxbc,
            technique_text="pixelShader 4.0 \"fixture\" {}",
            material_constants=constants,
        )
    except binding.MaterialConstantBindingError as exc:
        assert "has no material.* assignment" in str(exc)
    else:
        raise AssertionError("missing .tech material assignment was guessed")

    print("PASS: exact T6 DXBC -> material constant binding v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
