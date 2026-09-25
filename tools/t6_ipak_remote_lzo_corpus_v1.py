#!/usr/bin/env python3
"""Collect real LZO commands from a remote retail T6 IPAK using HTTP ranges."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import json
import struct
from pathlib import Path

from t6_ipak_http_range_v1 import HttpRangeSource

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
    ap.add_argument("url")
    ap.add_argument("out", type=Path)
    ap.add_argument("--limit", type=int, default=128)
    a = ap.parse_args()
    if a.limit <= 0:
        raise SystemExit("--limit must be positive")

    source = HttpRangeSource(a.url)
    head = source.read_at(0, 16)
    magic, version, declared_size, section_count = struct.unpack("<4sIII", head)
    if magic != b"KAPI" or version != IPAK_VERSION:
        raise SystemExit(f"bad IPAK header {magic!r} 0x{version:X}")
    if source.total_size != declared_size:
        raise SystemExit("remote/declaration size mismatch")

    sec_raw = source.read_at(16, section_count * 16)
    sections = [
        struct.unpack_from("<IIII", sec_raw, i * 16)
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

    index_raw = source.read_at(index_off, index_count * 16)
    entries = [
        struct.unpack_from("<IIII", index_raw, i * 16)
        for i in range(index_count)
    ]

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
    commands = []

    for entry_index, entry in enumerate(entries):
        if len(commands) >= a.limit:
            break
        data_hash, name_hash, rel_off, raw_size = entry
        absolute_start = data_off + rel_off
        absolute_end = absolute_start + raw_size
        if absolute_end > data_off + data_size or absolute_end > declared_size:
            raise SystemExit(f"entry {entry_index} escapes data section")

        entry_bytes = source.read_at(absolute_start, raw_size)
        relative = 0
        while relative < raw_size and len(commands) < a.limit:
            absolute = absolute_start + relative
            aligned = align_up(absolute, ALIGN)
            relative += aligned - absolute
            if relative >= raw_size:
                break

            hdr_end = relative + 128
            hdr = entry_bytes[relative:hdr_end]
            if len(hdr) != 128:
                raise SystemExit(f"entry {entry_index} truncated block header")
            first = struct.unpack_from("<I", hdr, 0)[0]
            count = first >> 24
            if count > 31:
                raise SystemExit(f"entry {entry_index} invalid command count {count}")
            words = [
                struct.unpack_from("<I", hdr, 4 + i * 4)[0]
                for i in range(count)
            ]
            specs = [(w & 0xFFFFFF, w >> 24) for w in words]
            payload_size = sum(size for size, _ in specs)
            payload_start = hdr_end
            payload_end = payload_start + payload_size
            payload = entry_bytes[payload_start:payload_end]
            if len(payload) != payload_size:
                raise SystemExit(f"entry {entry_index} truncated payload")

            cursor = 0
            for command_index, (size, kind) in enumerate(specs):
                blob = payload[cursor:cursor + size]
                if kind == CMD_LZO:
                    dst = ctypes.create_string_buffer(0x8000)
                    out_len = ctypes.c_size_t(0x8000)
                    src = ctypes.create_string_buffer(blob)
                    rc = dec(src, len(blob), dst, ctypes.byref(out_len), None)
                    if rc != 0:
                        raise SystemExit(
                            f"liblzo2 entry={entry_index} command={command_index} rc={rc}"
                        )
                    raw = dst.raw[:out_len.value]
                    idx = len(commands)
                    (a.out / f"{idx:04d}.lzo").write_bytes(blob)
                    (a.out / f"{idx:04d}.raw").write_bytes(raw)
                    commands.append({
                        "index": idx,
                        "entryIndex": entry_index,
                        "parentDataHash": data_hash & 0x1FFFFFFF,
                        "parentNameHash": name_hash,
                        "command": command_index,
                        "compressedBytes": len(blob),
                        "decodedBytes": len(raw),
                        "compressedSha256": sha256(blob),
                        "decodedSha256": sha256(raw),
                    })
                    if len(commands) >= a.limit:
                        break
                elif kind not in (CMD_RAW, CMD_SKIP):
                    raise SystemExit(f"unsupported T6 IPAK command 0x{kind:02X}")
                cursor += size

            relative = payload_end

    if not commands:
        raise SystemExit("no LZO commands found")
    manifest = {
        "format": "t6-ipak-remote-lzo-command-corpus-v1",
        "url": a.url,
        "remoteBytes": declared_size,
        "entryCount": index_count,
        "rangeRequests": source.requests,
        "rangeBytesFetched": source.bytes_fetched,
        "lzoCommandCount": len(commands),
        "lzoCompressedBytes": sum(x["compressedBytes"] for x in commands),
        "lzoDecodedBytes": sum(x["decodedBytes"] for x in commands),
        "commands": commands,
    }
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
