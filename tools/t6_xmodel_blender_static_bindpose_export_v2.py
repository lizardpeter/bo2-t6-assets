#!/usr/bin/env python3
"""Blender-safe static bind-pose GLB export for T6 XModels, v2.

v1 emitted the retail GfxPackedVertex.color field as glTF ``COLOR_0``. That is
not a lossless transport choice once a standard glTF material is attached:
``COLOR_0`` has defined PBR semantics and multiplies base color/alpha. T6's
32-bit vertex field is shader input whose per-material meaning has to be proven
from the retail technique; treating it as a universal albedo multiplier is an
inference.

v2 therefore preserves the exact same accessor under the custom attribute
``_T6_COLOR_RGBA``. This keeps the retail bytes available to Blender/custom
importers while preventing glTF PBR from silently changing the texture.
Geometry, UVs, normals, topology and coordinates are otherwise byte-for-byte
identical to the v1 export's decoded values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from t6_xmodel_blender_static_bindpose_export_v1 import export as export_v1

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


def _read_glb(blob: bytes) -> tuple[dict, bytes]:
    magic, version, total = struct.unpack_from('<4sII', blob, 0)
    if magic != b'glTF' or version != 2 or total != len(blob):
        raise ValueError('invalid GLB')
    p = 12
    doc = None
    bin_chunk = None
    while p < len(blob):
        n, typ = struct.unpack_from('<II', blob, p)
        p += 8
        raw = blob[p:p+n]
        p += n
        if typ == JSON_CHUNK:
            doc = json.loads(raw.rstrip(b' \t\r\n\0'))
        elif typ == BIN_CHUNK:
            bin_chunk = raw
    if doc is None or bin_chunk is None:
        raise ValueError('GLB missing JSON or BIN chunk')
    return doc, bin_chunk


def _emit_glb(doc: dict, bin_chunk: bytes) -> bytes:
    raw_bin = bytearray(bin_chunk)
    while len(raw_bin) % 4:
        raw_bin.append(0)
    doc['buffers'] = [{'byteLength': len(raw_bin)}]
    raw_json = json.dumps(doc, separators=(',', ':'), ensure_ascii=False).encode()
    raw_json += b' ' * ((-len(raw_json)) % 4)
    total = 12 + 8 + len(raw_json) + 8 + len(raw_bin)
    out = bytearray(struct.pack('<4sII', b'glTF', 2, total))
    out += struct.pack('<II', len(raw_json), JSON_CHUNK) + raw_json
    out += struct.pack('<II', len(raw_bin), BIN_CHUNK) + raw_bin
    return bytes(out)


def demote_color0(blob: bytes) -> bytes:
    doc, bin_chunk = _read_glb(blob)
    changed = 0
    for mesh in doc.get('meshes', []):
        for prim in mesh.get('primitives', []):
            attrs = prim.get('attributes', {})
            if 'COLOR_0' not in attrs:
                continue
            if '_T6_COLOR_RGBA' in attrs:
                raise ValueError('primitive already has _T6_COLOR_RGBA')
            attrs['_T6_COLOR_RGBA'] = attrs.pop('COLOR_0')
            changed += 1
    if changed == 0:
        raise ValueError('expected at least one T6 COLOR_0 accessor to demote')
    doc.setdefault('asset', {})['generator'] = 'bo2-t6-assets t6_xmodel_blender_static_bindpose_export_v2.py'
    for node in doc.get('nodes', []):
        ex = node.setdefault('extras', {})
        ex['t6VertexColorTransport'] = '_T6_COLOR_RGBA custom attribute; exact decoded GfxPackedVertex.color retained without glTF PBR COLOR_0 semantics'
    for mesh in doc.get('meshes', []):
        for prim in mesh.get('primitives', []):
            attrs = prim.get('attributes', {})
            if 'COLOR_0' in attrs:
                raise AssertionError('COLOR_0 remained after demotion')
            if '_T6_COLOR_RGBA' not in attrs:
                raise AssertionError('T6 color accessor missing after demotion')
    return _emit_glb(doc, bin_chunk)


def export(mesh_doc: dict, lod: int = 0) -> bytes:
    return demote_color0(export_v1(mesh_doc, lod))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('mesh_json', type=Path)
    ap.add_argument('output_glb', type=Path)
    ap.add_argument('--lod', type=int, default=0)
    args = ap.parse_args()
    mesh = json.loads(args.mesh_json.read_text(encoding='utf-8'))
    raw = export(mesh, args.lod)
    args.output_glb.write_bytes(raw)
    print(json.dumps({'out': str(args.output_glb), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
