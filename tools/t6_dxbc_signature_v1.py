#!/usr/bin/env python3
"""Strict DXBC SM4 input/output signature parser for retained T6 shaders.

Extracts ISGN/OSGN register -> semantic identity using the same 24-byte SM4
signature entry layout already exercised by retained T6 reflection proofs.
No shader semantic is inferred from register number alone.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

FORMAT = "t6-dxbc-signature-v1"


class DxbcSignatureError(RuntimeError):
    pass


def _chunks(blob: bytes, tag: bytes) -> list[bytes]:
    if len(blob) < 32 or blob[:4] != b"DXBC":
        raise DxbcSignatureError("missing/short DXBC container")
    total = struct.unpack_from("<I", blob, 24)[0]
    count = struct.unpack_from("<I", blob, 28)[0]
    if total != len(blob):
        raise DxbcSignatureError(f"DXBC size mismatch header={total} actual={len(blob)}")
    if 32 + 4 * count > len(blob):
        raise DxbcSignatureError("DXBC chunk offset table outside container")
    out = []
    for off in struct.unpack_from("<" + "I" * count, blob, 32):
        if off + 8 > len(blob):
            raise DxbcSignatureError(f"chunk offset outside container: {off}")
        size = struct.unpack_from("<I", blob, off + 4)[0]
        end = off + 8 + size
        if end > len(blob):
            raise DxbcSignatureError(f"chunk at {off} exceeds container")
        if blob[off:off + 4] == tag:
            out.append(blob[off + 8:end])
    return out


def parse_signature(blob: bytes, tag: str) -> dict:
    raw_tag = tag.encode("ascii")
    if raw_tag not in (b"ISGN", b"OSGN"):
        raise DxbcSignatureError(f"unsupported SM4 signature tag {tag!r}")
    chunks = _chunks(blob, raw_tag)
    if len(chunks) != 1:
        raise DxbcSignatureError(f"{tag}: expected exactly one chunk, found {len(chunks)}")
    payload = chunks[0]
    if len(payload) < 8:
        raise DxbcSignatureError(f"{tag}: payload shorter than header")
    count, unknown = struct.unpack_from("<II", payload, 0)
    table_end = 8 + 24 * count
    if table_end > len(payload):
        raise DxbcSignatureError(f"{tag}: entry table exceeds payload")
    rows = []
    seen_registers = set()
    for index in range(count):
        off = 8 + 24 * index
        name_off, semantic_index, system_value, component_type, register, mask_rw = struct.unpack_from(
            "<6I", payload, off
        )
        if name_off < table_end or name_off >= len(payload):
            raise DxbcSignatureError(
                f"{tag} entry {index}: semantic name offset {name_off} outside string region"
            )
        end = payload.find(b"\0", name_off)
        if end < 0:
            raise DxbcSignatureError(f"{tag} entry {index}: unterminated semantic name")
        try:
            name = payload[name_off:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DxbcSignatureError(f"{tag} entry {index}: semantic name is not UTF-8") from exc
        if not name:
            raise DxbcSignatureError(f"{tag} entry {index}: empty semantic name")
        if register in seen_registers:
            raise DxbcSignatureError(
                f"{tag}: multiple signature rows claim register {register}; component-split signatures unsupported"
            )
        seen_registers.add(register)
        mask = mask_rw & 0xFF
        rw_mask = (mask_rw >> 8) & 0xFF
        rows.append({
            "entryIndex": index,
            "register": int(register),
            "semanticName": name,
            "semanticIndex": int(semantic_index),
            "semantic": f"{name}{semantic_index}",
            "systemValue": int(system_value),
            "componentType": int(component_type),
            "mask": int(mask),
            "readWriteMask": int(rw_mask),
        })
    rows.sort(key=lambda row: row["register"])
    return {
        "format": FORMAT,
        "tag": tag,
        "headerUnknown": int(unknown),
        "entryCount": len(rows),
        "entries": rows,
        "registerMap": {str(row["register"]): row["semantic"] for row in rows},
    }


def parse_io_signatures(blob: bytes) -> dict:
    return {
        "format": "t6-dxbc-io-signatures-v1",
        "input": parse_signature(blob, "ISGN"),
        "output": parse_signature(blob, "OSGN"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("shader", type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    result = parse_io_signatures(a.shader.read_bytes())
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
