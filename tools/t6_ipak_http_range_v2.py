#!/usr/bin/env python3
"""Range-backed retail T6 IPAK reader v2.

v2 preserves the exact-pair/CRC29 behavior of v1 and adds the retail IPAK
padding command used by shared containers.  T6 treats command 0xCF as a file
skip: the command's byte range is consumed from the IPAK stream but contributes
no bytes to the reconstructed image payload.  Unknown command values remain a
hard error so extraction fails closed rather than silently accepting a format
we have not source-closed.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import struct
import zlib
from pathlib import Path

import t6_ipak_http_range_v1 as v1

IPAK_COMMAND_UNCOMPRESSED = 0x00
IPAK_COMMAND_LZO = 0x01
IPAK_COMMAND_SKIP = 0xCF


class T6IPakRangeV2(v1.T6IPakRange):
    def extract_entry(self, entry: tuple[int, int, int, int]) -> bytes:
        data_hash, _name_hash, rel_off, raw_size = entry
        data_base = self.data_section[1]
        pos = data_base + rel_off
        end = pos + raw_size
        out = bytearray()
        blocks = 0

        while pos < end:
            pos = v1.align_up(pos, v1.IPAK_BLOCK_ALIGN)
            if pos >= end:
                break

            hdr = self.source.read_at(pos, 128)
            command_word = struct.unpack_from("<I", hdr, 0)[0]
            file_off = command_word & 0xFFFFFF
            command_count = (command_word >> 24) & 0xFF
            if command_count > 31:
                raise ValueError(f"invalid IPAK command count {command_count}")

            commands = []
            for i in range(command_count):
                word = struct.unpack_from("<I", hdr, 4 + i * 4)[0]
                commands.append((word & 0xFFFFFF, (word >> 24) & 0xFF))

            # The retail loader only requires the output/file offset to agree
            # for commands that actually emit image bytes.  Skip commands are
            # padding and intentionally do not advance the reconstructed file.
            if any(comp in (IPAK_COMMAND_UNCOMPRESSED, IPAK_COMMAND_LZO) for _, comp in commands):
                if file_off != len(out):
                    raise ValueError(f"IPAK block output offset mismatch {file_off} != {len(out)}")

            payload_size = sum(sz for sz, _ in commands)
            payload = self.source.read_at(pos + 128, payload_size)
            p = 0
            for sz, comp in commands:
                blob = payload[p:p + sz]
                if len(blob) != sz:
                    raise ValueError("truncated IPAK command payload")
                if comp == IPAK_COMMAND_UNCOMPRESSED:
                    out.extend(blob)
                elif comp == IPAK_COMMAND_LZO:
                    dst = ctypes.create_string_buffer(0x8000)
                    n = ctypes.c_size_t(0x8000)
                    src = ctypes.create_string_buffer(blob)
                    rc = self._lzo(src, len(blob), dst, ctypes.byref(n), None)
                    if rc != 0:
                        raise ValueError(f"LZO error {rc}")
                    out.extend(dst.raw[:n.value])
                elif comp == IPAK_COMMAND_SKIP:
                    # Retail padding: consume source bytes, emit nothing.
                    pass
                else:
                    raise ValueError(f"unsupported IPAK compression command {comp}")
                p += sz

            pos += 128 + payload_size
            blocks += 1
            if blocks > 10000:
                raise ValueError("IPAK block runaway")

        result = bytes(out)
        crc29 = zlib.crc32(result) & 0x1FFFFFFF
        if crc29 != data_hash:
            raise ValueError(f"IPAK CRC29 mismatch {crc29:08X} != {data_hash:08X}")
        return result


def open_ipak(url: str) -> T6IPakRangeV2:
    return T6IPakRangeV2(v1.HttpRangeSource(url))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_info = sub.add_parser("info")
    p_info.add_argument("url")
    p_extract = sub.add_parser("extract-datahash")
    p_extract.add_argument("url")
    p_extract.add_argument("data_hash", type=lambda x: int(x, 0))
    p_extract.add_argument("out", type=Path)
    p_extract.add_argument("--name-hash", type=lambda x: int(x, 0))
    p_audit = sub.add_parser("audit-pairs")
    p_audit.add_argument("pairs", type=Path)
    p_audit.add_argument("out", type=Path)
    p_audit.add_argument("urls", nargs="+")
    a = ap.parse_args()

    if a.cmd == "info":
        ipak = open_ipak(a.url)
        print(json.dumps(ipak.describe(), indent=2, sort_keys=True))
        return 0

    if a.cmd == "extract-datahash":
        ipak = open_ipak(a.url)
        e = ipak.entry_exact(a.name_hash, a.data_hash) if a.name_hash is not None else ipak.entry_unique_datahash(a.data_hash)
        if e is None:
            raise SystemExit("requested IPAK identity is absent or non-unique")
        raw = ipak.extract_entry(e)
        a.out.write_bytes(raw)
        print(json.dumps({"entry": e, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), **ipak.describe()}, indent=2, sort_keys=True))
        return 0

    pairs = v1.load_pairs(a.pairs)
    ipaks = [open_ipak(u) for u in a.urls]
    report = v1.audit_pairs(pairs, ipaks)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
