#!/usr/bin/env python3
"""Reusable BO2/T6 IPAK (KAPI v0x50000) index and payload resolver.

Production policy:
- exact streamed lookup is `(nameHash, dataHash)`;
- same-name/different-data candidates are diagnostics, never implicit substitutes;
- unique-dataHash resolution is exposed explicitly for separately proven callers;
- decompressed payloads must reproduce the entry's T6 CRC29;
- retail block command 0xCF is consumed as padding/skip and emits no bytes;
- local files and HTTP byte-range sources use the same parser/extractor.

No map/model-specific behavior belongs in this module.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import io
import struct
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


KAPI_MAGIC = b"KAPI"
T6_IPAK_VERSION = 0x50000
IPAK_BLOCK_ALIGNMENT = 0x80
IPAK_HEADER_BYTES = 16
IPAK_SECTION_BYTES = 16
IPAK_ENTRY_BYTES = 16
IPAK_BLOCK_HEADER_BYTES = 128


class T6IpakError(RuntimeError):
    pass


class RangeSource(Protocol):
    label: str
    size: int | None

    def read_range(self, start: int, end_exclusive: int) -> bytes:
        ...


class LocalFileSource:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.label = str(self.path)
        self.size = self.path.stat().st_size

    def read_range(self, start: int, end_exclusive: int) -> bytes:
        if start < 0 or end_exclusive < start or end_exclusive > self.size:
            raise T6IpakError(
                f"{self.label}: invalid range [{start},{end_exclusive}) for {self.size} bytes"
            )
        with self.path.open("rb") as handle:
            handle.seek(start)
            data = handle.read(end_exclusive - start)
        if len(data) != end_exclusive - start:
            raise T6IpakError(f"{self.label}: short local range read")
        return data


class HttpRangeSource:
    def __init__(
        self,
        url: str,
        *,
        expected_size: int | None = None,
        user_agent: str = "bo2-t6-assets-ipak-core/1",
        timeout: int = 120,
    ):
        self.url = url
        self.label = url
        self.size = expected_size
        self.user_agent = user_agent
        self.timeout = timeout
        self.network_bytes = 0
        self.range_reads: list[dict[str, object]] = []

    def read_range(self, start: int, end_exclusive: int) -> bytes:
        if start < 0 or end_exclusive <= start:
            raise T6IpakError(f"{self.url}: invalid HTTP range [{start},{end_exclusive})")
        if self.size is not None and end_exclusive > self.size:
            raise T6IpakError(
                f"{self.url}: range [{start},{end_exclusive}) exceeds expected {self.size} bytes"
            )
        request = urllib.request.Request(
            self.url,
            headers={
                "Range": f"bytes={start}-{end_exclusive - 1}",
                "User-Agent": self.user_agent,
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            status = getattr(response, "status", None)
            if status != 206:
                raise T6IpakError(f"{self.url}: HTTP range not honored (status {status})")
            data = response.read()
            content_range = response.headers.get("Content-Range", "")
        expected = end_exclusive - start
        if len(data) != expected:
            raise T6IpakError(
                f"{self.url}: range length {len(data)} != {expected}; {content_range}"
            )
        self.network_bytes += len(data)
        self.range_reads.append(
            {
                "start": start,
                "endExclusive": end_exclusive,
                "bytes": len(data),
                "contentRange": content_range,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        return data


@dataclass(frozen=True)
class IpakSection:
    kind: int
    offset: int
    size: int
    count: int


@dataclass(frozen=True)
class IpakEntry:
    data_hash: int
    name_hash: int
    relative_offset: int
    raw_size: int

    @classmethod
    def from_tuple(cls, value: tuple[int, int, int, int]) -> "IpakEntry":
        return cls(*map(int, value))

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.data_hash, self.name_hash, self.relative_offset, self.raw_size)


class T6Ipak:
    def __init__(
        self,
        *,
        source: RangeSource,
        total_size: int,
        sections: list[IpakSection],
        index_section: IpakSection,
        data_section: IpakSection,
        entries: list[IpakEntry],
        header_bytes: bytes,
        index_bytes: bytes,
    ):
        self.source = source
        self.total_size = total_size
        self.sections = sections
        self.index_section = index_section
        self.data_section = data_section
        self.entries = entries
        self.header_bytes = header_bytes
        self.index_bytes = index_bytes

        by_pair: dict[tuple[int, int], IpakEntry] = {}
        by_name: dict[int, list[IpakEntry]] = {}
        by_data: dict[int, list[IpakEntry]] = {}
        for entry in entries:
            pair = (entry.name_hash, entry.data_hash)
            if pair in by_pair:
                raise T6IpakError(f"{source.label}: duplicate IPAK exact key {pair!r}")
            by_pair[pair] = entry
            by_name.setdefault(entry.name_hash, []).append(entry)
            by_data.setdefault(entry.data_hash, []).append(entry)
        self.by_pair = by_pair
        self.by_name = by_name
        self.by_data = by_data
        self._lzo = None

    @classmethod
    def open(cls, source: RangeSource) -> "T6Ipak":
        prefix = source.read_range(0, 16)
        magic, version, total_size, section_count = struct.unpack_from("<4sIII", prefix, 0)
        if magic != KAPI_MAGIC:
            raise T6IpakError(f"{source.label}: not a KAPI container")
        if version != T6_IPAK_VERSION:
            raise T6IpakError(f"{source.label}: unsupported IPAK version {version:#x}")
        if source.size is not None and total_size != source.size:
            raise T6IpakError(
                f"{source.label}: header size {total_size} != source size {source.size}"
            )
        section_table_end = IPAK_HEADER_BYTES + section_count * IPAK_SECTION_BYTES
        if section_table_end > total_size:
            raise T6IpakError(f"{source.label}: section table exceeds container")
        header_bytes = source.read_range(0, section_table_end)
        sections = [
            IpakSection(*struct.unpack_from("<IIII", header_bytes, 16 + 16 * i))
            for i in range(section_count)
        ]
        index_sections = [s for s in sections if s.kind == 1]
        data_sections = [s for s in sections if s.kind == 2]
        if len(index_sections) != 1 or len(data_sections) != 1:
            raise T6IpakError(
                f"{source.label}: expected one index and one data section, got "
                f"{len(index_sections)} / {len(data_sections)}"
            )
        index_section = index_sections[0]
        data_section = data_sections[0]
        expected_index_bytes = index_section.count * IPAK_ENTRY_BYTES
        if expected_index_bytes > index_section.size:
            raise T6IpakError(f"{source.label}: index entry table exceeds index section")
        index_end = index_section.offset + expected_index_bytes
        if index_section.offset < 0 or index_end > total_size:
            raise T6IpakError(f"{source.label}: index range exceeds container")
        index_bytes = source.read_range(index_section.offset, index_end)
        entries = [
            IpakEntry(*struct.unpack_from("<IIII", index_bytes, IPAK_ENTRY_BYTES * i))
            for i in range(index_section.count)
        ]
        for entry in entries:
            start = data_section.offset + entry.relative_offset
            end = start + entry.raw_size
            if start < data_section.offset or end > total_size:
                raise T6IpakError(
                    f"{source.label}: entry {entry.as_tuple()} compressed range outside container"
                )
        return cls(
            source=source,
            total_size=total_size,
            sections=sections,
            index_section=index_section,
            data_section=data_section,
            entries=entries,
            header_bytes=header_bytes,
            index_bytes=index_bytes,
        )

    @classmethod
    def open_file(cls, path: Path) -> "T6Ipak":
        return cls.open(LocalFileSource(path))

    @classmethod
    def open_http(
        cls,
        url: str,
        *,
        expected_size: int | None = None,
        user_agent: str = "bo2-t6-assets-ipak-core/1",
        timeout: int = 120,
    ) -> "T6Ipak":
        return cls.open(
            HttpRangeSource(
                url,
                expected_size=expected_size,
                user_agent=user_agent,
                timeout=timeout,
            )
        )

    def exact(self, name_hash: int, data_hash: int) -> IpakEntry | None:
        return self.by_pair.get((int(name_hash), int(data_hash)))

    def name_candidates(self, name_hash: int) -> tuple[IpakEntry, ...]:
        return tuple(self.by_name.get(int(name_hash), ()))

    def data_candidates(self, data_hash: int) -> tuple[IpakEntry, ...]:
        return tuple(self.by_data.get(int(data_hash), ()))

    def unique_data(self, data_hash: int) -> IpakEntry | None:
        rows = self.by_data.get(int(data_hash), ())
        return rows[0] if len(rows) == 1 else None

    def entry_segment_range(self, entry: IpakEntry) -> tuple[int, int]:
        start = self.data_section.offset + entry.relative_offset
        return start, start + entry.raw_size

    def _lzo_decompressor(self):
        if self._lzo is not None:
            return self._lzo
        library = ctypes.util.find_library("lzo2")
        if not library:
            raise T6IpakError("liblzo2 not found")
        fn = ctypes.CDLL(library).lzo1x_decompress_safe
        fn.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
        ]
        fn.restype = ctypes.c_int
        self._lzo = fn
        return fn

    def extract(self, entry: IpakEntry) -> bytes:
        start, end = self.entry_segment_range(entry)
        segment = self.source.read_range(start, end)
        out = bytearray()
        absolute = start
        block_count = 0
        lzo = None
        while absolute < end:
            aligned = ((absolute + IPAK_BLOCK_ALIGNMENT - 1) // IPAK_BLOCK_ALIGNMENT) * IPAK_BLOCK_ALIGNMENT
            if aligned >= end:
                break
            local = aligned - start
            header = segment[local:local + IPAK_BLOCK_HEADER_BYTES]
            if len(header) != IPAK_BLOCK_HEADER_BYTES:
                raise T6IpakError(f"{self.source.label}: truncated IPAK block header")
            command_header = struct.unpack_from("<I", header, 0)[0]
            file_offset = command_header & 0xFFFFFF
            command_count = (command_header >> 24) & 0xFF
            if command_count > 31:
                raise T6IpakError(
                    f"{self.source.label}: invalid block command count {command_count}"
                )
            commands = []
            for i in range(command_count):
                word = struct.unpack_from("<I", header, 4 + 4 * i)[0]
                commands.append((word & 0xFFFFFF, (word >> 24) & 0xFF))
            if any(kind in (0, 1) for _, kind in commands) and file_offset != len(out):
                raise T6IpakError(
                    f"{self.source.label}: block output offset {file_offset} != {len(out)}"
                )
            cursor = local + IPAK_BLOCK_HEADER_BYTES
            for stored_size, compression in commands:
                blob = segment[cursor:cursor + stored_size]
                if len(blob) != stored_size:
                    raise T6IpakError(f"{self.source.label}: truncated IPAK command payload")
                if compression == 0:
                    out.extend(blob)
                elif compression == 1:
                    if lzo is None:
                        lzo = self._lzo_decompressor()
                    destination = ctypes.create_string_buffer(0x8000)
                    destination_size = ctypes.c_size_t(0x8000)
                    source_buffer = ctypes.create_string_buffer(blob)
                    rc = lzo(
                        source_buffer,
                        len(blob),
                        destination,
                        ctypes.byref(destination_size),
                        None,
                    )
                    if rc != 0:
                        raise T6IpakError(f"{self.source.label}: lzo error {rc}")
                    out.extend(destination.raw[:destination_size.value])
                elif compression == 0xCF:
                    # Retail T6 skip/padding command: consume bytes, emit none.
                    pass
                else:
                    raise T6IpakError(
                        f"{self.source.label}: unsupported IPAK compression command {compression:#x}"
                    )
                cursor += stored_size
            absolute = start + cursor
            block_count += 1
            if block_count > 10000:
                raise T6IpakError(f"{self.source.label}: IPAK block runaway")
        payload = bytes(out)
        crc29 = zlib.crc32(payload) & 0x1FFFFFFF
        if crc29 != entry.data_hash:
            raise T6IpakError(
                f"{self.source.label}: CRC29 {crc29:08x} != {entry.data_hash:08x}"
            )
        return payload

    def extract_exact(self, name_hash: int, data_hash: int) -> bytes:
        entry = self.exact(name_hash, data_hash)
        if entry is None:
            variants = sorted(e.data_hash for e in self.name_candidates(name_hash))
            raise T6IpakError(
                f"{self.source.label}: exact pair missing name={int(name_hash):08x} "
                f"data={int(data_hash):08x}; same-name data hashes={variants}"
            )
        return self.extract(entry)

    def provenance(self) -> dict[str, object]:
        source = {
            "label": self.source.label,
            "size": self.total_size,
        }
        if isinstance(self.source, LocalFileSource):
            source["kind"] = "local-file"
            source["path"] = str(self.source.path)
        elif isinstance(self.source, HttpRangeSource):
            source["kind"] = "http-range"
            source["url"] = self.source.url
            source["networkBytes"] = self.source.network_bytes
            source["rangeReadCount"] = len(self.source.range_reads)
            source["rangeReads"] = list(self.source.range_reads)
        else:
            source["kind"] = type(self.source).__name__
        return {
            "format": "t6-ipak-provenance-v1",
            "source": source,
            "container": {
                "magic": "KAPI",
                "version": T6_IPAK_VERSION,
                "bytes": self.total_size,
                "sectionCount": len(self.sections),
                "indexEntryCount": len(self.entries),
                "headerSha256": hashlib.sha256(self.header_bytes).hexdigest(),
                "indexSha256": hashlib.sha256(self.index_bytes).hexdigest(),
                "indexSection": self.index_section.__dict__,
                "dataSection": self.data_section.__dict__,
            },
            "policy": (
                "Exact streamed lookup is (nameHash,dataHash). Same-name variants are diagnostic "
                "only; unique-dataHash fallback must be requested explicitly by a separately "
                "proven caller. Extracted bytes must reproduce T6 CRC29."
            ),
        }
