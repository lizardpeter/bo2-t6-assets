#!/usr/bin/env python3
"""Force pinned OAT T6 TechniqueSet dumper debug comments on.

Diagnostic-only source patch. It changes only the DumperT6 constructor argument
from the compile-time TECHSET_DEBUG switch to literal true, causing
CommonTechniqueDumper to emit its existing exact
  // Omitted due to matching accessors: ...
comments for CODE_CONST and CODE_SAMPLER arguments.

Material arguments are not omitted by CommonTechniqueDumper and are unaffected.
"""
from __future__ import annotations
import argparse
from pathlib import Path

def replace_once(path:Path,old:str,new:str):
    s=path.read_text()
    if new in s:
        if old in s: raise RuntimeError("mixed old/new debug patch")
        return "already-patched"
    if s.count(old)!=1:
        raise RuntimeError(f"expected exactly one T6 dumper debug block, got {s.count(old)}")
    path.write_text(s.replace(old,new,1))
    return "patched"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("oat_root",type=Path);a=ap.parse_args()
    p=a.oat_root.resolve()/"src/ObjWriting/Game/T6/ObjWriterT6.cpp"
    if not p.is_file(): raise SystemExit("pinned OAT T6 ObjWriter path absent")
    old='''    RegisterAssetDumper(std::make_unique<techset::DumperT6>(
#ifdef TECHSET_DEBUG
        true
#else
        false
#endif
        ));'''
    new='''    // bo2-t6-assets diagnostic build: preserve OAT's own exact comments for
    // matching-accessor code constants/samplers that normal dumps omit.
    RegisterAssetDumper(std::make_unique<techset::DumperT6>(true));'''
    print(replace_once(p,old,new))
    return 0
if __name__=="__main__":raise SystemExit(main())
