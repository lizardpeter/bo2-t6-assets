#!/usr/bin/env python3
"""Apply one diagnostic-only T6 XAnim ordinal/name trace to pinned OAT 9dca965.

The patch does not alter FastFile, block, pointer, XAnim, or asset-loading semantics.
It emits the already-loaded XAnimParts name while ContentLoader still points at the
physical XAsset array entry for the current ordinal.

Expected use is only on the exact pinned OpenAssetTools revision
9dca965366541504b71fa8cfb7ac049cb9b717e1 after checkout verification.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET = Path("src/ZoneLoading/Game/T6/ContentLoaderT6.cpp")
MARKER = "T6_XANIM_ORDINAL_NAME"

INCLUDE_OLD = "#include <cassert>\n"
INCLUDE_NEW = "#include <cassert>\n#include <cstdio>\n"

LOOP_OLD = """    for (size_t index = 0; index < count; index++)
    {
        LoadXAsset(false);
        varXAsset++;

#ifdef DEBUG_OFFSETS
"""

LOOP_NEW = """    for (size_t index = 0; index < count; index++)
    {
        LoadXAsset(false);

        if (varXAsset->type == ASSET_TYPE_XANIMPARTS)
        {
            const auto* parts = varXAsset->header.parts;
            std::fprintf(stderr,
                         "T6_XANIM_ORDINAL_NAME\\t%zu\\t%s\\n",
                         index,
                         parts != nullptr && parts->name != nullptr ? parts->name : "<null>");
        }

        varXAsset++;

#ifdef DEBUG_OFFSETS
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("oat_root", type=Path)
    args = parser.parse_args()

    root = args.oat_root.resolve()
    path = root / TARGET
    if not path.is_file():
        raise SystemExit(f"Pinned OAT source missing: {TARGET}")

    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        if text.count(MARKER) != 1 or INCLUDE_NEW not in text or LOOP_NEW not in text:
            raise SystemExit("mixed or multiply-patched T6 XAnim trace state")
        print(f"already-patched: {TARGET}")
        return 0

    if text.count(INCLUDE_OLD) != 1:
        raise SystemExit("expected exactly one <cassert> include anchor")
    if text.count(LOOP_OLD) != 1:
        raise SystemExit("expected exactly one T6 LoadXAssetArray loop anchor")

    text = text.replace(INCLUDE_OLD, INCLUDE_NEW, 1)
    text = text.replace(LOOP_OLD, LOOP_NEW, 1)

    if text.count(MARKER) != 1 or text.count("#include <cstdio>\n") != 1:
        raise SystemExit("T6 XAnim trace patch did not close exactly")
    if LOOP_OLD in text:
        raise SystemExit("unpatched T6 XAsset loop remains after trace patch")

    path.write_text(text, encoding="utf-8")
    print(f"patched: {TARGET}: diagnostic XAnim ordinal/name trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
