#!/usr/bin/env python3
"""Safely probe a remote ZIP/ZIP64 central directory for canonical T6 FastFiles.

The probe never downloads the archive payload. Every GET is an explicit byte
range and the response status/Content-Range are validated before reading the
body. ZIP64 EOCD is supported because full retail-game archives can exceed the
classic 32-bit ZIP offsets.
"""
from __future__ import annotations

import argparse
import json
import struct
import urllib.request
from pathlib import Path

EOCD_SIG = b"PK\x05\x06"
ZIP64_LOCATOR_SIG = b"PK\x06\x07"
ZIP64_EOCD_SIG = b"PK\x06\x06"
CENTRAL_SIG = b"PK\x01\x02"
MAX_EOCD_TAIL = 22 + 0xFFFF
MAX_CENTRAL_BYTES = 128 * 1024 * 1024


def request(url: str, *, start: int, end: int, user_agent: str) -> tuple[bytes, dict[str, str]]:
    if start < 0 or end < start:
        raise ValueError(f"invalid range {start}-{end}")
    expected = end - start + 1
    req = urllib.request.Request(
        url,
        headers={"Range": f"bytes={start}-{end}", "User-Agent": user_agent},
    )
    r = urllib.request.urlopen(req, timeout=60)
    try:
        status = getattr(r, "status", None)
        headers = {k.lower(): v for k, v in r.headers.items()}
        content_range = headers.get("content-range")
        if status != 206:
            raise RuntimeError(f"range request returned status {status}, expected 206")
        if not content_range or not content_range.lower().startswith(f"bytes {start}-{end}/"):
            raise RuntimeError(f"unexpected Content-Range {content_range!r} for {start}-{end}")
        if expected > MAX_CENTRAL_BYTES:
            raise RuntimeError(f"refusing oversized range read of {expected} bytes")
        data = r.read(expected + 1)
        if len(data) != expected:
            raise RuntimeError(f"range short/long read {len(data)} != {expected}")
        return data, headers
    finally:
        r.close()


def remote_size(url: str, user_agent: str) -> int:
    data, headers = request(url, start=0, end=0, user_agent=user_agent)
    if len(data) != 1:
        raise AssertionError("one-byte range did not return one byte")
    cr = headers["content-range"]
    total = int(cr.rsplit("/", 1)[1])
    if total <= 0:
        raise RuntimeError(f"invalid remote size {total}")
    return total


def parse_directory_location(url: str, total: int, user_agent: str) -> dict:
    tail_len = min(total, MAX_EOCD_TAIL)
    tail_start = total - tail_len
    tail, _ = request(url, start=tail_start, end=total - 1, user_agent=user_agent)
    rel = tail.rfind(EOCD_SIG)
    if rel < 0 or rel + 22 > len(tail):
        raise RuntimeError("classic EOCD not found in legal tail window")
    eocd_abs = tail_start + rel
    (
        disk,
        cd_disk,
        entries_disk,
        entries_total,
        cd_size32,
        cd_offset32,
        comment_len,
    ) = struct.unpack_from("<4H2LH", tail, rel + 4)
    if rel + 22 + comment_len != len(tail):
        # The tail can begin before the EOCD, but EOCD+comment must end at EOF.
        if eocd_abs + 22 + comment_len != total:
            raise RuntimeError("EOCD comment length does not land at EOF")
    if disk != 0 or cd_disk != 0:
        raise RuntimeError("multi-disk ZIP is unsupported")

    needs_zip64 = (
        entries_disk == 0xFFFF
        or entries_total == 0xFFFF
        or cd_size32 == 0xFFFFFFFF
        or cd_offset32 == 0xFFFFFFFF
    )
    if not needs_zip64:
        if entries_disk != entries_total:
            raise RuntimeError("classic EOCD entry-count mismatch")
        return {
            "zip64": False,
            "entries": entries_total,
            "centralSize": cd_size32,
            "centralOffset": cd_offset32,
            "eocdOffset": eocd_abs,
        }

    locator_off = eocd_abs - 20
    if locator_off < 0:
        raise RuntimeError("ZIP64 locator would precede archive")
    locator, _ = request(url, start=locator_off, end=locator_off + 19, user_agent=user_agent)
    if locator[:4] != ZIP64_LOCATOR_SIG:
        raise RuntimeError("ZIP64 locator signature missing")
    zip64_disk, zip64_eocd_off, total_disks = struct.unpack_from("<LQL", locator, 4)
    if zip64_disk != 0 or total_disks != 1:
        raise RuntimeError("multi-disk ZIP64 is unsupported")
    head, _ = request(url, start=zip64_eocd_off, end=zip64_eocd_off + 55, user_agent=user_agent)
    if head[:4] != ZIP64_EOCD_SIG:
        raise RuntimeError("ZIP64 EOCD signature missing")
    record_size = struct.unpack_from("<Q", head, 4)[0]
    if record_size < 44:
        raise RuntimeError(f"invalid ZIP64 EOCD record size {record_size}")
    (
        _version_made,
        _version_needed,
        disk64,
        cd_disk64,
        entries_disk64,
        entries_total64,
        cd_size64,
        cd_offset64,
    ) = struct.unpack_from("<2H2L4Q", head, 12)
    if disk64 != 0 or cd_disk64 != 0 or entries_disk64 != entries_total64:
        raise RuntimeError("ZIP64 multi-disk/count mismatch")
    return {
        "zip64": True,
        "entries": entries_total64,
        "centralSize": cd_size64,
        "centralOffset": cd_offset64,
        "eocdOffset": eocd_abs,
        "zip64EocdOffset": zip64_eocd_off,
        "zip64RecordSize": record_size,
    }


def canonical_zone_path(name: str) -> str | None:
    s = name.replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    if s.startswith("zone/"):
        return s
    marker = "/zone/"
    i = s.find(marker)
    if i >= 0:
        return s[i + 1 :]
    return None


def parse_central(data: bytes, declared_entries: int, wanted: set[str]) -> tuple[dict[str, dict], dict]:
    found: dict[str, dict] = {}
    seen_canonical: dict[str, list[str]] = {}
    o = 0
    entries = 0
    while o < len(data):
        if o + 46 > len(data) or data[o : o + 4] != CENTRAL_SIG:
            raise RuntimeError(f"invalid central-directory entry at offset {o}")
        (
            _version_made,
            _version_needed,
            flags,
            method,
            _mtime,
            _mdate,
            crc32,
            csize32,
            usize32,
            nlen,
            xlen,
            clen,
            _disk_start,
            _internal_attr,
            _external_attr,
            local_header_offset32,
        ) = struct.unpack_from("<6H3L5H2L", data, o + 4)
        end = o + 46 + nlen + xlen + clen
        if end > len(data):
            raise RuntimeError(f"central entry overruns directory at {o}")
        raw_name = data[o + 46 : o + 46 + nlen]
        encoding = "utf-8" if (flags & 0x800) else "cp437"
        name = raw_name.decode(encoding, "replace")
        canon = canonical_zone_path(name)
        extra = data[o + 46 + nlen : o + 46 + nlen + xlen]
        csize = csize32
        usize = usize32
        local_header_offset = local_header_offset32
        if 0xFFFFFFFF in (csize32, usize32, local_header_offset32):
            p = 0
            while p + 4 <= len(extra):
                tag, sz = struct.unpack_from("<HH", extra, p)
                body = extra[p + 4 : p + 4 + sz]
                if len(body) != sz:
                    raise RuntimeError("truncated ZIP extra field")
                if tag == 0x0001:
                    q = 0
                    if usize32 == 0xFFFFFFFF:
                        usize = struct.unpack_from("<Q", body, q)[0]
                        q += 8
                    if csize32 == 0xFFFFFFFF:
                        csize = struct.unpack_from("<Q", body, q)[0]
                        q += 8
                    if local_header_offset32 == 0xFFFFFFFF:
                        local_header_offset = struct.unpack_from("<Q", body, q)[0]
                    break
                p += 4 + sz
        if canon is not None:
            seen_canonical.setdefault(canon, []).append(name)
            if canon in wanted:
                row = {
                    "archiveName": name,
                    "crc32": f"{crc32:08x}",
                    "compressedBytes": int(csize),
                    "uncompressedBytes": int(usize),
                    "method": method,
                    "flags": flags,
                    "localHeaderOffset": int(local_header_offset),
                }
                old = found.get(canon)
                if old is not None and old != row:
                    raise RuntimeError(f"catalog path {canon} occurs with conflicting central records")
                found[canon] = row
        o = end
        entries += 1
    if o != len(data):
        raise RuntimeError("central-directory parser did not end exactly")
    if entries != declared_entries:
        raise RuntimeError(f"central entry count {entries} != declared {declared_entries}")
    duplicate_zone_names = {k: v for k, v in seen_canonical.items() if len(v) > 1}
    return found, {"parsedEntries": entries, "duplicateCanonicalZonePaths": duplicate_zone_names}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--paths", type=Path, required=True)
    ap.add_argument("--out-tsv", type=Path, required=True)
    ap.add_argument("--out-meta", type=Path, required=True)
    a = ap.parse_args()
    wanted = {line.strip() for line in a.paths.read_text(encoding="utf-8").splitlines() if line.strip()}
    if not wanted:
        raise SystemExit("empty wanted path set")
    ua = "bo2-t6-assets-safe-zip-range-probe/2"
    total = remote_size(a.url, ua)
    loc = parse_directory_location(a.url, total, ua)
    cd_size = int(loc["centralSize"])
    cd_off = int(loc["centralOffset"])
    if cd_size <= 0 or cd_size > MAX_CENTRAL_BYTES:
        raise SystemExit(f"central directory size {cd_size} outside safe range")
    if cd_off < 0 or cd_off + cd_size > total:
        raise SystemExit("central directory outside remote archive")
    central, _ = request(a.url, start=cd_off, end=cd_off + cd_size - 1, user_agent=ua)
    found, parsed = parse_central(central, int(loc["entries"]), wanted)
    a.out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with a.out_tsv.open("w", encoding="utf-8") as f:
        for path in sorted(wanted):
            row = found.get(path)
            if row is None:
                f.write(f"{path}\tunavailable\t-\t-\t-\t-\t-\t-\t{a.url}\n")
            else:
                f.write(
                    f"{path}\tpresent\t{row['uncompressedBytes']}\t{row['crc32']}\t"
                    f"{row['compressedBytes']}\t{row['method']}\t{row['flags']}\t"
                    f"{row['localHeaderOffset']}\t{a.url}\n"
                )
    meta = {
        "format": "t6-public-zip-ff-catalog-probe-v2",
        "url": a.url,
        "remoteZipBytes": total,
        "catalogPaths": len(wanted),
        "present": len(found),
        "unavailable": len(wanted - set(found)),
        "directory": loc,
        **parsed,
        "safety": {
            "requires206BeforeBodyRead": True,
            "maxCentralReadBytes": MAX_CENTRAL_BYTES,
            "archivePayloadDownloaded": False,
        },
    }
    a.out_meta.parent.mkdir(parents=True, exist_ok=True)
    a.out_meta.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
