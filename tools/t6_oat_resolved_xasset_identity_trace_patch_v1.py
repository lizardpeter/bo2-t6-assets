#!/usr/bin/env python3
"""Add diagnostic native resolved-identity tracing to pinned OAT T6.

Apply after `t6_oat_expanded_xasset_trace_patch_v1.py`.

For every top-level XAsset, this records:
- the raw serialized header encoding present before dispatch,
- the resolved native pointer after the real loader completes,
- the first top-level XAsset index seen with that same resolved pointer,
- for XMODEL only, the name field read from the resolved native XModel object.

The process address itself is diagnostic and not a durable identity. The durable
within-run equality relation (`resolvedOwnerIndex`) plus raw header encoding and
native resolved object name is intended to close zero-source top-level reference
semantics without scanning source bytes or inferring ownership from adjacency.
No loader behavior, pointer conversion, block allocation, or source consumption
is changed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED = "9dca965366541504b71fa8cfb7ac049cb9b717e1"
TARGET = Path("src/ZoneLoading/Game/T6/ContentLoaderT6.cpp")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one patch anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oat", type=Path)
    args = ap.parse_args()
    path = args.oat / TARGET
    if not path.is_file():
        raise SystemExit(f"missing pinned OAT source: {path}")
    text = path.read_text(encoding="utf-8")
    if "T6_RESOLVED_XASSET" in text:
        print("resolved XAsset identity trace already present")
        return 0
    if "T6_EXPANDED_XASSET" not in text or "SerializedBytesRead()" not in text:
        raise SystemExit(
            "expanded XAsset trace patch is missing; apply "
            "t6_oat_expanded_xasset_trace_patch_v1.py first"
        )

    replace_once(
        path,
        "#include <iostream>\n",
        "#include <iostream>\n#include <unordered_map>\n",
    )
    replace_once(
        path,
        "    for (size_t index = 0; index < count; index++)\n    {\n        const auto traceType = varXAsset->type;\n        const auto traceBeforeLocal = m_stream.SerializedBytesRead();\n        LoadXAsset(false);",
        "    std::unordered_map<const void*, size_t> t6ResolvedTopLevelOwner;\n"
        "    for (size_t index = 0; index < count; index++)\n"
        "    {\n"
        "        const auto traceType = varXAsset->type;\n"
        "        const auto traceHeaderRaw = reinterpret_cast<uintptr_t>(varXAsset->header.data);\n"
        "        const auto traceBeforeLocal = m_stream.SerializedBytesRead();\n"
        "        LoadXAsset(false);",
    )
    replace_once(
        path,
        "        std::cerr << \"T6_EXPANDED_XASSET index=\" << index\n"
        "                  << \" type=\" << traceType\n"
        "                  << \" beforeLocal=\" << traceBeforeLocal\n"
        "                  << \" afterLocal=\" << traceAfterLocal\n"
        "                  << \" before=\" << (40u + traceBeforeLocal)\n"
        "                  << \" after=\" << (40u + traceAfterLocal) << '\\n';\n"
        "        varXAsset++;",
        "        std::cerr << \"T6_EXPANDED_XASSET index=\" << index\n"
        "                  << \" type=\" << traceType\n"
        "                  << \" beforeLocal=\" << traceBeforeLocal\n"
        "                  << \" afterLocal=\" << traceAfterLocal\n"
        "                  << \" before=\" << (40u + traceBeforeLocal)\n"
        "                  << \" after=\" << (40u + traceAfterLocal) << '\\n';\n"
        "        const void* traceResolved = varXAsset->header.data;\n"
        "        size_t traceOwnerIndex = index;\n"
        "        bool traceSeen = false;\n"
        "        if (traceResolved != nullptr)\n"
        "        {\n"
        "            const auto [it, inserted] = t6ResolvedTopLevelOwner.emplace(traceResolved, index);\n"
        "            traceOwnerIndex = it->second;\n"
        "            traceSeen = !inserted;\n"
        "        }\n"
        "        std::cerr << \"T6_RESOLVED_XASSET index=\" << index\n"
        "                  << \" type=\" << traceType\n"
        "                  << \" rawHeader=0x\" << std::hex << traceHeaderRaw << std::dec\n"
        "                  << \" resolved=0x\" << std::hex << reinterpret_cast<uintptr_t>(traceResolved) << std::dec\n"
        "                  << \" resolvedOwnerIndex=\" << traceOwnerIndex\n"
        "                  << \" resolvedSeenEarlier=\" << (traceSeen ? 1 : 0);\n"
        "        if (traceType == ASSET_TYPE_XMODEL && varXAsset->header.model != nullptr)\n"
        "            std::cerr << \" xmodelName=\"\n"
        "                      << (varXAsset->header.model->name != nullptr ? varXAsset->header.model->name : \"<null>\");\n"
        "        std::cerr << '\\n';\n"
        "        varXAsset++;",
    )
    print("patched pinned OAT with diagnostic-only resolved XAsset identity trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
