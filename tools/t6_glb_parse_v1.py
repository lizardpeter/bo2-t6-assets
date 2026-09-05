#!/usr/bin/env python3
"""Strict minimal parser for the repo's single-buffer glTF 2.0 GLB artifacts.

The parser intentionally returns BIN bytes truncated to `buffers[0].byteLength`
rather than the four-byte-padded BIN chunk length. That distinction matters when
a later archival stage appends a new bufferView: GLB chunk padding is container
padding and is not part of the logical glTF buffer.
"""
from __future__ import annotations

import json
import struct


JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


class GlbParseError(RuntimeError):
    pass


def parse_glb(data: bytes) -> tuple[dict, bytes]:
    if len(data) < 12:
        raise GlbParseError("GLB is shorter than the 12-byte header")
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise GlbParseError(f"invalid GLB magic {magic!r}")
    if version != 2:
        raise GlbParseError(f"unsupported GLB version {version}")
    if total_length != len(data):
        raise GlbParseError(
            f"GLB header length {total_length} does not match file length {len(data)}"
        )

    offset = 12
    json_payload = None
    bin_payload = None
    chunk_count = 0
    while offset < len(data):
        if offset + 8 > len(data):
            raise GlbParseError("truncated GLB chunk header")
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        end = offset + chunk_length
        if end > len(data):
            raise GlbParseError("GLB chunk extends beyond file length")
        payload = data[offset:end]
        offset = end
        chunk_count += 1

        if chunk_type == JSON_CHUNK:
            if json_payload is not None:
                raise GlbParseError("GLB contains multiple JSON chunks")
            if chunk_count != 1:
                raise GlbParseError("glTF 2.0 JSON chunk must be first")
            json_payload = payload
        elif chunk_type == BIN_CHUNK:
            if bin_payload is not None:
                raise GlbParseError("GLB contains multiple BIN chunks")
            bin_payload = payload
        else:
            raise GlbParseError(f"unsupported GLB chunk type 0x{chunk_type:08x}")

    if json_payload is None:
        raise GlbParseError("GLB has no JSON chunk")
    try:
        document = json.loads(json_payload.rstrip(b" \t\r\n\0").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GlbParseError(f"invalid GLB JSON chunk: {exc}") from exc

    buffers = document.get("buffers", [])
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise GlbParseError(
            f"expected exactly one glTF buffer, found {len(buffers) if isinstance(buffers, list) else 'not-list'}"
        )
    logical_length = int(buffers[0].get("byteLength", -1))
    if logical_length < 0:
        raise GlbParseError("buffers[0] has invalid byteLength")

    if logical_length == 0:
        if bin_payload not in (None, b""):
            # A padded zero-byte logical buffer is not produced by our exporters.
            raise GlbParseError("zero-length logical buffer has unexpected BIN payload")
        return document, b""

    if bin_payload is None:
        raise GlbParseError("non-empty logical glTF buffer has no GLB BIN chunk")
    if logical_length > len(bin_payload):
        raise GlbParseError(
            f"logical buffer length {logical_length} exceeds BIN chunk length {len(bin_payload)}"
        )
    padding = bin_payload[logical_length:]
    if len(padding) > 3:
        raise GlbParseError(
            f"GLB BIN chunk has {len(padding)} bytes beyond logical buffer; expected <=3 padding bytes"
        )
    if any(byte != 0 for byte in padding):
        raise GlbParseError("GLB BIN padding contains non-zero bytes")

    return document, bin_payload[:logical_length]
