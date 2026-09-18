#!/usr/bin/env python3
"""Apply only host-compiler compatibility fixes needed by pinned OAT 7d027e8.

This helper exists for the Nuketown GfxWorld lightmap/reflection ownership
workflow pinned to OpenAssetTools commit
7d027e8f89118196713e955b0e11f8404149c54d.

Ubuntu 24.04 / GCC 13 exposes five unrelated upstream portability defects in
that exact revision:

* IW3/IW4/IW5 legacy menu writers use std::format without including <format>;
* FlatXAnimDataWriter.cpp uses std::numeric_limits without including <limits>;
* XModelHighMipVolumeT5.cpp calls std::sqrtf although this host standard library
  exposes the overloaded function as std::sqrt.

Only those source-level compatibility edits are permitted. No T6 loader,
generated ZoneCode, FastFile, GfxWorld, Material, TechniqueSet, shader, pointer,
or stream semantics are modified. All anchors are exact and fail closed.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PINNED_OAT_COMMIT = "7d027e8f89118196713e955b0e11f8404149c54d"

FORMAT_TARGETS = (
    "src/ObjWriting/Game/IW3/Menu/MenuWriterIW3.cpp",
    "src/ObjWriting/Game/IW4/Menu/MenuWriterIW4.cpp",
    "src/ObjWriting/Game/IW5/Menu/MenuWriterIW5.cpp",
)
LIMITS_TARGET = "src/ObjLoading/XAnim/FlatXAnimDataWriter.cpp"
SQRT_TARGET = "src/ObjLoading/Game/T5/XModel/XModelHighMipVolumeT5.cpp"


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def insert_once(path: Path, *, needle: str, insert: str, marker: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        raise RuntimeError(f"{path}: already contains {marker.strip()!r}")
    if text.count(needle) != 1:
        raise RuntimeError(f"{path}: expected exactly one {needle.strip()!r}")
    patched = text.replace(needle, insert, 1)
    if patched.count(marker) != 1:
        raise RuntimeError(f"{path}: failed to produce exactly one {marker.strip()!r}")
    path.write_text(patched, encoding="utf-8")


def replace_once(path: Path, *, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        raise RuntimeError(f"{path}: already contains patched expression {new!r}")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected exactly one {old!r}")
    patched = text.replace(old, new, 1)
    if old in patched or patched.count(new) != 1:
        raise RuntimeError(f"{path}: replacement did not close exactly")
    path.write_text(patched, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("oat_root", type=Path)
    args = parser.parse_args()

    root = args.oat_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"OAT root does not exist: {root}")

    head = git_head(root)
    if head != PINNED_OAT_COMMIT:
        raise SystemExit(
            f"unexpected OAT HEAD {head}; expected exactly {PINNED_OAT_COMMIT}"
        )

    for rel in FORMAT_TARGETS:
        path = root / rel
        if not path.is_file():
            raise SystemExit(f"Pinned OAT source missing: {rel}")
        insert_once(
            path,
            needle="#include <cmath>\n",
            insert="#include <cmath>\n#include <format>\n",
            marker="#include <format>\n",
        )
        print(f"patched: {rel}: <format>")

    path = root / LIMITS_TARGET
    if not path.is_file():
        raise SystemExit(f"Pinned OAT source missing: {LIMITS_TARGET}")
    insert_once(
        path,
        needle="#include <iterator>\n",
        insert="#include <iterator>\n#include <limits>\n",
        marker="#include <limits>\n",
    )
    print(f"patched: {LIMITS_TARGET}: <limits>")

    path = root / SQRT_TARGET
    if not path.is_file():
        raise SystemExit(f"Pinned OAT source missing: {SQRT_TARGET}")
    replace_once(
        path,
        old="return std::sqrtf(v6) * 0.5f;",
        new="return std::sqrt(v6) * 0.5f;",
    )
    print(f"patched: {SQRT_TARGET}: std::sqrtf -> std::sqrt")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
