#!/usr/bin/env python3
"""Move selected glTF scene roots out of the canonical scene without touching data.

This is an authoring/scene-organization operation only. Nodes, meshes, skins,
animations, materials, accessors and BIN bytes are preserved exactly. The tool
appends two scenes:
  * support scene containing matching roots
  * clean canonical scene containing the remaining roots

Useful for T6 `fxanim_*` helper geometry that must remain preserved but should
not obstruct Blender/Tour authoring views.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942

def read_glb(path: Path):
    data = path.read_bytes()
    magic, ver, total = struct.unpack_from('<4sII', data, 0)
    if magic != b'glTF' or ver != 2 or total != len(data):
        raise ValueError('invalid GLB2')
    o = 12; js = None; bb = None
    while o < total:
        n, t = struct.unpack_from('<II', data, o); o += 8
        c = data[o:o+n]; o += n
        if t == JSON_CHUNK: js = json.loads(c.rstrip(b' \0\t\r\n'))
        elif t == BIN_CHUNK: bb = c
    if js is None or bb is None: raise ValueError('missing GLB chunks')
    return data, js, bb

def write_glb(path: Path, js, bb: bytes):
    jb = json.dumps(js, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    jb += b' ' * ((-len(jb)) % 4)
    bd = bb + b'\0' * ((-len(bb)) % 4)
    js['buffers'][0]['byteLength'] = len(bb)
    # buffer byteLength update changes JSON; regenerate once.
    jb = json.dumps(js, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    jb += b' ' * ((-len(jb)) % 4)
    total = 12 + 8 + len(jb) + 8 + len(bd)
    out = bytearray(struct.pack('<4sII', b'glTF', 2, total))
    out += struct.pack('<II', len(jb), JSON_CHUNK) + jb
    out += struct.pack('<II', len(bd), BIN_CHUNK) + bd
    path.write_bytes(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--scene-index', type=int)
    ap.add_argument('--pattern', action='append', default=[])
    ap.add_argument('--support-scene-name', default='T6 Animation Support XModels')
    ap.add_argument('--canonical-scene-name', default='T6 Canonical Map')
    ap.add_argument('--report', type=Path)
    a = ap.parse_args()

    source_bytes, js, bb = read_glb(a.input)
    if not a.pattern:
        a.pattern = ['__fxanim_']
    si = int(js.get('scene', 0) if a.scene_index is None else a.scene_index)
    roots = list(js['scenes'][si].get('nodes', []))
    nodes = js.get('nodes', [])
    support = []
    keep = []
    for i in roots:
        name = str(nodes[i].get('name') or '')
        if any(p.lower() in name.lower() for p in a.pattern): support.append(i)
        else: keep.append(i)
    if not support:
        raise SystemExit('no matching support roots; refusing to create a no-op checkpoint')

    original_counts = {k: len(js.get(k, [])) for k in ('nodes','meshes','materials','images','textures','accessors','bufferViews','animations','skins','scenes')}
    support_scene = len(js['scenes'])
    js['scenes'].append({'name': a.support_scene_name, 'nodes': support,
                         'extras': {'T6': {'previewOnly': True, 'patterns': a.pattern,
                         'policy': 'Scene migration only; underlying nodes/assets remain unchanged.'}}})
    canonical_scene = len(js['scenes'])
    js['scenes'].append({'name': a.canonical_scene_name, 'nodes': keep,
                         'extras': {'T6': {'supportRootsIsolated': len(support), 'sourceSceneIndex': si}}})
    js['scene'] = canonical_scene
    write_glb(a.output, js, bb)

    out_bytes, out_js, out_bb = read_glb(a.output)
    unchanged = all(out_js.get(k, [])[:original_counts[k]] == js.get(k, [])[:original_counts[k]]
                    for k in original_counts if k != 'scenes') and out_bb[:len(bb)] == bb
    report = {
        'format': 't6-glb-isolate-support-scene-v1',
        'input': {'file': a.input.name, 'bytes': len(source_bytes), 'sha256': hashlib.sha256(source_bytes).hexdigest()},
        'output': {'file': a.output.name, 'bytes': len(out_bytes), 'sha256': hashlib.sha256(out_bytes).hexdigest()},
        'sourceSceneIndex': si,
        'patterns': a.pattern,
        'supportRootCount': len(support),
        'canonicalRootCount': len(keep),
        'supportRootNames': [str(nodes[i].get('name') or '') for i in support],
        'supportSceneIndex': support_scene,
        'canonicalSceneIndex': canonical_scene,
        'underlyingArraysAndBinaryPreserved': unchanged,
    }
    if a.report: a.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
