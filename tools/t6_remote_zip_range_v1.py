#!/usr/bin/env python3
"""Minimal ZIP/ZIP64 central-directory reader and range extractor over HTTP.

Designed for large public T6 archive mirrors where downloading the entire ZIP is
unnecessary. The reader uses HTTP Range requests, supports classic and ZIP64
EOCD records plus ZIP64 per-entry size/offset extras, and can extract stored or
raw-DEFLATE entries.

Transport is fail-closed. Some CDNs intermittently ignore Range and answer 200
with the whole object. Such a response is never consumed as range data: its
Content-Length may be used only to establish object size, then the requested
range is retried. Successful partial reads must be HTTP 206 with an exact
Content-Range matching the requested byte interval.

This is transport/container code only. It does not infer game asset ownership.
"""
from __future__ import annotations

import binascii
import struct
import time
import urllib.error
import urllib.request
import zlib


class RemoteZipError(RuntimeError):
    pass


class RemoteZip:
    def __init__(
        self,
        url: str,
        user_agent: str = "bo2-t6-assets-remote-zip/1",
        timeout: int = 90,
        retries: int = 5,
    ):
        self.url = url
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = max(1, int(retries))
        self.total_bytes = None
        self.etag = None
        self._central = None
        self._metadata = None

    @staticmethod
    def _header(headers: dict, name: str):
        return headers.get(name) or headers.get(name.lower())

    def _remember_identity(self, headers: dict) -> None:
        etag = self._header(headers, "ETag")
        if etag:
            if self.etag is not None and etag != self.etag:
                raise RemoteZipError(f"remote object ETag changed: {self.etag!r} -> {etag!r}")
            self.etag = etag

    @staticmethod
    def _parse_content_range(value: str) -> tuple[int, int, int]:
        # Exact form required here: bytes START-END/TOTAL. Unsatisfied ranges are
        # not accepted because every caller asks for an in-bounds interval.
        try:
            unit, rest = value.strip().split(None, 1)
            span, total_s = rest.split("/", 1)
            start_s, end_s = span.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            total = int(total_s)
        except Exception as exc:
            raise RemoteZipError(f"malformed Content-Range {value!r}") from exc
        if unit.lower() != "bytes" or start < 0 or end < start or total <= end:
            raise RemoteZipError(f"invalid Content-Range {value!r}")
        return start, end, total

    def _size_from_headers(self, headers: dict) -> int | None:
        cr = self._header(headers, "Content-Range")
        if cr and "/" in cr:
            try:
                _a, _b, total = self._parse_content_range(cr)
            except RemoteZipError:
                total = None
            if total is not None:
                return total
        cl = self._header(headers, "Content-Length")
        if cl:
            try:
                n = int(cl)
            except ValueError:
                return None
            if n >= 0:
                return n
        return None

    def _head_size(self) -> int | None:
        req = urllib.request.Request(
            self.url,
            method="HEAD",
            headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                headers = dict(r.headers)
                self._remember_identity(headers)
                n = self._size_from_headers(headers)
                if n is not None and n > 0:
                    return n
        except (urllib.error.URLError, TimeoutError, OSError, RemoteZipError):
            return None
        return None

    def range(self, start: int, end: int) -> tuple[bytes, dict, int]:
        if start < 0 or end < start:
            raise RemoteZipError(f"invalid range {start}-{end}")
        expected = end - start + 1
        last_error: Exception | None = None

        for attempt in range(self.retries):
            headers_out = {
                "Range": f"bytes={start}-{end}",
                "User-Agent": self.user_agent,
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
            }
            if self.etag:
                headers_out["If-Range"] = self.etag
            req = urllib.request.Request(self.url, headers=headers_out)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    headers = dict(r.headers)
                    status = int(r.status)
                    self._remember_identity(headers)

                    if status == 206:
                        cr = self._header(headers, "Content-Range")
                        if not cr:
                            raise RemoteZipError("HTTP 206 response lacks Content-Range")
                        got_start, got_end, total = self._parse_content_range(cr)
                        if (got_start, got_end) != (start, end):
                            raise RemoteZipError(
                                f"range response mismatch {(got_start, got_end)} != {(start, end)}"
                            )
                        if self.total_bytes is not None and total != self.total_bytes:
                            raise RemoteZipError(
                                f"remote object size changed: {self.total_bytes} -> {total}"
                            )
                        self.total_bytes = total
                        data = r.read(expected + 1)
                        if len(data) != expected:
                            raise RemoteZipError(
                                f"range short/long read {len(data)} != {expected} for {start}-{end}"
                            )
                        return data, headers, status

                    if status == 200:
                        # The CDN ignored Range. Do not read the full object. We
                        # may retain its declared whole-object size, then retry.
                        n = self._size_from_headers(headers)
                        if n is not None and n > 0:
                            if self.total_bytes is not None and n != self.total_bytes:
                                raise RemoteZipError(
                                    f"remote object size changed: {self.total_bytes} -> {n}"
                                )
                            self.total_bytes = n
                        # A 200 response is acceptable only when the requested
                        # interval is exactly the complete object.
                        if self.total_bytes == expected and start == 0 and end == expected - 1:
                            data = r.read(expected + 1)
                            if len(data) != expected:
                                raise RemoteZipError(
                                    f"whole-object read {len(data)} != {expected}"
                                )
                            return data, headers, status
                        last_error = RemoteZipError(
                            f"server ignored Range {start}-{end}; status=200"
                        )
                    else:
                        last_error = RemoteZipError(
                            f"unexpected HTTP status {status} for range {start}-{end}"
                        )
            except (urllib.error.URLError, TimeoutError, OSError, RemoteZipError) as exc:
                last_error = exc

            if attempt + 1 < self.retries:
                time.sleep(min(1.0, 0.15 * (attempt + 1)))

        raise RemoteZipError(
            f"range {start}-{end} failed after {self.retries} attempts: {last_error}"
        )

    def _ensure_size(self) -> int:
        if self.total_bytes is not None:
            return self.total_bytes
        head_size = self._head_size()
        if head_size is not None:
            self.total_bytes = head_size
            return head_size
        _b, hdr, status = self.range(0, 0)
        cr = self._header(hdr, "Content-Range")
        if not cr:
            raise RemoteZipError(f"size probe returned no Content-Range; status={status}")
        _start, _end, total = self._parse_content_range(cr)
        self.total_bytes = total
        return total

    def central_directory(self) -> tuple[list[dict], dict]:
        if self._central is not None:
            return self._central, self._metadata
        total = self._ensure_size()
        tail_n = min(total, 4 * 1024 * 1024)
        tail_start = total - tail_n
        tail, _, _ = self.range(tail_start, total - 1)
        eocd_sig = b"PK\x05\x06"
        p = tail.rfind(eocd_sig)
        if p < 0 or p + 22 > len(tail):
            raise RemoteZipError("EOCD not found in final 4 MiB")
        disk, cd_disk, disk_entries32, entries32, cd_size32, cd_off32, comment_len = struct.unpack_from(
            "<4H2LH", tail, p + 4
        )
        if disk or cd_disk:
            raise RemoteZipError("multi-disk ZIP unsupported")

        zip64 = entries32 == 0xFFFF or disk_entries32 == 0xFFFF or cd_size32 == 0xFFFFFFFF or cd_off32 == 0xFFFFFFFF
        if zip64:
            eocd_file_off = tail_start + p
            locator_off = eocd_file_off - 20
            loc, _, _ = self.range(locator_off, locator_off + 19)
            if loc[:4] != b"PK\x06\x07":
                raise RemoteZipError("ZIP64 locator missing before saturated EOCD")
            disk_with_record, zip64_eocd_off, total_disks = struct.unpack_from("<IQI", loc, 4)
            if disk_with_record != 0 or total_disks != 1:
                raise RemoteZipError("multi-disk ZIP64 unsupported")
            rec, _, _ = self.range(zip64_eocd_off, zip64_eocd_off + 55)
            if rec[:4] != b"PK\x06\x06":
                raise RemoteZipError("bad ZIP64 EOCD signature")
            rec_size = struct.unpack_from("<Q", rec, 4)[0]
            if rec_size < 44:
                raise RemoteZipError(f"short ZIP64 EOCD record size {rec_size}")
            (
                ver_made,
                ver_need,
                z_disk,
                z_cd_disk,
                disk_entries,
                entries,
                cd_size,
                cd_off,
            ) = struct.unpack_from("<HHIIQQQQ", rec, 12)
            if z_disk != 0 or z_cd_disk != 0 or disk_entries != entries:
                raise RemoteZipError("multi-disk ZIP64 central directory unsupported")
            eocd_kind = "zip64"
        else:
            if disk_entries32 != entries32:
                raise RemoteZipError("multi-disk classic ZIP unsupported")
            entries = entries32
            cd_size = cd_size32
            cd_off = cd_off32
            eocd_kind = "classic"

        cd, _, _ = self.range(cd_off, cd_off + cd_size - 1)
        if len(cd) != cd_size:
            raise RemoteZipError(f"central directory short read {len(cd)} != {cd_size}")

        rows = []
        o = 0
        while o < len(cd):
            if cd[o:o+4] != b"PK\x01\x02":
                raise RemoteZipError(f"bad central-directory signature at {o}")
            vals = struct.unpack_from("<6H3L5H2L", cd, o + 4)
            (
                ver_made,
                ver_need,
                flags,
                method,
                mtime,
                mdate,
                crc32,
                csize32,
                usize32,
                nlen,
                xlen,
                clen,
                disk_start32,
                int_attr,
                ext_attr,
                lhoff32,
            ) = vals
            name_raw = cd[o+46:o+46+nlen]
            extra = cd[o+46+nlen:o+46+nlen+xlen]
            try:
                name = name_raw.decode("utf-8" if flags & 0x800 else "cp437")
            except UnicodeDecodeError:
                name = name_raw.decode("utf-8", "replace")

            need_usize = usize32 == 0xFFFFFFFF
            need_csize = csize32 == 0xFFFFFFFF
            need_lhoff = lhoff32 == 0xFFFFFFFF
            need_disk = disk_start32 == 0xFFFF
            usize = usize32
            csize = csize32
            lhoff = lhoff32
            disk_start = disk_start32

            x = 0
            zip64_extra = None
            while x + 4 <= len(extra):
                xid, xn = struct.unpack_from("<HH", extra, x)
                payload = extra[x+4:x+4+xn]
                if x + 4 + xn > len(extra):
                    raise RemoteZipError(f"{name}: truncated extra field 0x{xid:04x}")
                if xid == 0x0001:
                    zip64_extra = payload
                    break
                x += 4 + xn

            if need_usize or need_csize or need_lhoff or need_disk:
                if zip64_extra is None:
                    raise RemoteZipError(f"{name}: saturated central field without ZIP64 extra")
                z = 0
                if need_usize:
                    if z + 8 > len(zip64_extra):
                        raise RemoteZipError(f"{name}: ZIP64 usize missing")
                    usize = struct.unpack_from("<Q", zip64_extra, z)[0]
                    z += 8
                if need_csize:
                    if z + 8 > len(zip64_extra):
                        raise RemoteZipError(f"{name}: ZIP64 csize missing")
                    csize = struct.unpack_from("<Q", zip64_extra, z)[0]
                    z += 8
                if need_lhoff:
                    if z + 8 > len(zip64_extra):
                        raise RemoteZipError(f"{name}: ZIP64 local offset missing")
                    lhoff = struct.unpack_from("<Q", zip64_extra, z)[0]
                    z += 8
                if need_disk:
                    if z + 4 > len(zip64_extra):
                        raise RemoteZipError(f"{name}: ZIP64 disk missing")
                    disk_start = struct.unpack_from("<I", zip64_extra, z)[0]
                    z += 4
            if disk_start != 0:
                raise RemoteZipError(f"{name}: nonzero disk start unsupported")

            rows.append({
                "name": name,
                "flags": flags,
                "method": method,
                "crc32": crc32,
                "compressedSize": int(csize),
                "uncompressedSize": int(usize),
                "localHeaderOffset": int(lhoff),
                "versionMade": ver_made,
                "versionNeeded": ver_need,
            })
            o += 46 + nlen + xlen + clen

        if len(rows) != entries:
            raise RemoteZipError(f"central entry count mismatch {len(rows)} != {entries}")
        metadata = {
            "url": self.url,
            "bytes": total,
            "etag": self.etag,
            "eocdKind": eocd_kind,
            "entryCount": int(entries),
            "centralDirectoryOffset": int(cd_off),
            "centralDirectoryBytes": int(cd_size),
            "commentLength": int(comment_len),
        }
        self._central = rows
        self._metadata = metadata
        return rows, metadata

    def compressed_entry_bytes(self, entry: dict) -> bytes:
        if int(entry["flags"]) & 0x1:
            raise RemoteZipError(f"{entry['name']}: encrypted ZIP entry unsupported")
        lhoff = int(entry["localHeaderOffset"])
        hdr, _, _ = self.range(lhoff, lhoff + 29)
        if hdr[:4] != b"PK\x03\x04":
            raise RemoteZipError(f"{entry['name']}: bad local-header signature")
        _ver, flags, method, _mtime, _mdate, _crc, _csize, _usize, nlen, xlen = struct.unpack_from(
            "<5H3L2H", hdr, 4
        )
        if flags & 0x1:
            raise RemoteZipError(f"{entry['name']}: encrypted local entry unsupported")
        if method != int(entry["method"]):
            raise RemoteZipError(f"{entry['name']}: central/local compression method mismatch")
        data_off = lhoff + 30 + nlen + xlen
        csize = int(entry["compressedSize"])
        if csize == 0:
            return b""
        data, _, _ = self.range(data_off, data_off + csize - 1)
        if len(data) != csize:
            raise RemoteZipError(f"{entry['name']}: compressed short read {len(data)} != {csize}")
        return data

    def extract(self, entry: dict, verify_crc: bool = True) -> bytes:
        comp = self.compressed_entry_bytes(entry)
        method = int(entry["method"])
        if method == 0:
            raw = comp
        elif method == 8:
            raw = zlib.decompress(comp, -15)
        else:
            raise RemoteZipError(f"{entry['name']}: unsupported compression method {method}")
        usize = int(entry["uncompressedSize"])
        if len(raw) != usize:
            raise RemoteZipError(f"{entry['name']}: uncompressed size mismatch {len(raw)} != {usize}")
        if verify_crc:
            crc = binascii.crc32(raw) & 0xFFFFFFFF
            if crc != int(entry["crc32"]):
                raise RemoteZipError(
                    f"{entry['name']}: CRC32 mismatch {crc:08x} != {int(entry['crc32']):08x}"
                )
        return raw
