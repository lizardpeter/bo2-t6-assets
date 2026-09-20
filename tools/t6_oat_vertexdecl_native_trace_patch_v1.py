#!/usr/bin/env python3
"""Instrument pinned OAT for exact T6 block-5 offset -> native VertexDecl field joins.

Patch scope is diagnostic only:
- ZoneInputStream: log block-5 raw offset conversions and resolved addresses.
- T6 Techset conversion: log native MaterialVertexDeclaration address and every
  serialized/runtime field OAT sees before common-format conversion.

The patch does not alter pointer resolution, object fields, routing, or dumping.
"""
from __future__ import annotations
import argparse
from pathlib import Path

def replace_once(path:Path,old:str,new:str,label:str):
    s=path.read_text()
    if new in s:
        if old in s: raise RuntimeError(f"{label}: mixed old/new")
        return "already-patched"
    if s.count(old)!=1: raise RuntimeError(f"{label}: expected one old block, got {s.count(old)}")
    s=s.replace(old,new,1)
    if s.count(new)!=1: raise RuntimeError(f"{label}: replacement failed")
    path.write_text(s)
    return "patched"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("oat_root",type=Path);a=ap.parse_args()
    root=a.oat_root.resolve()
    z=root/"src/ZoneLoading/Zone/Stream/ZoneInputStream.cpp"
    t=root/"src/ObjWriting/Techset/TechsetDumper.cpp.template"
    if not z.is_file() or not t.is_file(): raise SystemExit("pinned OAT paths absent")

    old_native="""            return &block->m_buffer[blockOffset];
        }

        void* ConvertOffsetToAliasNative"""
    new_native="""            auto* resolvedPointer = &block->m_buffer[blockOffset];
            if (blockNum == 5)
            {
                std::cerr << "T6_BLOCK5_OFFSET_NATIVE raw=0x" << std::hex << reinterpret_cast<uintptr_t>(offset)
                          << " decoded=0x" << offsetInt << " resolved=0x" << reinterpret_cast<uintptr_t>(resolvedPointer)
                          << std::dec << "\\n";
            }
            return resolvedPointer;
        }

        void* ConvertOffsetToAliasNative"""
    print(replace_once(z,old_native,new_native,"native pointer conversion"))

    old_lookup="""            const auto foundPointerLookup = m_pointer_redirect_lookup.find(offsetInt);
            if (foundPointerLookup != m_pointer_redirect_lookup.end())
                return MaybePointerFromLookup<void>(foundPointerLookup->second);

            return MaybePointerFromLookup<void>(&block->m_buffer[blockOffset], blockNum, blockOffset);
        }

        void* ConvertOffsetToAliasLookup"""
    new_lookup="""            const auto foundPointerLookup = m_pointer_redirect_lookup.find(offsetInt);
            if (foundPointerLookup != m_pointer_redirect_lookup.end())
            {
                if (blockNum == 5)
                {
                    std::cerr << "T6_BLOCK5_OFFSET_LOOKUP raw=0x" << std::hex << reinterpret_cast<uintptr_t>(offset)
                              << " decoded=0x" << offsetInt << " resolved=0x"
                              << reinterpret_cast<uintptr_t>(foundPointerLookup->second) << " redirected=1"
                              << std::dec << "\\n";
                }
                return MaybePointerFromLookup<void>(foundPointerLookup->second);
            }

            auto* resolvedPointer = &block->m_buffer[blockOffset];
            if (blockNum == 5)
            {
                std::cerr << "T6_BLOCK5_OFFSET_LOOKUP raw=0x" << std::hex << reinterpret_cast<uintptr_t>(offset)
                          << " decoded=0x" << offsetInt << " resolved=0x" << reinterpret_cast<uintptr_t>(resolvedPointer)
                          << " redirected=0" << std::dec << "\\n";
            }
            return MaybePointerFromLookup<void>(resolvedPointer, blockNum, blockOffset);
        }

        void* ConvertOffsetToAliasLookup"""
    print(replace_once(z,old_lookup,new_lookup,"lookup pointer conversion"))

    inc_old="#include <cassert>\n#include <format>\n"
    inc_new="#include <cassert>\n#include <cstdint>\n#include <format>\n#include <iostream>\n"
    print(replace_once(t,inc_old,inc_new,"techset includes"))

    old_decl="""    techset::CommonVertexDeclaration ConvertToCommonVertexDeclaration(const MaterialVertexDeclaration* vertexDecl)
    {
        std::vector<techset::CommonStreamRouting> commonRouting;

#if defined(FEATURE_IW4) || defined(FEATURE_IW5)"""
    new_decl="""    techset::CommonVertexDeclaration ConvertToCommonVertexDeclaration(const MaterialVertexDeclaration* vertexDecl)
    {
#ifdef FEATURE_T6
        if (vertexDecl)
        {
            const auto nativeStreamCount =
                std::min(static_cast<size_t>(vertexDecl->streamCount), std::extent_v<decltype(MaterialVertexStreamRouting::data)>);
            std::cerr << "T6_VERTEXDECL_NATIVE ptr=0x" << std::hex << reinterpret_cast<uintptr_t>(vertexDecl) << std::dec
                      << " streamCount=" << static_cast<unsigned>(vertexDecl->streamCount)
                      << " hasOptionalSource=" << static_cast<unsigned>(vertexDecl->hasOptionalSource)
                      << " isLoaded=" << static_cast<unsigned>(vertexDecl->isLoaded)
                      << " routing=";
            for (auto streamIndex = 0u; streamIndex < nativeStreamCount; streamIndex++)
            {
                if (streamIndex)
                    std::cerr << ",";
                const auto& nativeRouting = vertexDecl->routing.data[streamIndex];
                std::cerr << static_cast<unsigned>(nativeRouting.source) << ":" << static_cast<unsigned>(nativeRouting.dest);
            }
            std::cerr << "\\n";
        }
#endif

        std::vector<techset::CommonStreamRouting> commonRouting;

#if defined(FEATURE_IW4) || defined(FEATURE_IW5)"""
    print(replace_once(t,old_decl,new_decl,"T6 VertexDecl diagnostic"))
    return 0
if __name__=="__main__":raise SystemExit(main())
