#!/usr/bin/env python3
"""Regression for deterministic T6 DXBC/RDEF inspection."""
from __future__ import annotations

import copy
import json
import struct

from t6_dxbc_inspect_v1 import DxbcInspectError, inspect_dxbc


def _rdef() -> bytes:
    creator = b"fixture-compiler\0"
    primary = b"lightmapSamplerPrimary\0"
    secondary = b"lightmapSamplerSecondary\0"
    resource_offset = 28
    resource_count = 2
    strings_offset = resource_offset + resource_count * 32
    creator_offset = strings_offset
    primary_offset = creator_offset + len(creator)
    secondary_offset = primary_offset + len(primary)

    header = struct.pack(
        "<IIIIBBHII",
        0,                  # constantBufferCount
        0,                  # constantBufferOffset
        resource_count,
        resource_offset,
        0,                  # minor
        4,                  # major
        0,                  # shader type
        0,                  # flags
        creator_offset,
    )
    primary_resource = struct.pack(
        "<IIIIIIII",
        primary_offset,
        2,                  # TEXTURE
        5,                  # FLOAT
        4,                  # TEXTURE2D
        0,
        3,                  # bind point t3
        1,
        0,
    )
    secondary_resource = struct.pack(
        "<IIIIIIII",
        secondary_offset,
        2,
        5,
        4,
        0,
        7,                  # bind point t7
        1,
        0,
    )
    return header + primary_resource + secondary_resource + creator + primary + secondary


def _shdr(program_type: int = 0, major: int = 4, minor: int = 0) -> bytes:
    token = (program_type << 16) | (major << 4) | minor
    return struct.pack("<II", token, 2)


def _dxbc(chunks: list[tuple[bytes, bytes]], *, word20: int = 1) -> bytes:
    table_end = 32 + len(chunks) * 4
    offsets: list[int] = []
    body = bytearray()
    cursor = table_end
    for tag, payload in chunks:
        offsets.append(cursor)
        encoded = tag + struct.pack("<I", len(payload)) + payload
        body.extend(encoded)
        cursor += len(encoded)
    total = table_end + len(body)
    header = bytearray()
    header.extend(b"DXBC")
    header.extend(bytes(range(16)))
    header.extend(struct.pack("<III", word20, total, len(chunks)))
    header.extend(struct.pack("<" + "I" * len(offsets), *offsets))
    return bytes(header + body)


def _expect_error(data: bytes, needle: str) -> None:
    try:
        inspect_dxbc(data, name="bad.cso")
    except DxbcInspectError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected DxbcInspectError containing {needle!r}")


def main() -> int:
    data = _dxbc([(b"RDEF", _rdef()), (b"SHDR", _shdr())])
    doc = inspect_dxbc(data, name="ps_fixture.cso")
    assert doc["format"] == "t6-dxbc-inspection-v1"
    assert doc["name"] == "ps_fixture.cso"
    assert doc["bytes"] == len(data)
    assert doc["totalSize"] == len(data)
    assert doc["chunkCount"] == 2
    assert doc["headerWord20"] == 1
    assert doc["checksumHex"] == bytes(range(16)).hex()
    assert [x["tag"] for x in doc["chunks"]] == ["RDEF", "SHDR"]
    assert all(len(x["payloadSha256"]) == 64 for x in doc["chunks"])

    assert doc["program"] == {
        "tag": "SHDR",
        "shaderModel": "4.0",
        "major": 4,
        "minor": 0,
        "programType": "pixel",
        "programTypeValue": 0,
        "declaredProgramDwords": 2,
        "declaredProgramBytes": 8,
    }
    rdef = doc["reflection"]
    assert rdef["shaderModel"] == "4.0"
    assert rdef["creator"] == "fixture-compiler"
    assert rdef["boundResourceCount"] == 2
    assert rdef["boundResourceEntrySize"] == 32
    assert [x["name"] for x in rdef["boundResources"]] == [
        "lightmapSamplerPrimary",
        "lightmapSamplerSecondary",
    ]
    assert [x["bindPoint"] for x in rdef["boundResources"]] == [3, 7]
    assert all(x["inputType"] == "TEXTURE" for x in rdef["boundResources"])
    assert all(x["returnType"] == "FLOAT" for x in rdef["boundResources"])
    assert all(x["dimension"] == "TEXTURE2D" for x in rdef["boundResources"])
    assert doc["lightmap"]["hasPrimary"] is True
    assert doc["lightmap"]["hasSecondary"] is True
    assert doc["lightmap"]["resourceCount"] == 2

    # Deterministic inspection output.
    doc2 = inspect_dxbc(bytes(data), name="ps_fixture.cso")
    assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
        doc2, sort_keys=True, separators=(",", ":")
    )

    bad_magic = b"NOPE" + data[4:]
    _expect_error(bad_magic, "missing DXBC magic")

    bad_size = bytearray(data)
    struct.pack_into("<I", bad_size, 24, len(data) + 1)
    _expect_error(bytes(bad_size), "total size mismatch")

    no_rdef = _dxbc([(b"SHDR", _shdr())])
    _expect_error(no_rdef, "no RDEF")

    no_program = _dxbc([(b"RDEF", _rdef())])
    _expect_error(no_program, "no SHDR/SHEX")

    vertex = _dxbc([(b"RDEF", _rdef()), (b"SHDR", _shdr(program_type=1))])
    vdoc = inspect_dxbc(vertex)
    assert vdoc["program"]["programType"] == "vertex"

    model_mismatch = _dxbc([(b"RDEF", _rdef()), (b"SHDR", _shdr(major=5))])
    _expect_error(model_mismatch, "shader model disagreement")

    duplicate_offsets = bytearray(data)
    first = struct.unpack_from("<I", duplicate_offsets, 32)[0]
    struct.pack_into("<I", duplicate_offsets, 36, first)
    _expect_error(bytes(duplicate_offsets), "duplicate offsets")

    bad_program_length = _dxbc(
        [(b"RDEF", _rdef()), (b"SHDR", struct.pack("<II", 0x40, 999))]
    )
    _expect_error(bad_program_length, "declared program length")

    # Corrupt RDEF resource count so the table would exceed the chunk.
    bad_rdef_payload = bytearray(_rdef())
    struct.pack_into("<I", bad_rdef_payload, 8, 999)
    bad_rdef = _dxbc([(b"RDEF", bytes(bad_rdef_payload)), (b"SHDR", _shdr())])
    _expect_error(bad_rdef, "bound-resource table exceeds chunk")

    print("PASS t6_dxbc_inspect_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
