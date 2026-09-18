#!/usr/bin/env python3
"""Instrument pinned OAT's T6 image converter with packed identity fields.

Diagnostic-only source patch. It does not alter image resolution or loading.
"""
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/ObjWriting/Image/ImageToCommonConverter.cpp.template'
s=p.read_text()
needle='''#ifdef FEATURE_T6\n        if (image.streamedPartCount > 0)\n        {\n            for (auto* ipak : IIPak::Repository)\n'''
repl='''#ifdef FEATURE_T6\n        if (image.streamedPartCount > 0)\n        {\n            con::info("T6_GFXIMAGE_PACKED name={} nameHash={} dataHash={} streamedParts={} width={} height={} depth={}", image.name ? image.name : "<null>", image.hash, image.streamedParts[0].hash, image.streamedPartCount, image.width, image.height, image.depth);\n            for (auto* ipak : IIPak::Repository)\n'''
if s.count(needle)!=1: raise SystemExit(f'expected one T6 converter insertion site, got {s.count(needle)}')
p.write_text(s.replace(needle,repl))
print(p)
