#!/usr/bin/env python3
"""Apply only host-compiler compatibility fixes needed by pinned OAT 9dca965.

The pinned OpenAssetTools revision exposes three independent portability issues
on Ubuntu 24.04 / GCC 13.3.0:

* four legacy menu writers call ``std::format`` without including ``<format>``;
* ``FlatXAnimDataWriter.cpp`` uses ``std::numeric_limits`` without including
  ``<limits>``;
* ``XModelHighMipVolumeT5.cpp`` calls ``std::sqrtf`` even though this host's
  standard C++ library exposes the overloaded function as ``std::sqrt``.

This helper makes only those compatibility edits. It deliberately does not touch
T6 loader, generated ZoneCode, FastFile, Material, TechniqueSet, shader, pointer,
or stream semantics. Every source edit is fail-closed against the exact pinned
layout so an unexpected upstream/source state cannot be silently accepted.
"""

from __future__ import annotations

import argparse
from pathlib import Path


FORMAT_TARGETS = (
    "src/ObjWriting/Game/IW3/Menu/MenuWriterIW3.cpp",
    "src/ObjWriting/Game/IW4/Menu/MenuWriterIW4.cpp",
    "src/ObjWriting/Game/IW5/Menu/MenuWriterIW5.cpp",
    "src/ObjWriting/Game/T4/Menu/MenuWriterT4.cpp",
)

LIMITS_TARGET = "src/ObjLoading/XAnim/FlatXAnimDataWriter.cpp"
SQRT_TARGET = "src/ObjLoading/Game/T5/XModel/XModelHighMipVolumeT5.cpp"


def insert_once(path: Path, *, needle: str, insert: str, marker: str) -> str:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return "already-patched"
    if text.count(needle) != 1:
        raise RuntimeError(f"{path}: expected exactly one {needle.strip()!r}")
    patched = text.replace(needle, insert, 1)
    if patched.count(marker) != 1:
        raise RuntimeError(f"{path}: failed to produce exactly one {marker.strip()!r}")
    path.write_text(patched, encoding="utf-8")
    return "patched"


def replace_once(path: Path, *, old: str, new: str) -> str:
    text = path.read_text(encoding="utf-8")
    if new in text:
        if old in text:
            raise RuntimeError(f"{path}: mixed old/new replacement state")
        if text.count(new) != 1:
            raise RuntimeError(f"{path}: expected exactly one patched expression")
        return "already-patched"
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected exactly one {old!r}")
    patched = text.replace(old, new, 1)
    if old in patched or patched.count(new) != 1:
        raise RuntimeError(f"{path}: replacement did not close exactly")
    path.write_text(patched, encoding="utf-8")
    return "patched"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("oat_root", type=Path)
    args = parser.parse_args()

    root = args.oat_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"OAT root does not exist: {root}")

    statuses: list[tuple[str, str]] = []

    for rel in FORMAT_TARGETS:
        path = root / rel
        if not path.is_file():
            raise SystemExit(f"Pinned OAT source missing: {rel}")
        status = insert_once(
            path,
            needle="#include <cmath>\n",
            insert="#include <cmath>\n#include <format>\n",
            marker="#include <format>\n",
        )
        statuses.append((rel, status))
        print(f"{status}: {rel}: <format>")

    path = root / LIMITS_TARGET
    if not path.is_file():
        raise SystemExit(f"Pinned OAT source missing: {LIMITS_TARGET}")
    status = insert_once(
        path,
        needle="#include <iterator>\n",
        insert="#include <iterator>\n#include <limits>\n",
        marker="#include <limits>\n",
    )
    statuses.append((LIMITS_TARGET, status))
    print(f"{status}: {LIMITS_TARGET}: <limits>")

    path = root / SQRT_TARGET
    if not path.is_file():
        raise SystemExit(f"Pinned OAT source missing: {SQRT_TARGET}")
    status = replace_once(
        path,
        old="return std::sqrtf(v6) * 0.5f;",
        new="return std::sqrt(v6) * 0.5f;",
    )
    statuses.append((SQRT_TARGET, status))
    print(f"{status}: {SQRT_TARGET}: std::sqrtf -> std::sqrt")

    # The pinned revision is expected to need all six edits. A mixed state
    # means the source tree is not the exact state this compatibility helper
    # was written for, so stop rather than altering an unknown revision.
    kinds = {status for _, status in statuses}
    if len(kinds) != 1:
        raise SystemExit(f"mixed patch state: {statuses!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
