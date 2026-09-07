#!/usr/bin/env python3
"""Apply the bounded host-build fixes needed by pinned OAT 9dca965.

The pinned OpenAssetTools revision exposes three host portability issues on
Ubuntu 24.04 / GCC 13.3.0:

* four legacy menu writers call ``std::format`` without including ``<format>``;
* ``FlatXAnimDataWriter.cpp`` uses ``std::numeric_limits`` without including
  ``<limits>``;
* the T5 high-mip-volume helper calls non-standard ``std::sqrtf`` instead of
  the standard overloaded ``std::sqrt`` already provided by ``<cmath>``.

The SEAL6 proof needs only the ``UnlinkerCli`` product. The pinned legacy debug
script builds every OAT project, so this helper also narrows that script's make
target from ``all`` to ``UnlinkerCli``. Premake keeps the project's declared
linked dependencies; this only avoids unrelated executables/tests and does not
change the resulting Unlinker source or runtime semantics.

This helper deliberately does not touch T6 loader, generated ZoneCode,
FastFile, Material, TechniqueSet, shader, pointer, or stream semantics. Every
edit is fail-closed against the exact pinned layout so an unexpected
upstream/source state cannot be silently accepted.
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
BUILD_SCRIPT_TARGET = "scripts/make-debug.sh"


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


def replace_once(path: Path, *, needle: str, replacement: str) -> str:
    text = path.read_text(encoding="utf-8")
    if replacement in text and needle not in text:
        return "already-patched"
    if text.count(needle) != 1:
        raise RuntimeError(f"{path}: expected exactly one {needle!r}")
    if replacement in text:
        raise RuntimeError(f"{path}: replacement already present alongside source form")
    patched = text.replace(needle, replacement, 1)
    if patched.count(replacement) != 1 or needle in patched:
        raise RuntimeError(f"{path}: failed exact replacement {needle!r} -> {replacement!r}")
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
        needle="return std::sqrtf(v6) * 0.5f;",
        replacement="return std::sqrt(v6) * 0.5f;",
    )
    statuses.append((SQRT_TARGET, status))
    print(f"{status}: {SQRT_TARGET}: std::sqrtf -> std::sqrt")

    path = root / BUILD_SCRIPT_TARGET
    if not path.is_file():
        raise SystemExit(f"Pinned OAT build script missing: {BUILD_SCRIPT_TARGET}")
    status = replace_once(
        path,
        needle="make -C build -j$(nproc) config=debug_x86 all\n",
        replacement="make -C build -j$(nproc) config=debug_x86 UnlinkerCli\n",
    )
    statuses.append((BUILD_SCRIPT_TARGET, status))
    print(f"{status}: {BUILD_SCRIPT_TARGET}: all -> UnlinkerCli")

    kinds = {status for _, status in statuses}
    if len(kinds) != 1:
        raise SystemExit(f"mixed patch state: {statuses!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
