#!/usr/bin/env python3
"""Retail Black Ops II PC T6 FastFile expander v2.

This preserves the proven v1 Salsa20/SHA-1/raw-DEFLATE algorithm while adding
one native T6 XChunk framing rule that v1 omitted: the retail loader uses a
0x80000-byte vanilla input buffer. If the next 4-byte XChunk size field would
straddle that boundary, the remaining 1-3 bytes are consumed before the size
field is read at the next buffer start.

The rule is copied from pinned OpenAssetTools 9dca965366541504b71fa8cfb7ac049cb9b717e1
ProcessorXChunks::AdvanceStream with T6 ZoneConstants::VANILLA_BUFFER_SIZE.
No fitted zone-specific offset is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

import bo2_t6_fastfile as v1

VANILLA_BUFFER_SIZE = 0x80000


def parse_encrypted_records(ff: bytes):
    pos = v1.HEADER_SIZE
    record_index = 0
    while pos + 4 <= len(ff):
        boundary_offset = pos % VANILLA_BUFFER_SIZE
        skipped_before_length = 0
        skipped_offset = None
        if boundary_offset + 4 > VANILLA_BUFFER_SIZE:
            skipped_before_length = VANILLA_BUFFER_SIZE - boundary_offset
            skipped_offset = pos
            pos += skipped_before_length
            if pos + 4 > len(ff):
                if pos < len(ff) and any(ff[pos:]):
                    raise ValueError(f"truncated chunk-size field after vanilla-buffer boundary at 0x{pos:X}")
                return

        length_offset = pos
        encrypted_length = struct.unpack_from("<I", ff, pos)[0]
        pos += 4
        if encrypted_length == 0:
            if any(ff[length_offset + 4:]):
                raise ValueError(f"nonzero bytes after zero record marker at 0x{length_offset:X}")
            return
        if encrypted_length > v1.MAX_ENCRYPTED_RECORD:
            raise ValueError(
                f"record {record_index}: encrypted length 0x{encrypted_length:X} exceeds 0x8000"
            )
        end = pos + encrypted_length
        if end > len(ff):
            raise ValueError(f"record {record_index}: truncated ciphertext")
        yield {
            "record": record_index,
            "lengthFieldOffset": length_offset,
            "ciphertextOffset": pos,
            "ciphertext": ff[pos:end],
            "vanillaBoundarySkipOffset": skipped_offset,
            "vanillaBoundarySkipBytes": skipped_before_length,
        }
        pos = end
        record_index += 1
    if pos < len(ff) and any(ff[pos:]):
        raise ValueError(f"nonzero trailing bytes at 0x{pos:X}")


def decrypt_fastfile_bytes(ff: bytes):
    zone_name = v1.zone_name_from_file(ff)
    table = v1.initial_digest_table(zone_name)
    stream_counters = [0] * v1.STREAM_COUNT
    expanded_parts: list[bytes] = []
    audit = []
    boundary_skip_total = 0
    boundary_skip_events = 0

    for rec in parse_encrypted_records(ff):
        record_index = rec["record"]
        ciphertext = rec["ciphertext"]
        stream = record_index % v1.STREAM_COUNT
        counter_before = stream_counters[stream]
        table_index = (counter_before * v1.STREAM_COUNT + stream) % v1.TABLE_ENTRIES
        table_offset = table_index * v1.ENTRY_SIZE
        nonce = bytes(table[table_offset:table_offset + 8])
        plaintext = v1.salsa20_xor(ciphertext, v1.FASTFILE_KEY, nonce)
        try:
            expanded = zlib.decompress(plaintext, -15)
        except zlib.error as exc:
            raise ValueError(
                f"record {record_index} stream {stream}: raw-DEFLATE failed; nonce={nonce.hex()}"
            ) from exc

        digest = hashlib.sha1(plaintext).digest()
        next_counter = counter_before + 1
        next_table_index = (next_counter * v1.STREAM_COUNT + stream) % v1.TABLE_ENTRIES
        next_offset = next_table_index * v1.ENTRY_SIZE
        for i, value in enumerate(digest):
            table[next_offset + i] ^= value
        stream_counters[stream] = next_counter
        expanded_parts.append(expanded)

        skip = int(rec["vanillaBoundarySkipBytes"])
        if skip:
            boundary_skip_events += 1
            boundary_skip_total += skip
        audit.append({
            "record": record_index,
            "stream": stream,
            "streamCounterBefore": counter_before,
            "tableIndex": table_index,
            "nonceHex": nonce.hex(),
            "lengthFieldOffset": rec["lengthFieldOffset"],
            "ciphertextOffset": rec["ciphertextOffset"],
            "encryptedBytes": len(ciphertext),
            "expandedBytes": len(expanded),
            "plaintextSha1": digest.hex(),
            "vanillaBoundarySkipOffset": rec["vanillaBoundarySkipOffset"],
            "vanillaBoundarySkipBytes": skip,
        })

    expanded_stream = b"".join(expanded_parts)
    summary = {
        "format": "bo2-t6-fastfile-expand-v2",
        "zoneName": zone_name,
        "encryptedFileBytes": len(ff),
        "records": len(audit),
        "expandedStreamBytes": len(expanded_stream),
        "streamRecordCounts": stream_counters,
        "encryptedSha256": hashlib.sha256(ff).hexdigest(),
        "expandedSha256": hashlib.sha256(expanded_stream).hexdigest(),
        "vanillaBufferSize": VANILLA_BUFFER_SIZE,
        "vanillaBoundarySkipEvents": boundary_skip_events,
        "vanillaBoundarySkipBytes": boundary_skip_total,
    }
    return expanded_stream, audit, summary


def cmd_decrypt(args) -> None:
    src = Path(args.fastfile)
    expanded, audit, summary = decrypt_fastfile_bytes(src.read_bytes())
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(expanded)
    if args.audit:
        ap = Path(args.audit)
        ap.parent.mkdir(parents=True, exist_ok=True)
        ap.write_text(json.dumps({"summary": summary, "records": audit}, indent=2) + "\n", encoding="utf-8")
    summary["output"] = str(out)
    print(json.dumps(summary, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("decrypt")
    p.add_argument("fastfile")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--audit")
    p.set_defaults(func=cmd_decrypt)
    args = ap.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
