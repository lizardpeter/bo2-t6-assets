#!/usr/bin/env python3
"""Build a byte-exact T6 IPAK LZO command corpus from a proven retail entry.

This is intentionally based on the repository's public t6_ipak_http_range_v1.py
grammar. It emits only compressed LZO commands plus liblzo2-decoded reference
bytes for performance/correctness comparison.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import json
import struct
from pathlib import Path

IPAK_VERSION = 0x50000
IPAK_INDEX = 1
IPAK_DATA = 2
ALIGN = 0x80
CMD_RAW = 0x00
CMD_LZO = 0x01
CMD_SKIP = 0xCF


def align_up(n: int, a: int) -> int:
    return (n + a - 1) // a * a


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ipak", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--name-hash", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--data-hash", type=lambda x: int(x, 0), required=True)
    a = ap.parse_args()

    data = a.ipak.read_bytes()
    if len(data) < 16:
        raise SystemExit("IPAK too small")
    magic, version, declared_size, section_count = struct.unpack_from("<4sIII", data, 0)
    if magic != b"KAPI" or version != IPAK_VERSION:
        raise SystemExit(f"bad IPAK header {magic!r} 0x{version:X}")
    if declared_size != len(data):
        raise SystemExit(f"declared size {declared_size} != file size {len(data)}")

    sections = [
        struct.unpack_from("<IIII", data, 16 + i * 16)
        for i in range(section_count)
    ]
    index_sections = [s for s in sections if s[0] == IPAK_INDEX]
    data_sections = [s for s in sections if s[0] == IPAK_DATA]
    if len(index_sections) != 1 or len(data_sections) != 1:
        raise SystemExit("expected exactly one index and one data section")
    _, index_off, index_size, index_count = index_sections[0]
    _, data_off, data_size, _ = data_sections[0]
    if index_count * 16 > index_size:
        raise SystemExit("index count exceeds section")

    target = None
    nh = a.name_hash & 0xFFFFFFFF
    dh = a.data_hash & 0x1FFFFFFF
    for i in range(index_count):
        entry = struct.unpack_from("<IIII", data, index_off + i * 16)
        data_hash, name_hash, rel_off, raw_size = entry
        if name_hash == nh and (data_hash & 0x1FFFFFFF) == dh:
            if target is not None:
                raise SystemExit("duplicate exact pair")
            target = entry
    if target is None:
        raise SystemExit("exact IPAK pair not found")

    data_hash, name_hash, rel_off, raw_size = target
    pos = data_off + rel_off
    end = pos + raw_size
    if end > data_off + data_size or end > len(data):
        raise SystemExit("entry range escapes data section")

    lib = ctypes.util.find_library("lzo2")
    if not lib:
        raise SystemExit("liblzo2 not found")
    dec = ctypes.CDLL(lib).lzo1x_decompress_safe
    dec.argtypes = [
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_void_p,
    ]
    dec.restype = ctypes.c_int

    a.out.mkdir(parents=True, exist_ok=True)
    blocks = []
    full = bytearray()
    lzo_index = 0
    block_index = 0
    while pos < end:
        pos = align_up(pos, ALIGN)
        if pos >= end:
            break
        hdr = data[pos:pos + 128]
        if len(hdr) != 128:
            raise SystemExit("truncated block header")
        first = struct.unpack_from("<I", hdr, 0)[0]
        file_off = first & 0xFFFFFF
        count = first >> 24
        if count > 31:
            raise SystemExit(f"invalid command count {count}")
        commands = []
        for i in range(count):
            word = struct.unpack_from("<I", hdr, 4 + i * 4)[0]
            commands.append((word & 0xFFFFFF, word >> 24))
        if any(kind in (CMD_RAW, CMD_LZO) for _, kind in commands) and file_off != len(full):
            raise SystemExit(f"output offset mismatch {file_off} != {len(full)}")
        payload_size = sum(size for size, _ in commands)
        payload = data[pos + 128:pos + 128 + payload_size]
        if len(payload) != payload_size:
            raise SystemExit("truncated block payload")
        cursor = 0
        for command_index, (size, kind) in enumerate(commands):
            blob = payload[cursor:cursor + size]
            if len(blob) != size:
                raise SystemExit("truncated command")
            if kind == CMD_RAW:
                full.extend(blob)
            elif kind == CMD_LZO:
                dst = ctypes.create_string_buffer(0x8000)
                out_len = ctypes.c_size_t(0x8000)
                src = ctypes.create_string_buffer(blob)
                rc = dec(src, len(blob), dst, ctypes.byref(out_len), None)
                if rc != 0:
                    raise SystemExit(f"liblzo2 failed rc={rc}")
                raw = dst.raw[:out_len.value]
                comp_name = f"{lzo_index:04d}.lzo"
                raw_name = f"{lzo_index:04d}.raw"
                (a.out / comp_name).write_bytes(blob)
                (a.out / raw_name).write_bytes(raw)
                blocks.append({
                    "index": lzo_index,
                    "block": block_index,
                    "command": command_index,
                    "compressedBytes": len(blob),
                    "decodedBytes": len(raw),
                    "compressedSha256": sha256(blob),
                    "decodedSha256": sha256(raw),
                })
                full.extend(raw)
                lzo_index += 1
            elif kind == CMD_SKIP:
                pass
            else:
                raise SystemExit(f"unsupported command 0x{kind:02X}")
            cursor += size
        pos += 128 + payload_size
        block_index += 1

    crc29 = __import__("zlib").crc32(full) & 0x1FFFFFFF
    if crc29 != dh:
        raise SystemExit(f"CRC29 0x{crc29:08X} != 0x{dh:08X}")

    manifest = {
        "format": "t6-ipak-lzo-command-corpus-v1",
        "sourceFile": a.ipak.name,
        "sourceSha256": sha256(data),
        "nameHash": nh,
        "dataHash": dh,
        "entry": list(target),
        "entryDecodedBytes": len(full),
        "entryDecodedSha256": sha256(bytes(full)),
        "lzoCommandCount": len(blocks),
        "lzoCompressedBytes": sum(x["compressedBytes"] for x in blocks),
        "lzoDecodedBytes": sum(x["decodedBytes"] for x in blocks),
        "commands": blocks,
    }
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
