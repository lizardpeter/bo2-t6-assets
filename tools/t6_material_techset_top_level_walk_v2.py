#!/usr/bin/env python3
"""Exact T6 PC32 top-level Material/TechniqueSet serialized walker v2.

v2 preserves v1 semantics except for the nested T6 GfxImageLoadDef serializer.
Pinned T6 native layout stores `resourceSize` at +8 in the 12-byte load-def
prefix, followed immediately by the flexible `data[resourceSize]` byte array.
There is no data pointer at +8.

Historical v1 output remains immutable. Use v2 for any proof path that can
encounter inline GfxImage load definitions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from t6_material_techset_top_level_walk_v1 import (
    FOLLOW,
    INSERT,
    MATERIAL,
    TECHSET,
    Cursor as CursorV1,
    dec,
    inline,
    parse_front,
)


class Cursor(CursorV1):
    def image(self) -> dict:
        s = self.take(80)
        load = struct.unpack_from('<I', self.d, s)[0]
        namep = struct.unpack_from('<I', self.d, s + 72)[0]
        name = self.string(namep)
        ld = None
        if inline(load):
            ls = self.take(12)
            resource = struct.unpack_from('<I', self.d, ls + 8)[0]
            ds = self.take(resource) if resource else None
            ld = {
                'fixedStart': ls,
                'resourceSize': resource,
                'dataStart': ds,
                'dataEnd': self.p if resource else None,
                'layout': 'T6 GfxImageLoadDef 12-byte prefix + flexible data[resourceSize]',
            }
        return {
            'fixedStart': s,
            'end': self.p,
            'name': name,
            'loadDefPointer': dec(load, self.blocks),
            'loadDef': ld,
        }


def walk(d: bytes, start_asset: int, end_asset: int, source_start: int) -> dict:
    blocks, assets, _ = parse_front(d)
    c = Cursor(d, source_start, blocks)
    rows = []
    for q in range(start_asset, end_asset + 1):
        a = assets[q]
        if a['headerRaw'] not in (FOLLOW, INSERT):
            raise ValueError(f'XAsset {q} top-level header is not inline')
        before = c.p
        if a['type'] == MATERIAL:
            r = c.material()
        elif a['type'] == TECHSET:
            r = c.techset()
        else:
            raise ValueError(
                f'unsupported top-level XAsset type {a["type"]} at {q}; walker is intentionally fail-closed'
            )
        r.update(
            {
                'xassetIndex': q,
                'xassetType': a['type'],
                'sourceStart': before,
                'sourceEnd': c.p,
            }
        )
        rows.append(r)
    return {
        'format': 't6-material-techset-top-level-walk-v2',
        'startAssetIndex': start_asset,
        'endAssetIndex': end_asset,
        'sourceStart': source_start,
        'sourceEnd': c.p,
        'rows': rows,
        'inlineShaderCount': len(c.inlineShaders),
        'directInlineShaders': [
            x for x in c.inlineShaders if x.get('program') and x['program'].get('direct')
        ],
        'proofBoundary': [
            'GfxImageLoadDef resourceSize is read from +8 per pinned T6 native structure layout.',
            'GfxImageLoadDef data is consumed directly as resourceSize inline bytes per pinned T6 ZoneCode arraysize rule.',
            'Historical v1 output is not retroactively changed; any v1 proof involving inline image load-def payloads must be rerun with v2 before promotion.',
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--start-asset', type=int, required=True)
    ap.add_argument('--end-asset', type=int, required=True)
    ap.add_argument('--source-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--expect-end', type=lambda x: int(x, 0))
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    d = a.expanded.read_bytes()
    o = walk(d, a.start_asset, a.end_asset, a.source_start)
    o['expandedSha256'] = hashlib.sha256(d).hexdigest()
    if a.expect_end is not None:
        o['expectedEnd'] = a.expect_end
        o['expectedEndMatches'] = o['sourceEnd'] == a.expect_end
        if not o['expectedEndMatches']:
            raise SystemExit(f'end {o["sourceEnd"]} != expected {a.expect_end}')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(o, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(
        json.dumps(
            {
                'sourceEnd': o['sourceEnd'],
                'assetCount': len(o['rows']),
                'inlineShaderCount': o['inlineShaderCount'],
            },
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
