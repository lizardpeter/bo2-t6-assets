#!/usr/bin/env python3
"""Offline regressions for the remote ZIP range parser."""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from t6_remote_zip_member_v1 import (
    RemoteZipError,
    central_entries,
    local_data_offset,
    resolve_basename,
)


class FileReader:
    def __init__(self, path: Path):
        self.path = path
        self.length = path.stat().st_size

    def read(self, start: int, size: int) -> bytes:
        if start < 0 or size < 0 or start + size > self.length:
            raise RemoteZipError("test range out of bounds")
        with self.path.open("rb") as f:
            f.seek(start)
            data = f.read(size)
        if len(data) != size:
            raise RemoteZipError("short test read")
        return data


def must_fail(fn, needle: str) -> None:
    try:
        fn()
    except RemoteZipError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected RemoteZipError containing {needle!r}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        zpath = root / "fixture.zip"
        payload_a = b"TAff0100" + bytes(range(64))
        payload_b = b"ipak-fixture" * 100
        with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
            z.writestr("Plutonium/zone/all/faction_seals_mp.ff", payload_a)
            z.writestr("Plutonium/zone/all/base.ipak", payload_b)
            z.writestr("Plutonium/docs/readme.txt", b"hello")

        reader = FileReader(zpath)
        entries, cd = central_entries(reader, 1024 * 1024)
        assert cd["entries"] == 3
        assert len(entries) == 3
        ff = resolve_basename(entries, "faction_seals_mp.ff")
        assert ff.method == 0
        assert ff.uncompressed_size == len(payload_a)
        start = local_data_offset(reader, ff)
        assert reader.read(start, ff.uncompressed_size) == payload_a
        ipak = resolve_basename(entries, "base.ipak")
        assert reader.read(local_data_offset(reader, ipak), ipak.uncompressed_size) == payload_b
        must_fail(lambda: resolve_basename(entries, "missing.ff"), "not found")

        dup = root / "duplicate.zip"
        with zipfile.ZipFile(dup, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("a/common_mp.ff", b"a")
            z.writestr("b/common_mp.ff", b"b")
        dup_reader = FileReader(dup)
        dup_entries, _ = central_entries(dup_reader, 1024 * 1024)
        must_fail(lambda: resolve_basename(dup_entries, "common_mp.ff"), "ambiguous")

        compressed = root / "compressed.zip"
        with zipfile.ZipFile(compressed, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("x/file.bin", b"compress me" * 100)
        comp_reader = FileReader(compressed)
        comp_entries, _ = central_entries(comp_reader, 1024 * 1024)
        c = resolve_basename(comp_entries, "file.bin")
        assert c.method == zipfile.ZIP_DEFLATED
        assert c.compressed_size < c.uncompressed_size

    print("PASS: T6 remote ZIP member parser v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
