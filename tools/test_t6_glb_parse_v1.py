#!/usr/bin/env python3
from __future__ import annotations

import json
import struct

from t6_glb_parse_v1 import BIN_CHUNK, JSON_CHUNK, GlbParseError, parse_glb
from t6_world_gltf_export_v1 import glb_bytes


def expect_error(data: bytes, needle: str) -> None:
    try:
        parse_glb(data)
    except GlbParseError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected GlbParseError containing {needle!r}")


def main() -> int:
    # Exercise every possible logical-buffer padding count. The parser must
    # return logical bytes only, never the GLB BIN chunk's trailing zero pad.
    for length in range(1, 9):
        raw = bytes(range(length))
        doc = {
            "asset": {"version": "2.0"},
            "buffers": [{"byteLength": len(raw)}],
            "extras": {"sentinel": length},
        }
        payload = glb_bytes(doc, raw)
        parsed, parsed_raw = parse_glb(payload)
        assert parsed == doc
        assert parsed_raw == raw

    # Build a tiny valid GLB manually to keep the parser independent of the
    # writer helper in at least one case.
    raw = b"abcde"
    doc = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 5}]}
    json_raw = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    while len(json_raw) % 4:
        json_raw += b" "
    bin_raw = raw
    while len(bin_raw) % 4:
        bin_raw += b"\0"
    total = 12 + 8 + len(json_raw) + 8 + len(bin_raw)
    manual = (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<II", len(json_raw), JSON_CHUNK)
        + json_raw
        + struct.pack("<II", len(bin_raw), BIN_CHUNK)
        + bin_raw
    )
    parsed, parsed_raw = parse_glb(manual)
    assert parsed == doc and parsed_raw == raw

    expect_error(b"bad", "shorter")
    bad_magic = bytearray(manual)
    bad_magic[:4] = b"BAD!"
    expect_error(bytes(bad_magic), "magic")
    bad_version = bytearray(manual)
    struct.pack_into("<I", bad_version, 4, 1)
    expect_error(bytes(bad_version), "version")
    bad_length = bytearray(manual)
    struct.pack_into("<I", bad_length, 8, len(manual) - 1)
    expect_error(bytes(bad_length), "file length")

    # Logical byteLength cannot consume the container pad.
    bad_doc = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 9}]}
    bad_json = json.dumps(bad_doc).encode("utf-8")
    while len(bad_json) % 4:
        bad_json += b" "
    total = 12 + 8 + len(bad_json) + 8 + len(bin_raw)
    bad = (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<II", len(bad_json), JSON_CHUNK)
        + bad_json
        + struct.pack("<II", len(bin_raw), BIN_CHUNK)
        + bin_raw
    )
    expect_error(bad, "exceeds BIN")

    # Non-zero BIN pad is not legal output from this repo's writer and is
    # rejected so later append stages cannot accidentally archive it as data.
    corrupt = bytearray(manual)
    corrupt[-1] = 0x7F
    expect_error(bytes(corrupt), "padding contains non-zero")

    print("PASS: strict T6 GLB parser v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
