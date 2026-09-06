#!/usr/bin/env python3
"""Convert one self-contained glTF 2.0 JSON document into a deterministic GLB 2.0.

The T6 XModel/XAnim exporters intentionally emit a single embedded base64 buffer
so their JSON sidecars remain easy to inspect.  This adapter only changes the
container.  It does not rewrite accessors, nodes, skins, animations, materials,
or any decoded retail payload.

Fail-closed constraints:
- exactly one glTF buffer;
- buffer must be an application/octet-stream base64 data URI;
- declared byteLength must equal decoded bytes;
- no external buffer dependency;
- emitted GLB is reparsed and its JSON/BIN payloads are verified.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import struct
from pathlib import Path

MAGIC = b"glTF"
VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
BUFFER_PREFIX = "data:application/octet-stream;base64,"


class GlbError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_glb(gltf: dict) -> bytes:
    doc = copy.deepcopy(gltf)
    buffers = doc.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise GlbError(f"expected exactly one glTF buffer, got {0 if buffers is None else len(buffers)}")
    buf = buffers[0]
    uri = buf.get("uri")
    if not isinstance(uri, str) or not uri.startswith(BUFFER_PREFIX):
        raise GlbError("buffer is not the required embedded application/octet-stream base64 URI")
    try:
        raw = base64.b64decode(uri[len(BUFFER_PREFIX):], validate=True)
    except Exception as e:
        raise GlbError(f"invalid embedded base64 buffer: {e}") from e
    declared = int(buf.get("byteLength", -1))
    if declared != len(raw):
        raise GlbError(f"buffer byteLength mismatch: declared={declared} decoded={len(raw)}")

    doc["buffers"] = [{"byteLength": len(raw)}]
    json_bytes = json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    json_bytes += b" " * ((-len(json_bytes)) % 4)
    bin_bytes = raw + b"\x00" * ((-len(raw)) % 4)
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    out = bytearray(struct.pack("<4sII", MAGIC, VERSION, total))
    out += struct.pack("<II", len(json_bytes), JSON_CHUNK)
    out += json_bytes
    out += struct.pack("<II", len(bin_bytes), BIN_CHUNK)
    out += bin_bytes
    return bytes(out)


def parse_glb(blob: bytes) -> tuple[dict, bytes]:
    if len(blob) < 20:
        raise GlbError("GLB too short")
    magic, version, total = struct.unpack_from("<4sII", blob, 0)
    if magic != MAGIC or version != VERSION or total != len(blob):
        raise GlbError(f"invalid GLB header magic={magic!r} version={version} total={total} actual={len(blob)}")
    pos = 12
    doc = None
    bin_chunk = None
    seen = []
    while pos < len(blob):
        if pos + 8 > len(blob):
            raise GlbError("truncated GLB chunk header")
        n, typ = struct.unpack_from("<II", blob, pos)
        pos += 8
        if pos + n > len(blob):
            raise GlbError("truncated GLB chunk payload")
        payload = blob[pos:pos+n]
        pos += n
        seen.append(typ)
        if typ == JSON_CHUNK:
            if doc is not None:
                raise GlbError("duplicate JSON chunk")
            doc = json.loads(payload.rstrip(b" \x00\t\r\n"))
        elif typ == BIN_CHUNK:
            if bin_chunk is not None:
                raise GlbError("duplicate BIN chunk")
            bin_chunk = payload
    if doc is None or bin_chunk is None:
        raise GlbError(f"missing required chunks: {seen}")
    return doc, bin_chunk


def convert_gltf_dict(gltf: dict) -> tuple[bytes, dict]:
    uri = gltf.get("buffers", [{}])[0].get("uri", "") if gltf.get("buffers") else ""
    if not isinstance(uri, str) or not uri.startswith(BUFFER_PREFIX):
        raise GlbError("input glTF does not contain the expected embedded buffer")
    raw = base64.b64decode(uri[len(BUFFER_PREFIX):], validate=True)
    blob = encode_glb(gltf)
    parsed, parsed_bin = parse_glb(blob)
    if parsed.get("buffers") != [{"byteLength": len(raw)}]:
        raise GlbError("round-trip GLB buffer declaration changed")
    if parsed_bin[:len(raw)] != raw or any(parsed_bin[len(raw):]):
        raise GlbError("round-trip GLB BIN payload differs from source buffer")
    expected = copy.deepcopy(gltf)
    expected["buffers"] = [{"byteLength": len(raw)}]
    if parsed != expected:
        raise GlbError("round-trip GLB JSON differs from source glTF after URI removal")
    return blob, {
        "sourceBufferBytes": len(raw),
        "sourceBufferSha256": sha256(raw),
        "glbBytes": len(blob),
        "glbSha256": sha256(blob),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_gltf", type=Path)
    ap.add_argument("output_glb", type=Path)
    args = ap.parse_args()
    gltf = json.loads(args.input_gltf.read_text(encoding="utf-8"))
    blob, stats = convert_gltf_dict(gltf)
    args.output_glb.parent.mkdir(parents=True, exist_ok=True)
    args.output_glb.write_bytes(blob)
    print(json.dumps({"out": str(args.output_glb), **stats}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
