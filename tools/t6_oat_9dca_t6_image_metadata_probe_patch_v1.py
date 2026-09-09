#!/usr/bin/env python3
"""Apply a metadata-only T6 GfxImage diagnostic to pinned OAT 9dca965.

This patch is intentionally observational. When OAT_T6_IMAGE_METADATA_V1 is
set, the generated T6 Image dumper prints fields already present in the loaded
retail GfxImage and returns before texture conversion or file output. It does
not derive hashes from names, resolve IPAK entries, mutate assets, or alter the
normal dumper path when the environment variable is absent.
"""
from __future__ import annotations

import argparse
from pathlib import Path

TARGET = "src/ObjWriting/Image/ImageDumper.cpp.template"
ENV_NAME = "OAT_T6_IMAGE_METADATA_V1"
MARKER = "T6_IMAGE_META_V1|name={}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oat_root", type=Path)
    args = ap.parse_args()
    root = args.oat_root.resolve()
    path = root / TARGET
    if not path.is_file():
        raise SystemExit(f"pinned OAT source missing: {TARGET}")

    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        raise SystemExit("metadata probe already present; expected pristine pinned template")

    include_needle = "#include <cassert>\n"
    if text.count(include_needle) != 1:
        raise SystemExit("unexpected pinned ImageDumper include layout")
    text = text.replace(include_needle, "#include <cassert>\n#include <cstdlib>\n", 1)

    body_needle = """        const auto* image = asset.Asset();\n        auto texture = CONVERTER_NAME().Convert(asset, context.m_obj_search_path);\n"""
    if text.count(body_needle) != 1:
        raise SystemExit("unexpected pinned ImageDumper DumpAsset layout")

    body = """        const auto* image = asset.Asset();
#ifdef FEATURE_T6
        if (std::getenv(\"OAT_T6_IMAGE_METADATA_V1\") != nullptr)
        {
            const auto streamedPartCount = static_cast<unsigned int>(static_cast<unsigned char>(image->streamedPartCount));
            const auto part0HashRaw = streamedPartCount > 0 ? image->streamedParts[0].hash : 0u;
            con::info(
                \"T6_IMAGE_META_V1|name={}|hash={}|streaming={}|streamedPartCount={}|part0HashRaw={}|part0Hash29={}|width={}|height={}|depth={}|baseSize={}|loadedSize={}\",
                image->name,
                image->hash,
                static_cast<unsigned int>(static_cast<unsigned char>(image->streaming)),
                streamedPartCount,
                part0HashRaw,
                part0HashRaw & 0x1FFFFFFFu,
                image->width,
                image->height,
                image->depth,
                image->baseSize,
                image->loadedSize);
            return;
        }
#endif
        auto texture = CONVERTER_NAME().Convert(asset, context.m_obj_search_path);
"""
    text = text.replace(body_needle, body, 1)

    if text.count(ENV_NAME) != 1 or text.count(MARKER) != 1:
        raise SystemExit("metadata probe patch did not produce exactly one guarded logger")
    path.write_text(text, encoding="utf-8")
    print(f"patched: {TARGET}: T6 metadata-only GfxImage logger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
