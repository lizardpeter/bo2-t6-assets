#!/usr/bin/env python3
"""Range-backed retail T6 IPAK reader.

Reads only the IPAK header, section table, index, and compressed blocks required
for requested entries.  Intended for exact extraction from mirrors such as
https://r2.houseofkublai.com/bo2/ without downloading multi-GB shared IPAKs.

Identity is fail-closed: callers can address entries by the retail pair
(nameHash, dataHash) or by a unique dataHash.  Extracted bytes must reproduce
the IPAK entry's 29-bit CRC identity.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import json
import struct
import urllib.request
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Iterable

IPAK_MAGIC = b"KAPI"
IPAK_VERSION = 0x50000
IPAK_INDEX = 1
IPAK_DATA = 2
IPAK_BLOCK_ALIGN = 0x80


def align_up(n: int, a: int) -> int:
    return (n + a - 1) // a * a


def r_hash_string(s: str, h: int = 0) -> int:
    for c in s.encode("latin1"):
        h = ((33 * h) ^ (c | 0x20)) & 0xFFFFFFFF
    return h


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class HttpRangeSource:
    def __init__(self, url: str, timeout: int = 60):
        self.url = url
        self.timeout = timeout
        self.requests = 0
        self.bytes_fetched = 0
        self.total_size: int | None = None

    def read_at(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0:
            raise ValueError("negative range")
        if size == 0:
            return b""
        end = offset + size - 1
        req = urllib.request.Request(
            self.url,
            headers={"Range": f"bytes={offset}-{end}", "User-Agent": "bo2-t6-assets-range-reader/1"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            status = getattr(r, "status", None)
            if status != 206:
                raise ValueError(f"server did not honor Range request: HTTP {status}")
            cr = r.headers.get("Content-Range")
            if not cr or not cr.startswith("bytes ") or "/" not in cr:
                raise ValueError(f"missing/invalid Content-Range: {cr!r}")
            spec, total = cr[6:].split("/", 1)
            got_start, got_end = map(int, spec.split("-", 1))
            if (got_start, got_end) != (offset, end):
                raise ValueError(f"range mismatch {(got_start, got_end)} != {(offset, end)}")
            if total != "*":
                total_i = int(total)
                if self.total_size is not None and total_i != self.total_size:
                    raise ValueError("remote object size changed during extraction")
                self.total_size = total_i
            data = r.read(size + 1)
        if len(data) != size:
            raise ValueError(f"short range read {offset}+{size}: got {len(data)}")
        self.requests += 1
        self.bytes_fetched += len(data)
        return data


class T6IPakRange:
    def __init__(self, source: HttpRangeSource):
        self.source = source
        head = source.read_at(0, 16)
        magic, version, declared_size, section_count = struct.unpack("<4sIII", head)
        if magic != IPAK_MAGIC or version != IPAK_VERSION:
            raise ValueError(f"invalid T6 IPAK header magic={magic!r} version=0x{version:X}")
        if source.total_size is None:
            raise ValueError("remote total size unavailable")
        if declared_size != source.total_size:
            raise ValueError(f"IPAK declared/remote size mismatch {declared_size} != {source.total_size}")
        self.size = declared_size
        self.section_count = section_count
        sec_raw = source.read_at(16, section_count * 16)
        self.sections = [struct.unpack_from("<IIII", sec_raw, i * 16) for i in range(section_count)]
        data_sections = [s for s in self.sections if s[0] == IPAK_DATA]
        index_sections = [s for s in self.sections if s[0] == IPAK_INDEX]
        if len(data_sections) != 1 or len(index_sections) != 1:
            raise ValueError("expected exactly one IPAK data and index section")
        self.data_section = data_sections[0]
        self.index_section = index_sections[0]
        _, index_offset, index_size, index_count = self.index_section
        if index_count * 16 > index_size:
            raise ValueError("IPAK index count exceeds index section")
        index_raw = source.read_at(index_offset, index_count * 16)
        self.entries: list[tuple[int, int, int, int]] = [
            struct.unpack_from("<IIII", index_raw, i * 16) for i in range(index_count)
        ]
        self.by_pair: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        self.by_name: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
        self.by_data: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
        for e in self.entries:
            data_hash, name_hash, _, _ = e
            key = (name_hash, data_hash)
            if key in self.by_pair:
                raise ValueError(f"duplicate exact IPAK key {key}")
            self.by_pair[key] = e
            self.by_name[name_hash].append(e)
            self.by_data[data_hash].append(e)
        lib = ctypes.util.find_library("lzo2")
        if not lib:
            raise RuntimeError("liblzo2 not found")
        self._lzo = ctypes.CDLL(lib).lzo1x_decompress_safe
        self._lzo.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
        self._lzo.restype = ctypes.c_int

    @property
    def url(self) -> str:
        return self.source.url

    def entry_exact(self, name_hash: int, data_hash: int):
        return self.by_pair.get((name_hash & 0xFFFFFFFF, data_hash & 0x1FFFFFFF))

    def entry_for_name(self, image_name: str, data_hash: int | None = None):
        nh = r_hash_string(image_name)
        if data_hash is None:
            rows = self.by_name.get(nh, [])
            if len(rows) != 1:
                return None
            return rows[0]
        return self.entry_exact(nh, data_hash)

    def entry_unique_datahash(self, data_hash: int):
        rows = self.by_data.get(data_hash & 0x1FFFFFFF, [])
        return rows[0] if len(rows) == 1 else None

    def extract_entry(self, entry: tuple[int, int, int, int]) -> bytes:
        data_hash, _name_hash, rel_off, raw_size = entry
        data_base = self.data_section[1]
        pos = data_base + rel_off
        end = pos + raw_size
        out = bytearray()
        blocks = 0
        while pos < end:
            pos = align_up(pos, IPAK_BLOCK_ALIGN)
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
            if any(comp in (0, 1) for _, comp in commands) and file_off != len(out):
                raise ValueError(f"IPAK block output offset mismatch {file_off} != {len(out)}")
            payload_size = sum(sz for sz, _ in commands)
            payload = self.source.read_at(pos + 128, payload_size)
            p = 0
            for sz, comp in commands:
                blob = payload[p:p + sz]
                if comp == 0:
                    out.extend(blob)
                elif comp == 1:
                    dst = ctypes.create_string_buffer(0x8000)
                    n = ctypes.c_size_t(0x8000)
                    src = ctypes.create_string_buffer(blob)
                    rc = self._lzo(src, len(blob), dst, ctypes.byref(n), None)
                    if rc != 0:
                        raise ValueError(f"LZO error {rc}")
                    out.extend(dst.raw[:n.value])
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

    def describe(self) -> dict:
        return {
            "url": self.url,
            "bytes": self.size,
            "sectionCount": self.section_count,
            "entryCount": len(self.entries),
            "uniqueNameHashCount": len(self.by_name),
            "uniqueDataHashCount": len(self.by_data),
            "rangeRequests": self.source.requests,
            "rangeBytesFetched": self.source.bytes_fetched,
        }


def open_ipak(url: str) -> T6IPakRange:
    return T6IPakRange(HttpRangeSource(url))


def load_pairs(path: Path) -> list[dict]:
    doc = json.loads(path.read_text())
    rows = doc.get("pairs") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise ValueError("pair manifest must be a list or {pairs:[...]}")
    out = []
    for row in rows:
        if not isinstance(row, dict) or "dataHash" not in row:
            raise ValueError(f"invalid pair row {row!r}")
        r = dict(row)
        if "nameHash" not in r:
            if not r.get("image"):
                raise ValueError("pair row needs nameHash or image")
            r["nameHash"] = r_hash_string(r["image"])
        r["nameHash"] = int(r["nameHash"]) & 0xFFFFFFFF
        r["dataHash"] = int(r["dataHash"]) & 0x1FFFFFFF
        out.append(r)
    return out


def audit_pairs(pairs: Iterable[dict], ipaks: list[T6IPakRange]) -> dict:
    rows = []
    exact = unique_data = missing = ambiguous = 0
    for pair in pairs:
        hits = []
        for ipak in ipaks:
            e = ipak.entry_exact(pair["nameHash"], pair["dataHash"])
            if e:
                hits.append({"url": ipak.url, "identityResolution": "exact-nameHash-dataHash", "entry": e})
        if not hits:
            for ipak in ipaks:
                e = ipak.entry_unique_datahash(pair["dataHash"])
                if e:
                    hits.append({"url": ipak.url, "identityResolution": "unique-dataHash", "entry": e})
        if len(hits) == 1:
            if hits[0]["identityResolution"] == "exact-nameHash-dataHash":
                exact += 1
            else:
                unique_data += 1
            status = "resolved"
        elif not hits:
            missing += 1
            status = "missing"
        else:
            ambiguous += 1
            status = "ambiguous"
        rows.append({**pair, "status": status, "matches": hits})
    return {
        "summary": {
            "pairCount": len(rows),
            "resolvedExactPair": exact,
            "resolvedUniqueDataHash": unique_data,
            "missing": missing,
            "ambiguous": ambiguous,
        },
        "pairs": rows,
        "containers": [i.describe() for i in ipaks],
        "proofBoundary": "Exact pair resolution is preferred. Unique-dataHash fallback is admitted only when exactly one supplied IPAK contains that 29-bit payload identity; extraction still requires decompressed CRC29 equality. No filename similarity or nearest-entry fallback is used.",
    }


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
        if a.name_hash is not None:
            e = ipak.entry_exact(a.name_hash, a.data_hash)
        else:
            e = ipak.entry_unique_datahash(a.data_hash)
        if e is None:
            raise SystemExit("requested IPAK identity is absent or non-unique")
        raw = ipak.extract_entry(e)
        a.out.write_bytes(raw)
        print(json.dumps({"entry": e, "bytes": len(raw), "sha256": sha256(raw), **ipak.describe()}, indent=2, sort_keys=True))
        return 0
    pairs = load_pairs(a.pairs)
    ipaks = [open_ipak(u) for u in a.urls]
    report = audit_pairs(pairs, ipaks)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
