#!/usr/bin/env python3
"""Retail Black Ops II PC T6 fastfile decryptor + RawFile extractor.

This is the dependency-free reference implementation of the retail path recovered
from t6mp.exe:
- signed/encrypted XChunk records begin at file offset 0x138;
- four interleaved crypto streams (`record_index % 4`);
- Salsa20/20 with the exact 256-bit retail fastfile key;
- an 800 x 20-byte zone-name-derived nonce/digest table;
- SHA-1 plaintext-digest progression of the per-stream table entry;
- raw-DEFLATE inflation of every decrypted record.

The optional RawFile scanner recognizes the directly serialized retail form:
    FFFFFFFF, uint32 length, FFFFFFFF, name\0, content[length]

No OpenAssetTools executable is required and no network access is used.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

HEADER_SIZE = 0x138
MAX_ENCRYPTED_RECORD = 0x8000
STREAM_COUNT = 4
TABLE_ENTRIES = 800
ENTRY_SIZE = 20
TABLE_DWORDS = TABLE_ENTRIES * (ENTRY_SIZE // 4)
FASTFILE_KEY = bytes.fromhex(
    "641d8a2fe31d3aa63622bbc9ce858722"
    "9d42b0f8ed9b924130bf88b65edc50be"
)
SALSA_SIGMA = b"expand 32-byte k"
RAWFILE_SENTINEL = b"\xff\xff\xff\xff"
SAFE_NAME_RE = re.compile(r"[A-Za-z0-9_@+\-./:]+\Z")


def _rotl32(x: int, n: int) -> int:
    return ((x << n) & 0xFFFFFFFF) | (x >> (32 - n))


def salsa20_block(key: bytes, nonce: bytes, counter: int) -> bytes:
    if len(key) != 32 or len(nonce) != 8:
        raise ValueError("Salsa20 requires a 32-byte key and 8-byte nonce")
    k = struct.unpack("<8I", key)
    n = struct.unpack("<2I", nonce)
    c = struct.unpack("<4I", SALSA_SIGMA)
    initial = [
        c[0], k[0], k[1], k[2], k[3], c[1], n[0], n[1],
        counter & 0xFFFFFFFF, (counter >> 32) & 0xFFFFFFFF,
        c[2], k[4], k[5], k[6], k[7], c[3],
    ]
    x = initial.copy()
    for _ in range(10):
        # Column round.
        x[4] ^= _rotl32((x[0] + x[12]) & 0xFFFFFFFF, 7)
        x[8] ^= _rotl32((x[4] + x[0]) & 0xFFFFFFFF, 9)
        x[12] ^= _rotl32((x[8] + x[4]) & 0xFFFFFFFF, 13)
        x[0] ^= _rotl32((x[12] + x[8]) & 0xFFFFFFFF, 18)

        x[9] ^= _rotl32((x[5] + x[1]) & 0xFFFFFFFF, 7)
        x[13] ^= _rotl32((x[9] + x[5]) & 0xFFFFFFFF, 9)
        x[1] ^= _rotl32((x[13] + x[9]) & 0xFFFFFFFF, 13)
        x[5] ^= _rotl32((x[1] + x[13]) & 0xFFFFFFFF, 18)

        x[14] ^= _rotl32((x[10] + x[6]) & 0xFFFFFFFF, 7)
        x[2] ^= _rotl32((x[14] + x[10]) & 0xFFFFFFFF, 9)
        x[6] ^= _rotl32((x[2] + x[14]) & 0xFFFFFFFF, 13)
        x[10] ^= _rotl32((x[6] + x[2]) & 0xFFFFFFFF, 18)

        x[3] ^= _rotl32((x[15] + x[11]) & 0xFFFFFFFF, 7)
        x[7] ^= _rotl32((x[3] + x[15]) & 0xFFFFFFFF, 9)
        x[11] ^= _rotl32((x[7] + x[3]) & 0xFFFFFFFF, 13)
        x[15] ^= _rotl32((x[11] + x[7]) & 0xFFFFFFFF, 18)

        # Row round.
        x[1] ^= _rotl32((x[0] + x[3]) & 0xFFFFFFFF, 7)
        x[2] ^= _rotl32((x[1] + x[0]) & 0xFFFFFFFF, 9)
        x[3] ^= _rotl32((x[2] + x[1]) & 0xFFFFFFFF, 13)
        x[0] ^= _rotl32((x[3] + x[2]) & 0xFFFFFFFF, 18)

        x[6] ^= _rotl32((x[5] + x[4]) & 0xFFFFFFFF, 7)
        x[7] ^= _rotl32((x[6] + x[5]) & 0xFFFFFFFF, 9)
        x[4] ^= _rotl32((x[7] + x[6]) & 0xFFFFFFFF, 13)
        x[5] ^= _rotl32((x[4] + x[7]) & 0xFFFFFFFF, 18)

        x[11] ^= _rotl32((x[10] + x[9]) & 0xFFFFFFFF, 7)
        x[8] ^= _rotl32((x[11] + x[10]) & 0xFFFFFFFF, 9)
        x[9] ^= _rotl32((x[8] + x[11]) & 0xFFFFFFFF, 13)
        x[10] ^= _rotl32((x[9] + x[8]) & 0xFFFFFFFF, 18)

        x[12] ^= _rotl32((x[15] + x[14]) & 0xFFFFFFFF, 7)
        x[13] ^= _rotl32((x[12] + x[15]) & 0xFFFFFFFF, 9)
        x[14] ^= _rotl32((x[13] + x[12]) & 0xFFFFFFFF, 13)
        x[15] ^= _rotl32((x[14] + x[13]) & 0xFFFFFFFF, 18)

    return struct.pack(
        "<16I", *[((x[i] + initial[i]) & 0xFFFFFFFF) for i in range(16)]
    )


_SODIUM_SALSA20 = None
try:
    _sodium_name = ctypes.util.find_library("sodium")
    if _sodium_name:
        _sodium = ctypes.CDLL(_sodium_name)
        _fn = _sodium.crypto_stream_salsa20_xor
        _fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_void_p, ctypes.c_void_p]
        _fn.restype = ctypes.c_int
        _SODIUM_SALSA20 = _fn
except Exception:
    _SODIUM_SALSA20 = None


def salsa20_xor(data: bytes, key: bytes, nonce: bytes) -> bytes:
    if _SODIUM_SALSA20 is not None:
        out = ctypes.create_string_buffer(len(data))
        src = ctypes.create_string_buffer(data, max(1, len(data)))
        nbuf = ctypes.create_string_buffer(nonce, 8)
        kbuf = ctypes.create_string_buffer(key, 32)
        rc = _SODIUM_SALSA20(out, src, len(data), nbuf, kbuf)
        if rc == 0:
            return out.raw[:len(data)]
    out = bytearray(len(data))
    for block_index, offset in enumerate(range(0, len(data), 64)):
        stream = salsa20_block(key, nonce, block_index)
        chunk = data[offset:offset + 64]
        for j, value in enumerate(chunk):
            out[offset + j] = value ^ stream[j]
    return bytes(out)


def zone_name_from_file(ff: bytes) -> str:
    if len(ff) < HEADER_SIZE:
        raise ValueError("file is too small to be a T6 signed fastfile")
    if ff[:8] != b"TAff0100":
        raise ValueError(f"unexpected T6 fastfile magic: {ff[:8]!r}")
    raw = ff[24:56].split(b"\0", 1)[0]
    if not raw:
        raise ValueError("zone-name field is empty")
    return raw.decode("ascii")


def initial_digest_table(zone_name: str) -> bytearray:
    zone = zone_name.encode("ascii")
    if not zone:
        raise ValueError("empty zone name")
    table = bytearray(TABLE_ENTRIES * ENTRY_SIZE)
    for dword_index in range(TABLE_DWORDS):
        c = zone[dword_index % len(zone)]
        off = dword_index * 4
        table[off:off + 4] = bytes((c,)) * 4
    return table


def parse_encrypted_records(ff: bytes):
    pos = HEADER_SIZE
    record_index = 0
    while pos + 4 <= len(ff):
        length_offset = pos
        encrypted_length = struct.unpack_from("<I", ff, pos)[0]
        pos += 4
        if encrypted_length == 0:
            if any(ff[length_offset:]):
                raise ValueError(f"nonzero bytes after zero record marker at 0x{length_offset:X}")
            return
        if encrypted_length > MAX_ENCRYPTED_RECORD:
            raise ValueError(
                f"record {record_index}: encrypted length 0x{encrypted_length:X} exceeds 0x8000"
            )
        end = pos + encrypted_length
        if end > len(ff):
            raise ValueError(f"record {record_index}: truncated ciphertext")
        yield record_index, length_offset, pos, ff[pos:end]
        pos = end
        record_index += 1
    if pos < len(ff) and any(ff[pos:]):
        raise ValueError(f"nonzero trailing bytes at 0x{pos:X}")


def decrypt_fastfile_bytes(ff: bytes):
    zone_name = zone_name_from_file(ff)
    table = initial_digest_table(zone_name)
    stream_counters = [0] * STREAM_COUNT
    expanded_parts: list[bytes] = []
    audit = []
    for record_index, length_offset, data_offset, ciphertext in parse_encrypted_records(ff):
        stream = record_index % STREAM_COUNT
        counter_before = stream_counters[stream]
        table_index = (counter_before * STREAM_COUNT + stream) % TABLE_ENTRIES
        table_offset = table_index * ENTRY_SIZE
        nonce = bytes(table[table_offset:table_offset + 8])
        plaintext = salsa20_xor(ciphertext, FASTFILE_KEY, nonce)
        try:
            expanded = zlib.decompress(plaintext, -15)
        except zlib.error as exc:
            raise ValueError(
                f"record {record_index} stream {stream}: raw-DEFLATE failed; nonce={nonce.hex()}"
            ) from exc
        digest = hashlib.sha1(plaintext).digest()
        next_counter = counter_before + 1
        next_table_index = (next_counter * STREAM_COUNT + stream) % TABLE_ENTRIES
        next_offset = next_table_index * ENTRY_SIZE
        for i, value in enumerate(digest):
            table[next_offset + i] ^= value
        stream_counters[stream] = next_counter
        expanded_parts.append(expanded)
        audit.append({
            "record": record_index,
            "stream": stream,
            "streamCounterBefore": counter_before,
            "tableIndex": table_index,
            "nonceHex": nonce.hex(),
            "lengthFieldOffset": length_offset,
            "ciphertextOffset": data_offset,
            "encryptedBytes": len(ciphertext),
            "expandedBytes": len(expanded),
            "plaintextSha1": digest.hex(),
        })
    expanded_stream = b"".join(expanded_parts)
    summary = {
        "zoneName": zone_name,
        "encryptedFileBytes": len(ff),
        "records": len(audit),
        "expandedStreamBytes": len(expanded_stream),
        "streamRecordCounts": stream_counters,
        "encryptedSha256": hashlib.sha256(ff).hexdigest(),
        "expandedSha256": hashlib.sha256(expanded_stream).hexdigest(),
    }
    return expanded_stream, audit, summary


def _safe_rawfile_name(name: str) -> bool:
    if not (3 <= len(name) <= 260) or not SAFE_NAME_RE.fullmatch(name):
        return False
    if "\\" in name or name.startswith("/"):
        return False
    if not ("/" in name or "." in name):
        return False
    return not any(part in ("", ".", "..") for part in name.split("/"))


def scan_rawfiles(expanded: bytes, max_content_bytes: int = 32 * 1024 * 1024):
    results = []
    pos = 0
    limit = len(expanded)
    while pos + 12 <= limit:
        p = expanded.find(RAWFILE_SENTINEL, pos)
        if p < 0 or p + 12 > limit:
            break
        if expanded[p + 8:p + 12] != RAWFILE_SENTINEL:
            pos = p + 1
            continue
        length = struct.unpack_from("<I", expanded, p + 4)[0]
        if length > max_content_bytes:
            pos = p + 1
            continue
        name_start = p + 12
        name_end = expanded.find(b"\0", name_start, min(name_start + 512, limit))
        if name_end < 0:
            pos = p + 1
            continue
        try:
            name = expanded[name_start:name_end].decode("ascii")
        except UnicodeDecodeError:
            pos = p + 1
            continue
        if not _safe_rawfile_name(name):
            pos = p + 1
            continue
        content_start = name_end + 1
        content_end = content_start + length
        if content_end > limit:
            pos = p + 1
            continue
        content = expanded[content_start:content_end]
        results.append({
            "structOffset": p,
            "name": name,
            "length": length,
            "contentOffset": content_start,
            "contentEnd": content_end,
            "sha256": hashlib.sha256(content).hexdigest(),
            "content": content,
        })
        pos = content_end
    return results


def extract_rawfiles(expanded: bytes, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for record in scan_rawfiles(expanded):
        target = output_dir / Path(record["name"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(record["content"])
        item = {k: v for k, v in record.items() if k != "content"}
        item["outputPath"] = str(target)
        written.append(item)
    return written


def cmd_decrypt(args):
    src = Path(args.fastfile)
    expanded, audit, summary = decrypt_fastfile_bytes(src.read_bytes())
    output = Path(args.output) if args.output else src.with_suffix(src.suffix + ".expanded")
    output.write_bytes(expanded)
    if args.audit:
        Path(args.audit).write_text(json.dumps({"summary": summary, "records": audit}, indent=2) + "\n")
    print(json.dumps({**summary, "output": str(output)}, indent=2))


def cmd_all(args):
    src = Path(args.fastfile)
    expanded, audit, summary = decrypt_fastfile_bytes(src.read_bytes())
    root = Path(args.output_dir); root.mkdir(parents=True, exist_ok=True)
    expanded_path = root / (src.name + ".expanded")
    expanded_path.write_bytes(expanded)
    rawfiles = extract_rawfiles(expanded, root / "rawfiles")
    (root / "fastfile_audit.json").write_text(json.dumps({"summary": summary, "records": audit}, indent=2) + "\n")
    (root / "rawfile_inventory.json").write_text(json.dumps({"zoneName": summary["zoneName"], "rawfiles": rawfiles}, indent=2) + "\n")
    print(json.dumps({**summary, "expandedOutput": str(expanded_path), "rawfiles": len(rawfiles)}, indent=2))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("decrypt"); d.add_argument("fastfile"); d.add_argument("-o", "--output"); d.add_argument("--audit"); d.set_defaults(func=cmd_decrypt)
    a = sub.add_parser("all"); a.add_argument("fastfile"); a.add_argument("output_dir"); a.set_defaults(func=cmd_all)
    args = p.parse_args(); args.func(args); return 0


if __name__ == "__main__":
    raise SystemExit(main())
