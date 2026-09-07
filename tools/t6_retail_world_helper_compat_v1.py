#!/usr/bin/env python3
"""Compatibility surface for retained T6 world TechniqueSet parsers.

The current authoritative retained-world helper is
`t6_retail_world_formats_45_proof_v1.py`, whose APIs are `front`, `scan_tech`,
and `dec`. Older retained TechniqueSet parsers call `parse_front`,
`scan_techsets`, and `decode_zone_pointer`.

This module performs naming/shape adaptation only. Pointer decoding and byte
scanning remain delegated to the current helper unchanged.
"""
from __future__ import annotations

import t6_retail_world_formats_45_proof_v1 as base

front = base.front
scan_tech = base.scan_tech
dec = base.dec


def decode_zone_pointer(raw: int, blocks):
    kind, block, offset = base.dec(raw, blocks)
    names = {
        'null': 'null',
        'follow': 'following',
        'insert': 'insert',
        'packed': 'packed',
        'bad': 'bad',
    }
    if kind not in names:
        raise ValueError(f'unsupported current-helper pointer kind {kind!r}')
    out = {'kind': names[kind]}
    if kind in ('packed', 'bad'):
        out['block'] = int(block)
        out['offset'] = int(offset)
    return out


def parse_front(data: bytes):
    blocks, assets = base.front(data)
    return {'blockSizes': blocks, 'assets': assets}


def scan_techsets(data: bytes, blocks, *, before: int):
    return [
        {
            **row,
            'fixedStart': int(row['start']),
            'worldVertFormat': int(row['fmt']),
        }
        for row in base.scan_tech(data, blocks, before)
    ]


PROOF_BOUNDARY = (
    'API compatibility only: decode_zone_pointer delegates to current helper dec; '
    'parse_front delegates to front; scan_techsets delegates to scan_tech. No '
    'pointer class, offset, byte range, or TechniqueSet candidate is inferred.'
)
