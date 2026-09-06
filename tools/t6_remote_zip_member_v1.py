#!/usr/bin/env python3
"""Fetch exact members from a very large remote ZIP using HTTP Range requests.

Designed for the public Plutonium T6 archive without downloading the complete
~45 GB ZIP.  The reader parses EOCD/ZIP64 EOCD and the central directory, then
requires each requested basename to resolve uniquely.  Member data is copied in
bounded range chunks and hashed while streaming.

This is transport only.  It does not reinterpret T6 content and it never picks
between duplicate basenames heuristically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

EOCD_SIG = 0x06054B50
ZIP64_LOCATOR_SIG = 0x07064B50
ZIP64_EOCD_SIG = 0x06064B50
CENTRAL_SIG = 0x02014B50
LOCAL_SIG = 0x04034B50
ZIP64_EXTRA_ID = 0x0001
MAX_EOCD_SEARCH = 22 + 0xFFFF


class RemoteZipError(RuntimeError):
    pass


@dataclass(frozen=True)
class Entry:
    name: str
    method: int
    flags: int
    crc32: int
    compressed_size: int
    uncompressed_size: int
    local_header_offset: int


class RangeReader:
    def __init__(self, url: str, length: int | None = None):
        self.url = url
        self.length = length if length is not None else self._discover_length()
        if self.length <= 0:
            raise RemoteZipError(f"invalid remote length {self.length}")

    def _request(self, *, method: str = "GET", range_value: str | None = None):
        headers = {"Accept-Encoding": "identity", "User-Agent": "bo2-t6-assets-range-v1"}
        if range_value is not None:
            headers["Range"] = range_value
        req = urllib.request.Request(self.url, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=120)

    def _discover_length(self) -> int:
        try:
            with self._request(method="HEAD") as r:
                raw = r.headers.get("Content-Length")
                if raw:
                    return int(raw)
        except Exception:
            pass
        with self._request(range_value="bytes=0-0") as r:
            cr = r.headers.get("Content-Range", "")
            m = re.fullmatch(r"bytes\s+0-0/(\d+)", cr.strip())
            if not m:
                raise RemoteZipError(f"server did not expose total length: {cr!r}")
            return int(m.group(1))

    def read(self, start: int, size: int) -> bytes:
        if size < 0 or start < 0 or start + size > self.length:
            raise RemoteZipError(f"range out of bounds start={start} size={size} length={self.length}")
        if size == 0:
            return b""
        end = start + size - 1
        with self._request(range_value=f"bytes={start}-{end}") as r:
            status = getattr(r, "status", None)
            data = r.read()
            cr = r.headers.get("Content-Range")
        if status != 206:
            raise RemoteZipError(f"range request returned HTTP {status}, expected 206")
        if len(data) != size:
            raise RemoteZipError(f"range {start}-{end} returned {len(data)} bytes, expected {size}")
        expected_cr = f"bytes {start}-{end}/{self.length}"
        if cr and cr.strip() != expected_cr:
            raise RemoteZipError(f"unexpected Content-Range {cr!r}, expected {expected_cr!r}")
        return data

    def copy(self, start: int, size: int, output: Path, chunk_size: int) -> str:
        h = hashlib.sha256()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as f:
            done = 0
            while done < size:
                n = min(chunk_size, size - done)
                block = self.read(start + done, n)
                f.write(block)
                h.update(block)
                done += n
        return h.hexdigest()


def _u16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def _u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def _u64(b: bytes, off: int) -> int:
    return struct.unpack_from("<Q", b, off)[0]


def locate_central_directory(reader: RangeReader) -> tuple[int, int, int]:
    tail_size = min(reader.length, MAX_EOCD_SEARCH)
    tail_start = reader.length - tail_size
    tail = reader.read(tail_start, tail_size)
    sig = struct.pack("<I", EOCD_SIG)
    rel = tail.rfind(sig)
    if rel < 0 or rel + 22 > len(tail):
        raise RemoteZipError("EOCD not found in legal trailing window")
    eocd_abs = tail_start + rel
    comment_len = _u16(tail, rel + 20)
    if rel + 22 + comment_len != len(tail):
        # There can be bytes before EOCD in the fetched tail, but nothing after
        # the exact comment except the end of file.
        if eocd_abs + 22 + comment_len != reader.length:
            raise RemoteZipError("EOCD comment length does not terminate at EOF")
    disk = _u16(tail, rel + 4)
    cd_disk = _u16(tail, rel + 6)
    entries_disk = _u16(tail, rel + 8)
    entries_total = _u16(tail, rel + 10)
    cd_size32 = _u32(tail, rel + 12)
    cd_off32 = _u32(tail, rel + 16)
    if disk != 0 or cd_disk != 0:
        raise RemoteZipError("multi-disk ZIP archives are unsupported")

    needs_zip64 = (
        entries_disk == 0xFFFF or entries_total == 0xFFFF
        or cd_size32 == 0xFFFFFFFF or cd_off32 == 0xFFFFFFFF
    )
    if not needs_zip64:
        if entries_disk != entries_total:
            raise RemoteZipError("EOCD per-disk and total entry counts disagree")
        return cd_off32, cd_size32, entries_total

    locator_off = eocd_abs - 20
    if locator_off < 0:
        raise RemoteZipError("ZIP64 locator missing before EOCD")
    locator = reader.read(locator_off, 20)
    if _u32(locator, 0) != ZIP64_LOCATOR_SIG:
        raise RemoteZipError("ZIP64 locator signature missing")
    zip64_disk = _u32(locator, 4)
    zip64_eocd_off = _u64(locator, 8)
    total_disks = _u32(locator, 16)
    if zip64_disk != 0 or total_disks != 1:
        raise RemoteZipError("multi-disk ZIP64 archives are unsupported")
    z = reader.read(zip64_eocd_off, 56)
    if _u32(z, 0) != ZIP64_EOCD_SIG:
        raise RemoteZipError("ZIP64 EOCD signature missing")
    record_size = _u64(z, 4)
    if record_size < 44:
        raise RemoteZipError(f"invalid ZIP64 EOCD record size {record_size}")
    disk = _u32(z, 16)
    cd_disk = _u32(z, 20)
    entries_disk64 = _u64(z, 24)
    entries_total64 = _u64(z, 32)
    cd_size64 = _u64(z, 40)
    cd_off64 = _u64(z, 48)
    if disk != 0 or cd_disk != 0 or entries_disk64 != entries_total64:
        raise RemoteZipError("unsupported multi-disk ZIP64 central directory")
    return cd_off64, cd_size64, entries_total64


def _zip64_values(extra: bytes, need_uncomp: bool, need_comp: bool, need_off: bool) -> tuple[int | None, int | None, int | None]:
    pos = 0
    payload = None
    while pos + 4 <= len(extra):
        field_id, field_len = struct.unpack_from("<HH", extra, pos)
        pos += 4
        end = pos + field_len
        if end > len(extra):
            raise RemoteZipError("truncated central-directory extra field")
        if field_id == ZIP64_EXTRA_ID:
            payload = extra[pos:end]
            break
        pos = end
    if payload is None:
        raise RemoteZipError("ZIP64 central entry is missing ZIP64 extra data")
    p = 0
    values: list[int | None] = []
    for needed in (need_uncomp, need_comp, need_off):
        if needed:
            if p + 8 > len(payload):
                raise RemoteZipError("truncated ZIP64 extra value")
            values.append(_u64(payload, p))
            p += 8
        else:
            values.append(None)
    return values[0], values[1], values[2]


def parse_central_directory(blob: bytes, expected_entries: int | None = None) -> list[Entry]:
    entries: list[Entry] = []
    pos = 0
    while pos < len(blob):
        if pos + 46 > len(blob) or _u32(blob, pos) != CENTRAL_SIG:
            raise RemoteZipError(f"bad central-directory signature at relative 0x{pos:X}")
        flags = _u16(blob, pos + 8)
        method = _u16(blob, pos + 10)
        crc32 = _u32(blob, pos + 16)
        comp32 = _u32(blob, pos + 20)
        uncomp32 = _u32(blob, pos + 24)
        name_len = _u16(blob, pos + 28)
        extra_len = _u16(blob, pos + 30)
        comment_len = _u16(blob, pos + 32)
        disk_start = _u16(blob, pos + 34)
        local32 = _u32(blob, pos + 42)
        end = pos + 46 + name_len + extra_len + comment_len
        if end > len(blob):
            raise RemoteZipError("truncated central-directory record")
        raw_name = blob[pos + 46:pos + 46 + name_len]
        encoding = "utf-8" if flags & 0x800 else "cp437"
        name = raw_name.decode(encoding)
        extra = blob[pos + 46 + name_len:pos + 46 + name_len + extra_len]
        if disk_start not in (0, 0xFFFF):
            raise RemoteZipError(f"entry {name!r} starts on unsupported disk {disk_start}")
        need_uncomp = uncomp32 == 0xFFFFFFFF
        need_comp = comp32 == 0xFFFFFFFF
        need_off = local32 == 0xFFFFFFFF
        if need_uncomp or need_comp or need_off:
            zu, zc, zo = _zip64_values(extra, need_uncomp, need_comp, need_off)
            uncomp = int(zu if need_uncomp else uncomp32)
            comp = int(zc if need_comp else comp32)
            local = int(zo if need_off else local32)
        else:
            uncomp, comp, local = uncomp32, comp32, local32
        entries.append(Entry(name, method, flags, crc32, comp, uncomp, local))
        pos = end
    if expected_entries is not None and len(entries) != expected_entries:
        raise RemoteZipError(f"central directory parsed {len(entries)} entries, expected {expected_entries}")
    return entries


def central_entries(reader: RangeReader, max_cd_bytes: int) -> tuple[list[Entry], dict]:
    cd_off, cd_size, count = locate_central_directory(reader)
    if cd_size > max_cd_bytes:
        raise RemoteZipError(f"central directory {cd_size} exceeds configured maximum {max_cd_bytes}")
    if cd_off + cd_size > reader.length:
        raise RemoteZipError("central directory range lies outside remote file")
    blob = reader.read(cd_off, cd_size)
    entries = parse_central_directory(blob, count)
    return entries, {"offset": cd_off, "bytes": cd_size, "entries": count}


def resolve_basename(entries: list[Entry], basename: str) -> Entry:
    hits = [e for e in entries if PurePosixPath(e.name).name == basename]
    if not hits:
        raise RemoteZipError(f"basename {basename!r} not found")
    if len(hits) != 1:
        raise RemoteZipError(f"basename {basename!r} is ambiguous: {[e.name for e in hits]}")
    return hits[0]


def local_data_offset(reader: RangeReader, entry: Entry) -> int:
    h = reader.read(entry.local_header_offset, 30)
    if _u32(h, 0) != LOCAL_SIG:
        raise RemoteZipError(f"{entry.name}: bad local-header signature")
    flags = _u16(h, 6)
    method = _u16(h, 8)
    name_len = _u16(h, 26)
    extra_len = _u16(h, 28)
    if method != entry.method or flags != entry.flags:
        raise RemoteZipError(f"{entry.name}: local/central method or flags disagree")
    name_bytes = reader.read(entry.local_header_offset + 30, name_len)
    encoding = "utf-8" if flags & 0x800 else "cp437"
    if name_bytes.decode(encoding) != entry.name:
        raise RemoteZipError(f"{entry.name}: local/central names disagree")
    return entry.local_header_offset + 30 + name_len + extra_len


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--length", type=int)
    ap.add_argument("--basename", action="append", required=True, help="unique member basename; repeatable")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--expect", action="append", default=[], help="BASENAME=SIZE:SHA256")
    ap.add_argument("--chunk-mib", type=int, default=16)
    ap.add_argument("--max-central-directory-mib", type=int, default=128)
    ap.add_argument("--allow-compressed", action="store_true")
    a = ap.parse_args()

    expected: dict[str, tuple[int, str]] = {}
    for raw in a.expect:
        try:
            name, spec = raw.split("=", 1)
            size_s, digest = spec.split(":", 1)
            expected[name] = (int(size_s), digest.lower())
        except Exception as exc:
            raise SystemExit(f"invalid --expect {raw!r}; expected BASENAME=SIZE:SHA256") from exc
        if not re.fullmatch(r"[0-9a-f]{64}", expected[name][1]):
            raise SystemExit(f"invalid SHA-256 in --expect {raw!r}")

    reader = RangeReader(a.url, a.length)
    entries, cd = central_entries(reader, a.max_central_directory_mib * 1024 * 1024)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "format": "t6-remote-zip-member-fetch-v1",
        "url": a.url,
        "remoteBytes": reader.length,
        "centralDirectory": cd,
        "members": [],
    }
    for basename in a.basename:
        entry = resolve_basename(entries, basename)
        if entry.method != 0 and not a.allow_compressed:
            raise RemoteZipError(f"{entry.name}: compression method {entry.method}, expected STORED (0)")
        if entry.method != 0:
            raise RemoteZipError("compressed-member extraction is intentionally not implemented in v1")
        if entry.compressed_size != entry.uncompressed_size:
            raise RemoteZipError(f"{entry.name}: STORED member size mismatch")
        if basename in expected and entry.uncompressed_size != expected[basename][0]:
            raise RemoteZipError(
                f"{entry.name}: central-directory size {entry.uncompressed_size} != expected {expected[basename][0]}"
            )
        data_off = local_data_offset(reader, entry)
        out = a.out_dir / basename
        digest = reader.copy(data_off, entry.compressed_size, out, a.chunk_mib * 1024 * 1024)
        if basename in expected and digest != expected[basename][1]:
            raise RemoteZipError(f"{entry.name}: SHA-256 {digest} != expected {expected[basename][1]}")
        result["members"].append({
            "basename": basename,
            "zipPath": entry.name,
            "method": entry.method,
            "crc32Hex": f"{entry.crc32:08x}",
            "localHeaderOffset": entry.local_header_offset,
            "dataOffset": data_off,
            "bytes": entry.uncompressed_size,
            "sha256": digest,
            "output": str(out),
            "expectedValidated": basename in expected,
        })
        print(json.dumps(result["members"][-1], sort_keys=True), file=sys.stderr)

    manifest = a.out_dir / "remote_zip_fetch_manifest.json"
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest), "members": len(result["members"]), "centralDirectory": cd}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RemoteZipError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
