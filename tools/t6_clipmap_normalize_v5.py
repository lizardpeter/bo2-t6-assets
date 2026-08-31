#!/usr/bin/env python3
"""T6 ClipMap normalized collision exporter v5.

Extends v4 by resolving every cStaticModel_s::xmodel packed pointer to the
exact top-level XAsset index. Resolution uses XAsset-header pointer-slot
identity: a packed model reference targets VIRTUAL base + assetIndex*8 + 4.
The VIRTUAL base is solved uniquely from all distinct static-model references
and the XAsset type table; no model-name or placement heuristics are used.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from collections import Counter
from pathlib import Path
from t6_clipmap_normalize_v1 import normalize as normalize_v1
from t6_clipmap_normalize_v2 import resolve_planes
from t6_clipmap_normalize_v3 import resolve_leafbrushes
from t6_clipmap_normalize_v4 import decode_static_models, decode_constraints
from t6_clipmap_serialized_walker import ptr_kind

XASSETLIST_RAW_START = 40
XASSET_SIZE = 8
ASSET_TYPE_XMODEL = 5
PTR_FOLLOWING = 0xFFFFFFFF


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _read_cstr_end(data: bytes, pos: int, max_len: int = 1 << 20) -> int:
    end = data.find(b'\0', pos, min(len(data), pos + max_len))
    if end < 0:
        raise ValueError(f'unterminated serialized string at raw offset {pos}')
    return end + 1


def parse_top_level_xasset_table(data: bytes) -> dict:
    p = XASSETLIST_RAW_START
    script_count = _u32(data, p + 0)
    script_ptr = _u32(data, p + 4)
    depend_count = _u32(data, p + 8)
    depends_ptr = _u32(data, p + 12)
    asset_count = _u32(data, p + 16)
    assets_ptr = _u32(data, p + 20)
    if script_ptr != PTR_FOLLOWING:
        raise ValueError(f'XAssetList stringList.strings must be FOLLOWING, got 0x{script_ptr:08X}')
    if assets_ptr != PTR_FOLLOWING:
        raise ValueError(f'XAssetList assets must be FOLLOWING, got 0x{assets_ptr:08X}')
    if depend_count != 0 or depends_ptr != 0:
        raise ValueError('v5 raw XAsset table locator currently requires zero dependency strings')
    cur = p + 24
    if cur + script_count * 4 > len(data):
        raise ValueError('script-string pointer table is truncated')
    string_ptrs = struct.unpack_from(f'<{script_count}I', data, cur) if script_count else ()
    cur += script_count * 4
    string_kinds = Counter()
    for raw in string_ptrs:
        q = ptr_kind(raw)
        string_kinds[q['kind']] += 1
        if q['kind'] == 'following':
            cur = _read_cstr_end(data, cur)
        elif q['kind'] == 'null':
            pass
        else:
            raise ValueError(f'cannot source-walk non-inline script string pointer: {q}')
    asset_array_start = cur
    end = asset_array_start + asset_count * XASSET_SIZE
    if end > len(data):
        raise ValueError('XAsset table is truncated')
    entries = []
    for i in range(asset_count):
        off = asset_array_start + i * XASSET_SIZE
        typ, raw_header = struct.unpack_from('<II', data, off)
        if not (0 <= typ < 128):
            raise ValueError(f'implausible XAsset type {typ} at index {i}')
        entries.append({'index': i, 'type': typ, 'headerPointerRaw': raw_header, 'rawStart': off})
    return {
        'rawStart': p,
        'scriptStringCount': script_count,
        'scriptStringPointerKinds': dict(sorted(string_kinds.items())),
        'dependCount': depend_count,
        'assetCount': asset_count,
        'assetArrayRawStart': asset_array_start,
        'assetArrayRawEnd': end,
        'entries': entries,
    }


def resolve_static_xmodel_assets(out: dict, data: bytes) -> dict:
    table = parse_top_level_xasset_table(data)
    entries = table['entries']
    types = [e['type'] for e in entries]
    xmodel_indices = [i for i, typ in enumerate(types) if typ == ASSET_TYPE_XMODEL]
    if not xmodel_indices:
        raise ValueError('top-level XAsset table contains no XMODEL entries')

    refs = []
    for row in out['staticModels']:
        p = row['xModelPointer']
        if p.get('kind') != 'packed' or p.get('block') != 5:
            raise ValueError(f'staticModels[{row["index"]}].xModelPointer is not packed VIRTUAL: {p}')
        refs.append(int(p['offset']))
    distinct_offsets = sorted(set(refs))
    if not distinct_offsets:
        summary = {
            'xAssetList': {k: v for k, v in table.items() if k != 'entries'},
            'xAssetVirtualBase': None,
            'placementCount': 0,
            'uniqueXModelAssetCount': 0,
            'uniqueTargets': [],
            'status': 'no_static_models',
        }
        out['staticModelXModelAssetResolution'] = summary
        return summary

    first = distinct_offsets[0]
    candidates = []
    for idx in xmodel_indices:
        base = first - (idx * XASSET_SIZE + 4)
        ok = True
        for off in distinct_offsets:
            delta = off - base - 4
            q, rem = divmod(delta, XASSET_SIZE)
            if rem or not (0 <= q < len(entries)) or types[q] != ASSET_TYPE_XMODEL:
                ok = False
                break
        if ok:
            candidates.append(base)
    if len(candidates) != 1:
        raise ValueError(f'expected unique XAsset VIRTUAL base, got {candidates}')
    base = candidates[0]

    counts = Counter()
    for row, off in zip(out['staticModels'], refs):
        q, rem = divmod(off - base - 4, XASSET_SIZE)
        if rem or not (0 <= q < len(entries)):
            raise ValueError(f'static model pointer cannot resolve to XAsset index: row={row["index"]} off={off}')
        ent = entries[q]
        if ent['type'] != ASSET_TYPE_XMODEL:
            raise ValueError(f'static model row {row["index"]} resolves to non-XMODEL asset {q} type={ent["type"]}')
        expected_slot = base + q * XASSET_SIZE + 4
        if expected_slot != off:
            raise AssertionError((row['index'], off, expected_slot))
        row['xModelAssetIndex'] = q
        row['xModelAssetType'] = ASSET_TYPE_XMODEL
        row['xModelAssetTypeName'] = 'XMODEL'
        row['xModelAssetHeaderSlotLogicalOffset'] = expected_slot
        row['xModelAssetEntryRawStart'] = ent['rawStart']
        row['xModelAssetHeaderPointerRaw'] = ent['headerPointerRaw']
        counts[q] += 1

    targets = []
    for idx in sorted(counts):
        ent = entries[idx]
        targets.append({
            'assetIndex': idx,
            'placementCount': counts[idx],
            'xAssetEntryRawStart': ent['rawStart'],
            'xAssetHeaderPointerRaw': ent['headerPointerRaw'],
            'xAssetHeaderPointer': ptr_kind(ent['headerPointerRaw']),
            'xAssetHeaderSlotLogicalOffset': base + idx * XASSET_SIZE + 4,
        })
    summary = {
        'xAssetList': {k: v for k, v in table.items() if k != 'entries'},
        'xAssetVirtualBase': base,
        'candidateBaseCount': len(candidates),
        'placementCount': len(refs),
        'distinctPackedPointerCount': len(distinct_offsets),
        'uniqueXModelAssetCount': len(targets),
        'topLevelXModelAssetCount': len(xmodel_indices),
        'allReferencesResolveToXModel': True,
        'allReferencesEqualBasePlusAssetIndexTimes8Plus4': True,
        'uniqueTargets': targets,
        'status': 'resolved_by_xasset_header_pointer_slot_identity',
    }
    out['staticModelXModelAssetResolution'] = summary
    out['normalizationStatus']['staticModelXModelAssetsResolved'] = True
    out['normalizationStatus']['staticModelXModelAssetNamesResolved'] = False
    out['normalizationStatus']['unresolvedSemanticLinks'] = ['staticModels.xModelAssetName']
    out['format'] = 't6-clipmap-normalized-v5'
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--asset-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--gfxworld-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--plane-source-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    data = a.expanded.read_bytes()
    out, walk = normalize_v1(data, a.asset_start)
    planes = resolve_planes(out, data, gfxworld_start=a.gfxworld_start, plane_source_start=a.plane_source_start)
    leaf = resolve_leafbrushes(out, walk, data)
    sm = decode_static_models(out, walk, data)
    con = decode_constraints(out, walk, data)
    xm = resolve_static_xmodel_assets(out, data)
    out['expandedSha256'] = hashlib.sha256(data).hexdigest()
    out['normalizationStatus']['unexpandedOwnedSections'] = sorted(out['unexpandedSections'])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({
        'out': str(a.out),
        'bytes': a.out.stat().st_size,
        'sha256': hashlib.sha256(a.out.read_bytes()).hexdigest(),
        'planesResolved': planes['count'],
        'leafBrushesResolved': leaf['count'],
        'staticModels': sm,
        'constraints': con,
        'xModels': {
            'placements': xm['placementCount'],
            'uniqueAssets': xm['uniqueXModelAssetCount'],
            'virtualBase': xm['xAssetVirtualBase'],
            'candidateBaseCount': xm['candidateBaseCount'],
        },
        'unexpanded': out['unexpandedSections'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
