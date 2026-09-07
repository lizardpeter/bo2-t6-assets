#!/usr/bin/env python3
"""Apply the minimal GCC compatibility patch needed by pinned OAT 9dca965.

The pinned OpenAssetTools revision uses std::format in four legacy menu writers
without including <format>. GCC 13 therefore fails while building ObjWriting.
This helper adds only the missing standard-library include and refuses to touch
any other source text. It does not alter T6 loader, material, TechniqueSet,
shader, or FastFile semantics.
"""

from __future__ import annotations

import argparse
from pathlib import Path


TARGETS = (
    "src/ObjWriting/Game/IW3/Menu/MenuWriterIW3.cpp",
    "src/ObjWriting/Game/IW4/Menu/MenuWriterIW4.cpp",
    "src/ObjWriting/Game/IW5/Menu/MenuWriterIW5.cpp",
    "src/ObjWriting/Game/T4/Menu/MenuWriterT4.cpp",
)

NEEDLE = "#include <cmath>\n"
INSERT = "#include <cmath>\n#include <format>\n"


def patch_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "#include <format>\n" in text:
        return "already-patched"
    if text.count(NEEDLE) != 1:
        raise RuntimeError(f"{path}: expected exactly one {NEEDLE.strip()!r}")
    patched = text.replace(NEEDLE, INSERT, 1)
    if patched.count("#include <format>\n") != 1:
        raise RuntimeError(f"{path}: failed to produce exactly one <format> include")
    path.write_text(patched, encoding="utf-8")
    return "patched"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("oat_root", type=Path)
    args = parser.parse_args()

    root = args.oat_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"OAT root does not exist: {root}")

    statuses = []
    for rel in TARGETS:
        path = root / rel
        if not path.is_file():
            raise SystemExit(f"Pinned OAT source missing: {rel}")
        status = patch_file(path)
        statuses.append((rel, status))
        print(f"{status}: {rel}")

    # Fail closed if upstream unexpectedly already contains the patch in only a
    # subset of the four files. The pinned revision is expected to need all 4.
    kinds = {status for _, status in statuses}
    if len(kinds) != 1:
        raise SystemExit(f"mixed patch state: {statuses!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
