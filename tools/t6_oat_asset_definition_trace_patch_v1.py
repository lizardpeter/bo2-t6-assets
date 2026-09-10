#!/usr/bin/env python3
"""Add diagnostic serialized-definition provenance to pinned OAT T6 loaders.

This patch is proof instrumentation only. It does not change T6 loading semantics.
For every generated T6 asset loader invocation it records:
  * asset type,
  * the raw zone-pointer token seen before resolution,
  * the exact serialized input-stream position before resolution/load,
  * the resolved native pointer after the normal loader completes.

FOLLOWING/INSERT calls therefore expose the exact serialized definition site;
OFFSET calls expose aliases whose target can be joined by resolved pointer.
"""
from __future__ import annotations

import argparse
from pathlib import Path

HEADER = "src/ZoneLoading/Zone/Stream/ZoneInputStream.h"
SOURCE = "src/ZoneLoading/Zone/Stream/ZoneInputStream.cpp"
TEMPLATE = "src/ZoneCodeGeneratorLib/Generating/Templates/ZoneLoadTemplate.cpp"
MARKER = "T6_ASSET_LOAD_EVENT"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"unexpected pinned OAT {label} layout: expected one match, got {text.count(old)}")
    return text.replace(old, new, 1)


def patch_header(root: Path) -> None:
    path = root / HEADER
    text = path.read_text(encoding="utf-8")
    marker = "ProofRawStreamPos"
    if marker in text:
        return
    old = "    [[nodiscard]] virtual unsigned GetPointerBitCount() const = 0;\n"
    new = old + (
        "\n"
        "    // Diagnostic proof accessor: serialized XFile byte position.\n"
        "    // It does not mutate block or stream state.\n"
        "    [[nodiscard]] virtual int64_t ProofRawStreamPos() = 0;\n"
    )
    text = replace_once(text, old, new, HEADER)
    path.write_text(text, encoding="utf-8")


def patch_source(root: Path) -> None:
    path = root / SOURCE
    text = path.read_text(encoding="utf-8")
    marker = "ProofRawStreamPos() override"
    if marker in text:
        return
    old = (
        "        [[nodiscard]] unsigned GetPointerBitCount() const override\n"
        "        {\n"
        "            return m_pointer_byte_count * 8u;\n"
        "        }\n"
    )
    new = old + (
        "\n"
        "        [[nodiscard]] int64_t ProofRawStreamPos() override\n"
        "        {\n"
        "            return m_stream.Pos();\n"
        "        }\n"
    )
    text = replace_once(text, old, new, SOURCE)
    path.write_text(text, encoding="utf-8")


def patch_template(root: Path) -> None:
    path = root / TEMPLATE
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return

    old_includes = (
        '            LINE("#include <cassert>")\n'
        '            LINE("#include <cstring>")\n'
        '            LINE("#include <type_traits>")\n'
    )
    new_includes = (
        '            LINE("#include <cassert>")\n'
        '            LINE("#include <cstring>")\n'
        '            if (m_env.m_game == "T6")\n'
        '                LINE("#include <cstdio>")\n'
        '            LINE("#include <type_traits>")\n'
    )
    text = replace_once(text, old_includes, new_includes, f"{TEMPLATE} includes")

    old_begin = (
        '            LINE("assert(pAsset != nullptr);")\n'
        '            LINE("")\n'
        '            LINE("m_asset_info = nullptr;")\n'
    )
    new_begin = (
        '            LINE("assert(pAsset != nullptr);")\n'
        '            if (m_env.m_game == "T6")\n'
        '            {\n'
        '                LINEF("const auto t6ProofRawAssetPointer = reinterpret_cast<uintptr_t>(*pAsset);")\n'
        '                LINE("const auto t6ProofSerializedPosition = m_stream.ProofRawStreamPos();")\n'
        '            }\n'
        '            LINE("")\n'
        '            LINE("m_asset_info = nullptr;")\n'
    )
    text = replace_once(text, old_begin, new_begin, f"{TEMPLATE} Load begin")

    old_end = (
        '            LINE("")\n'
        '            LINE("return m_asset_info;")\n'
        '\n'
        '            m_intendation--;\n'
    )
    new_end = (
        '            if (m_env.m_game == "T6")\n'
        '            {\n'
        '                LINE("")\n'
        '                LINEF("std::fprintf(stderr, \\\"T6_ASSET_LOAD_EVENT\\\\t%u\\\\t0x%08llX\\\\t%lld\\\\t%p\\\\n\\\", "\n'
        '                      "static_cast<unsigned>({0}), "\n'
        '                      "static_cast<unsigned long long>(t6ProofRawAssetPointer), "\n'
        '                      "static_cast<long long>(t6ProofSerializedPosition), "\n'
        '                      "static_cast<void*>(*pAsset));",\n'
        '                      m_env.m_asset->m_asset_name)\n'
        '            }\n'
        '            LINE("")\n'
        '            LINE("return m_asset_info;")\n'
        '\n'
        '            m_intendation--;\n'
    )
    text = replace_once(text, old_end, new_end, f"{TEMPLATE} Load end")

    if text.count(MARKER) != 1 or text.count("ProofRawStreamPos") != 1:
        raise SystemExit("T6 serialized-definition trace template patch did not close exactly")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oat_root", type=Path)
    args = ap.parse_args()
    root = args.oat_root.resolve()
    for rel in (HEADER, SOURCE, TEMPLATE):
        if not (root / rel).is_file():
            raise SystemExit(f"pinned OAT source missing: {rel}")
    patch_header(root)
    patch_source(root)
    patch_template(root)
    print("patched pinned OAT: exact serialized T6 asset-definition provenance trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
