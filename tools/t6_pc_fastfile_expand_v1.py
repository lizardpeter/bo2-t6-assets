#!/usr/bin/env python3
"""Expand official signed BO2/T6 PC TAff0100 fastfiles.

This is a small fail-closed implementation of the retail loading transform used
by T6 PC v147:

  TAff0100 / PHEEBs71
    -> four round-robin XChunk streams
    -> Salsa20 decryption with Treyarch's PC T6 key
    -> per-stream OAT-compatible SHA1/IV evolution
    -> raw-DEFLATE decompression
    -> expanded XFile byte stream

The constants and transform are pinned against OpenAssetTools commit
7d027e8f89118196713e955b0e11f8404149c54d.  This tool does not verify the RSA
signature itself; that fact is explicit in its proof output.  It does require
the signed retail magic/version/auth header and every chunk to decrypt/inflate
cleanly.  Any malformed chunk fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

KEY = bytes([
    0x64, 0x1D, 0x8A, 0x2F, 0xE3, 0x1D, 0x3A, 0xA6,
    0x36, 0x22, 0xBB, 0xC9, 0xCE, 0x85, 0x87, 0x22,
    0x9D, 0x42, 0xB0, 0xF8, 0xED, 0x9B, 0x92, 0x41,
    0x30, 0xBF, 0x88, 0xB6, 0x5E, 0xDC, 0x50, 0xBE,
])
STREAMS = 4
BLOCK_HASH_COUNT = 200
SHA1_BYTES = 20
XCHUNK_SIZE = 0x8000
PC_VERSION = 147
MAGIC = b"TAff0100"
AUTH_MAGIC = b"PHEEBs71"
OAT_COMMIT = "7d027e8f89118196713e955b0e11f8404149c54d"


def _rotl(v: int, n: int) -> int:
    return ((v << n) & 0xFFFFFFFF) | (v >> (32 - n))


def _salsa20_block(key: bytes, nonce: bytes, counter: int) -> bytes:
    if len(key) != 32 or len(nonce) != 8:
        raise ValueError("Salsa20 requires 32-byte key and 8-byte nonce")
    sigma = b"expand 32-byte k"
    k = list(struct.unpack("<8I", key))
    c = list(struct.unpack("<4I", sigma))
    n = list(struct.unpack("<2I", nonce))
    x = [
        c[0], k[0], k[1], k[2], k[3], c[1], n[0], n[1],
        counter & 0xFFFFFFFF, (counter >> 32) & 0xFFFFFFFF,
        c[2], k[4], k[5], k[6], k[7], c[3],
    ]
    z = x[:]
    for _ in range(10):
        z[4] ^= _rotl((z[0] + z[12]) & 0xFFFFFFFF, 7)
        z[8] ^= _rotl((z[4] + z[0]) & 0xFFFFFFFF, 9)
        z[12] ^= _rotl((z[8] + z[4]) & 0xFFFFFFFF, 13)
        z[0] ^= _rotl((z[12] + z[8]) & 0xFFFFFFFF, 18)
        z[9] ^= _rotl((z[5] + z[1]) & 0xFFFFFFFF, 7)
        z[13] ^= _rotl((z[9] + z[5]) & 0xFFFFFFFF, 9)
        z[1] ^= _rotl((z[13] + z[9]) & 0xFFFFFFFF, 13)
        z[5] ^= _rotl((z[1] + z[13]) & 0xFFFFFFFF, 18)
        z[14] ^= _rotl((z[10] + z[6]) & 0xFFFFFFFF, 7)
        z[2] ^= _rotl((z[14] + z[10]) & 0xFFFFFFFF, 9)
        z[6] ^= _rotl((z[2] + z[14]) & 0xFFFFFFFF, 13)
        z[10] ^= _rotl((z[6] + z[2]) & 0xFFFFFFFF, 18)
        z[3] ^= _rotl((z[15] + z[11]) & 0xFFFFFFFF, 7)
        z[7] ^= _rotl((z[3] + z[15]) & 0xFFFFFFFF, 9)
        z[11] ^= _rotl((z[7] + z[3]) & 0xFFFFFFFF, 13)
        z[15] ^= _rotl((z[11] + z[7]) & 0xFFFFFFFF, 18)
        z[1] ^= _rotl((z[0] + z[3]) & 0xFFFFFFFF, 7)
        z[2] ^= _rotl((z[1] + z[0]) & 0xFFFFFFFF, 9)
        z[3] ^= _rotl((z[2] + z[1]) & 0xFFFFFFFF, 13)
        z[0] ^= _rotl((z[3] + z[2]) & 0xFFFFFFFF, 18)
        z[6] ^= _rotl((z[5] + z[4]) & 0xFFFFFFFF, 7)
        z[7] ^= _rotl((z[6] + z[5]) & 0xFFFFFFFF, 9)
        z[4] ^= _rotl((z[7] + z[6]) & 0xFFFFFFFF, 13)
        z[5] ^= _rotl((z[4] + z[7]) & 0xFFFFFFFF, 18)
        z[11] ^= _rotl((z[10] + z[9]) & 0xFFFFFFFF, 7)
        z[8] ^= _rotl((z[11] + z[10]) & 0xFFFFFFFF, 9)
        z[9] ^= _rotl((z[8] + z[11]) & 0xFFFFFFFF, 13)
        z[10] ^= _rotl((z[9] + z[8]) & 0xFFFFFFFF, 18)
        z[12] ^= _rotl((z[15] + z[14]) & 0xFFFFFFFF, 7)
        z[13] ^= _rotl((z[12] + z[15]) & 0xFFFFFFFF, 9)
        z[14] ^= _rotl((z[13] + z[12]) & 0xFFFFFFFF, 13)
        z[15] ^= _rotl((z[14] + z[13]) & 0xFFFFFFFF, 18)
    return struct.pack("<16I", *[((z[i] + x[i]) & 0xFFFFFFFF) for i in range(16)])


def _salsa_xor(payload: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray(len(payload))
    pos = 0
    counter = 0
    while pos < len(payload):
        stream = _salsa20_block(key, nonce, counter)
        counter += 1
        take = min(64, len(payload) - pos)
        for i in range(take):
            out[pos + i] = payload[pos + i] ^ stream[i]
        pos += take
    return bytes(out)


def _initial_hash_blocks(zone_name: str) -> bytearray:
    raw = zone_name[:31].encode("ascii")
    if not raw:
        raise ValueError("empty T6 zone name")
    out = bytearray(BLOCK_HASH_COUNT * STREAMS * SHA1_BYTES)
    j = 0
    for i in range(0, len(out), 4):
        out[i:i + 4] = bytes([raw[j]]) * 4
        j = (j + 1) % len(raw)
    return out


def _hash_block(buf: bytearray, indices: list[int], stream: int) -> memoryview:
    off = indices[stream] * STREAMS * SHA1_BYTES + stream * SHA1_BYTES
    return memoryview(buf)[off:off + SHA1_BYTES]


def expand_fastfile(source: Path, output: Path) -> dict:
    raw = source.read_bytes()
    if len(raw) < 312:
        raise ValueError("fastfile too small for signed T6 PC header")
    if raw[:8] != MAGIC:
        raise ValueError(f"unsupported T6 magic {raw[:8]!r}")
    version = struct.unpack_from("<I", raw, 8)[0]
    if version != PC_VERSION:
        raise ValueError(f"expected T6 PC zone version {PC_VERSION}, got {version}")
    if raw[12:20] != AUTH_MAGIC:
        raise ValueError("T6 signed auth magic mismatch")

    zone_name = raw[24:56].split(b"\0", 1)[0].decode("ascii")
    # Signed header layout: magic/version + auth + auth field + 32-byte name + 256-byte RSA signature.
    source_pos = 12 + 8 + 4 + 32 + 256
    hash_blocks = _initial_hash_blocks(zone_name)
    stream_indices = [0] * STREAMS
    expanded = bytearray()
    records = []
    chunk_index = 0
    terminal_size_offset = None

    while source_pos + 4 <= len(raw):
        size_offset = source_pos
        chunk_size = struct.unpack_from("<I", raw, source_pos)[0]
        source_pos += 4
        if chunk_size == 0:
            terminal_size_offset = size_offset
            break
        if chunk_size > XCHUNK_SIZE or source_pos + chunk_size > len(raw):
            raise ValueError(f"invalid chunk size {chunk_size} at 0x{size_offset:X}")

        encrypted = raw[source_pos:source_pos + chunk_size]
        source_pos += chunk_size
        stream = chunk_index % STREAMS
        current_hash = _hash_block(hash_blocks, stream_indices, stream)
        iv = bytes(current_hash[:8])
        compressed = _salsa_xor(encrypted, KEY, iv)
        try:
            plain = zlib.decompress(compressed, wbits=-15)
        except zlib.error as exc:
            raise RuntimeError(
                f"chunk {chunk_index} stream {stream} raw-DEFLATE failed at 0x{size_offset:X}: {exc}"
            ) from exc
        if len(plain) > XCHUNK_SIZE:
            raise ValueError(f"chunk {chunk_index} inflated beyond XChunk size")

        expanded_offset = len(expanded)
        expanded.extend(plain)
        digest = hashlib.sha1(compressed).digest()
        stream_indices[stream] = (stream_indices[stream] + 1) % BLOCK_HASH_COUNT
        upcoming_hash = _hash_block(hash_blocks, stream_indices, stream)
        for i, value in enumerate(digest):
            upcoming_hash[i] ^= value

        records.append({
            "chunk": chunk_index,
            "stream": stream,
            "rawSizeOffset": size_offset,
            "compressedEncryptedBytes": chunk_size,
            "expandedOffset": expanded_offset,
            "expandedBytes": len(plain),
            "iv": iv.hex(),
            "decryptedCompressedSha1": digest.hex(),
        })
        chunk_index += 1

    if terminal_size_offset is None:
        raise ValueError("T6 XChunk stream has no zero-size terminator")

    suffix = raw[source_pos:]
    suffix_all_zero = all(value == 0 for value in suffix)
    if not suffix_all_zero:
        raise ValueError("non-zero bytes after terminal XChunk")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(expanded)
    proof = {
        "format": "t6-pc-fastfile-expand-proof-v1",
        "authority": "deterministic transform of supplied signed-format T6 PC bytes",
        "source": {
            "path": str(source),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "zoneName": zone_name,
            "magic": MAGIC.decode("ascii"),
            "version": version,
            "authMagic": AUTH_MAGIC.decode("ascii"),
            "signatureVerificationPerformed": False,
        },
        "expanded": {
            "path": str(output),
            "bytes": len(expanded),
            "sha256": hashlib.sha256(expanded).hexdigest(),
        },
        "chunks": {
            "count": chunk_index,
            "terminalSizeOffset": terminal_size_offset,
            "remainingSuffixBytes": len(suffix),
            "remainingSuffixAllZero": suffix_all_zero,
            "records": records,
        },
        "algorithm": {
            "referenceRepository": "Laupetin/OpenAssetTools",
            "referenceCommit": OAT_COMMIT,
            "streams": STREAMS,
            "xchunkSize": XCHUNK_SIZE,
            "compression": "raw DEFLATE",
            "encryption": "Salsa20/20",
            "ivEvolution": "zone-name initialized 200x4 SHA1 blocks; SHA1(decrypted compressed chunk) XORed into next per-stream block",
        },
    }
    proof_path = output.with_suffix(output.suffix + ".proof.json")
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    proof = expand_fastfile(args.input, args.output)
    print(json.dumps({
        "source": proof["source"],
        "expanded": proof["expanded"],
        "chunkCount": proof["chunks"]["count"],
        "remainingSuffixBytes": proof["chunks"]["remainingSuffixBytes"],
        "remainingSuffixAllZero": proof["chunks"]["remainingSuffixAllZero"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
