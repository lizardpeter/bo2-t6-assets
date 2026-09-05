#!/usr/bin/env python3
"""Expand encrypted PC T6 FastFiles to the exact decompressed XFile stream.

This is a small audited reproduction of the T6 XChunk loading path used by the
pinned OpenAssetTools v0.33.0 source (commit
7d027e8f89118196713e955b0e11f8404149c54d):

* PC ZoneHeader: 8-byte magic + little-endian version 147
* official signed header: PHEEBs71 + 4 flags + 32-byte zone name + 256-byte sig
* four interleaved XChunk streams
* 32-bit little-endian encrypted chunk sizes, max 0x8000
* chunk-size field may not straddle a 0x80000 vanilla buffer boundary
* Salsa20 with the retail Treyarch PC key and an 8-byte evolving IV
* 200 SHA-1 hash blocks per stream; next hash block XORs SHA1(decrypted chunk)
* raw DEFLATE (zlib wbits=-15) after decryption
* zero chunk size / zero-padded file suffix terminates the stream

The tool is fail-closed when expected source/output identities are supplied.
It does not parse XAssets or alter the expanded bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

try:
    from Crypto.Cipher import Salsa20
except ImportError as exc:  # pragma: no cover - explicit operational dependency
    raise SystemExit("pycryptodome is required: python -m pip install pycryptodome") from exc

MAGIC_SIGNED_TREYARCH = b"TAff0100"
MAGIC_SIGNED_OAT = b"ABff0100"
MAGIC_UNSIGNED = b"TAffu100"
MAGIC_UNSIGNED_SERVER = b"TAsvu100"
MAGIC_AUTH_HEADER = b"PHEEBs71"
ZONE_VERSION_PC = 147
STREAM_COUNT = 4
XCHUNK_SIZE = 0x8000
VANILLA_BUFFER_SIZE = 0x80000
BLOCK_HASHES_COUNT = 200
SHA1_SIZE = 20
SALSA20_KEY_TREYARCH_PC = bytes([
    0x64, 0x1D, 0x8A, 0x2F, 0xE3, 0x1D, 0x3A, 0xA6,
    0x36, 0x22, 0xBB, 0xC9, 0xCE, 0x85, 0x87, 0x22,
    0x9D, 0x42, 0xB0, 0xF8, 0xED, 0x9B, 0x92, 0x41,
    0x30, 0xBF, 0x88, 0xB6, 0x5E, 0xDC, 0x50, 0xBE,
])


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def init_hash_blocks(zone_name: str) -> tuple[bytearray, list[int]]:
    if not zone_name:
        raise ValueError("empty zone name")
    name = zone_name[:31].encode("ascii")
    if not name:
        raise ValueError("zone name is not ASCII")
    total = BLOCK_HASHES_COUNT * STREAM_COUNT * SHA1_SIZE
    blocks = bytearray(total)
    name_index = 0
    # OAT initializes four bytes at a time with one repeated zone-name byte.
    for off in range(0, total, 4):
        blocks[off:off + 4] = bytes([name[name_index]]) * 4
        name_index = (name_index + 1) % len(name)
    return blocks, [0] * STREAM_COUNT


def hash_block_offset(stream: int, indices: list[int]) -> int:
    return (indices[stream] * STREAM_COUNT + stream) * SHA1_SIZE


def decrypt_chunk(
    encrypted: bytes,
    stream: int,
    hash_blocks: bytearray,
    indices: list[int],
) -> tuple[bytes, str, str]:
    off = hash_block_offset(stream, indices)
    iv = bytes(hash_blocks[off:off + 8])
    cipher = Salsa20.new(key=SALSA20_KEY_TREYARCH_PC, nonce=iv)
    decrypted = cipher.decrypt(encrypted)
    digest = hashlib.sha1(decrypted).digest()

    indices[stream] = (indices[stream] + 1) % BLOCK_HASHES_COUNT
    next_off = hash_block_offset(stream, indices)
    for i, b in enumerate(digest):
        hash_blocks[next_off + i] ^= b

    return decrypted, iv.hex(), digest.hex()


def parse_header(raw: bytes, zone_name: str) -> dict:
    if len(raw) < 12:
        raise ValueError("FastFile shorter than ZoneHeader")
    magic = raw[:8]
    version = struct.unpack_from("<I", raw, 8)[0]
    if version != ZONE_VERSION_PC:
        raise ValueError(f"unsupported T6 PC version {version}, expected {ZONE_VERSION_PC}")

    pos = 12
    signed = magic in (MAGIC_SIGNED_TREYARCH, MAGIC_SIGNED_OAT)
    encrypted = magic in (MAGIC_SIGNED_TREYARCH, MAGIC_SIGNED_OAT, MAGIC_UNSIGNED)
    official = magic in (MAGIC_SIGNED_TREYARCH, MAGIC_UNSIGNED_SERVER)
    if magic not in (MAGIC_SIGNED_TREYARCH, MAGIC_SIGNED_OAT, MAGIC_UNSIGNED, MAGIC_UNSIGNED_SERVER):
        raise ValueError(f"unsupported T6 magic {magic!r}")

    auth = None
    if signed:
        if len(raw) < pos + 300:
            raise ValueError("truncated signed auth header")
        if raw[pos:pos + 8] != MAGIC_AUTH_HEADER:
            raise ValueError(f"bad auth magic at 0x{pos:X}")
        flags = struct.unpack_from("<I", raw, pos + 8)[0]
        name_field = raw[pos + 12:pos + 44]
        file_name = name_field.split(b"\0", 1)[0].decode("ascii", errors="strict")
        if file_name != zone_name:
            raise ValueError(f"auth zone name {file_name!r} != expected {zone_name!r}")
        signature = raw[pos + 44:pos + 300]
        auth = {
            "magic": MAGIC_AUTH_HEADER.decode("ascii"),
            "flags": flags,
            "zoneName": file_name,
            "signatureBytes": len(signature),
            "signatureSha256": sha256_bytes(signature),
        }
        pos += 300

    return {
        "magic": magic.decode("ascii"),
        "version": version,
        "signed": signed,
        "encrypted": encrypted,
        "official": official,
        "auth": auth,
        "xchunkRawOffset": pos,
    }


def expand(raw: bytes, zone_name: str, *, collect_records: bool = False) -> tuple[bytes, dict]:
    header = parse_header(raw, zone_name)
    if not header["encrypted"]:
        raise ValueError("this v1 expander is intentionally scoped to encrypted PC T6 FastFiles")

    hash_blocks, indices = init_hash_blocks(zone_name)
    pos = int(header["xchunkRawOffset"])
    vanilla_offset = pos % VANILLA_BUFFER_SIZE
    out = bytearray()
    records = []
    stream_counts = [0] * STREAM_COUNT
    compressed_total = 0
    decrypted_total = 0
    decompressed_total = 0
    ordinal = 0
    termination = None

    while True:
        # ProcessorXChunks refuses to split the uint32 chunk-size field across
        # a 0x80000 vanilla buffer boundary. The writer fills the remainder
        # with zero bytes in exactly this case.
        if vanilla_offset + 4 > VANILLA_BUFFER_SIZE:
            skip = VANILLA_BUFFER_SIZE - vanilla_offset
            padding = raw[pos:pos + skip]
            if len(padding) != skip:
                termination = "eof-in-vanilla-wrap-padding"
                break
            if any(padding):
                raise ValueError(f"nonzero vanilla-wrap padding at 0x{pos:X}")
            pos += skip
            vanilla_offset = 0

        if pos + 4 > len(raw):
            termination = "physical-eof"
            break
        chunk_size = struct.unpack_from("<I", raw, pos)[0]
        size_offset = pos
        pos += 4
        vanilla_offset = (vanilla_offset + 4) % VANILLA_BUFFER_SIZE

        if chunk_size == 0:
            termination = "zero-chunk-size"
            break
        if chunk_size > XCHUNK_SIZE:
            raise ValueError(f"invalid encrypted chunk size {chunk_size} at 0x{size_offset:X}")
        if pos + chunk_size > len(raw):
            raise ValueError(f"truncated encrypted chunk {ordinal} at 0x{pos:X}")

        encrypted_chunk = raw[pos:pos + chunk_size]
        pos += chunk_size
        vanilla_offset = (vanilla_offset + chunk_size) % VANILLA_BUFFER_SIZE
        stream = ordinal % STREAM_COUNT

        decrypted, iv_hex, sha1_hex = decrypt_chunk(encrypted_chunk, stream, hash_blocks, indices)
        try:
            expanded = zlib.decompress(decrypted, wbits=-15)
        except zlib.error as exc:
            raise ValueError(
                f"raw-DEFLATE failed for chunk {ordinal} stream {stream} "
                f"raw=0x{size_offset:X} encryptedBytes={chunk_size}: {exc}"
            ) from exc
        if len(expanded) > XCHUNK_SIZE:
            raise ValueError(f"decompressed chunk {ordinal} is {len(expanded)} > 0x{XCHUNK_SIZE:X}")

        out.extend(expanded)
        stream_counts[stream] += 1
        compressed_total += chunk_size
        decrypted_total += len(decrypted)
        decompressed_total += len(expanded)
        if collect_records:
            records.append({
                "ordinal": ordinal,
                "stream": stream,
                "chunkSizeFieldRawOffset": size_offset,
                "encryptedRawOffset": size_offset + 4,
                "encryptedBytes": chunk_size,
                "encryptedSha256": sha256_bytes(encrypted_chunk),
                "salsa20Iv": iv_hex,
                "decryptedSha1": sha1_hex,
                "decompressedBytes": len(expanded),
                "decompressedSha256": sha256_bytes(expanded),
            })
        ordinal += 1

    meta = {
        "format": "t6-fastfile-expand-v1",
        "zoneName": zone_name,
        "header": header,
        "recordCount": ordinal,
        "streamRecordCounts": stream_counts,
        "encryptedChunkPayloadBytes": compressed_total,
        "decryptedCompressedBytes": decrypted_total,
        "expandedBytes": decompressed_total,
        "expandedSha256": sha256_bytes(bytes(out)),
        "termination": termination,
        "terminationRawOffset": pos,
        "finalVanillaBufferOffset": vanilla_offset,
        "finalStreamBlockIndices": indices,
        "records": records if collect_records else None,
        "proofBoundary": (
            "Reproduces the pinned OAT T6 PC encrypted XChunk transport only: signed-header framing, "
            "four-stream interleave, vanilla-buffer size-field wrap, Salsa20 IV/hash evolution, and raw "
            "DEFLATE. XAsset interpretation is outside this stage."
        ),
    }
    return bytes(out), meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fastfile", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--zone-name")
    ap.add_argument("--expected-raw-bytes", type=int)
    ap.add_argument("--expected-raw-sha256")
    ap.add_argument("--expected-expanded-bytes", type=int)
    ap.add_argument("--expected-expanded-sha256")
    ap.add_argument("--expected-record-count", type=int)
    ap.add_argument("--expected-stream-record-counts", help="comma-separated, e.g. 1183,1183,1182,1182")
    ap.add_argument("--records", action="store_true", help="retain per-chunk hashes in manifest")
    args = ap.parse_args()

    raw = args.fastfile.read_bytes()
    raw_sha = sha256_bytes(raw)
    if args.expected_raw_bytes is not None and len(raw) != args.expected_raw_bytes:
        raise SystemExit(f"raw byte count {len(raw)} != {args.expected_raw_bytes}")
    if args.expected_raw_sha256 and raw_sha.lower() != args.expected_raw_sha256.lower():
        raise SystemExit(f"raw SHA256 {raw_sha} != {args.expected_raw_sha256}")

    zone_name = args.zone_name or args.fastfile.stem
    expanded, meta = expand(raw, zone_name, collect_records=args.records)
    if args.expected_expanded_bytes is not None and len(expanded) != args.expected_expanded_bytes:
        raise SystemExit(f"expanded byte count {len(expanded)} != {args.expected_expanded_bytes}")
    if args.expected_expanded_sha256 and meta["expandedSha256"].lower() != args.expected_expanded_sha256.lower():
        raise SystemExit(f"expanded SHA256 {meta['expandedSha256']} != {args.expected_expanded_sha256}")
    if args.expected_record_count is not None and meta["recordCount"] != args.expected_record_count:
        raise SystemExit(f"record count {meta['recordCount']} != {args.expected_record_count}")
    if args.expected_stream_record_counts:
        expected = [int(v) for v in args.expected_stream_record_counts.split(",")]
        if meta["streamRecordCounts"] != expected:
            raise SystemExit(f"stream record counts {meta['streamRecordCounts']} != {expected}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(expanded)
    meta["source"] = {
        "file": args.fastfile.name,
        "bytes": len(raw),
        "sha256": raw_sha,
    }
    meta["output"] = {
        "file": args.out.name,
        "bytes": len(expanded),
        "sha256": meta["expandedSha256"],
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "zoneName": zone_name,
        "recordCount": meta["recordCount"],
        "streamRecordCounts": meta["streamRecordCounts"],
        "expandedBytes": len(expanded),
        "expandedSha256": meta["expandedSha256"],
        "termination": meta["termination"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
