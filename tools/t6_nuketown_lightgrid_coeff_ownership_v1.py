#!/usr/bin/env python3
"""Retail-byte verifier for Nuketown 2020 T6 GfxLightGrid + coeff ownership.

This is intentionally map-specific proof code. It validates the exact expanded
retail mp_nuketown_2020 FastFile, reads the GfxWorld light-grid fixed record,
replays its serialized arrays from the independently retained end of the
GfxWorld draw/index stream, and joins coefficient indices against the existing
source-derived 2,992 GfxStaticModelDrawInst placement manifest.

No GLB is an input.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, struct
from pathlib import Path

FOLLOWING = 0xFFFFFFFF
EXPECTED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
GFXWORLD_START = 63_150_420
LIGHTGRID_FIXED_OFFSET = 464
LIGHTGRID_SIZE = 72
MODEL_COUNT_OFFSET = 536
MODELS_PTR_OFFSET = 540
EXPECTED_MODEL_COUNT = 184
# Independently retained GfxWorld draw proof: second lightmap image -> vd0 -> vd1 -> indices.
DRAW_INDEX_END = 82_103_528
EXPECTED_STATIC_COUNT = 2_992


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def u32(d: bytes, o: int) -> int:
    return struct.unpack_from('<I', d, o)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--placements', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()

    d = a.expanded.read_bytes()
    got_sha = sha(d)
    if got_sha != EXPECTED_SHA256:
        raise SystemExit(f'expanded SHA mismatch: {got_sha}')

    lg = GFXWORLD_START + LIGHTGRID_FIXED_OFFSET
    fixed = d[lg:lg + LIGHTGRID_SIZE]
    if len(fixed) != LIGHTGRID_SIZE:
        raise SystemExit('truncated light-grid fixed record')

    sun = u32(d, lg + 0)
    mins = list(struct.unpack_from('<3H', d, lg + 4))
    maxs = list(struct.unpack_from('<3H', d, lg + 10))
    offset = struct.unpack_from('<f', d, lg + 16)[0]
    row_axis = u32(d, lg + 20)
    col_axis = u32(d, lg + 24)
    row_ptr = u32(d, lg + 28)
    raw_size = u32(d, lg + 32)
    raw_ptr = u32(d, lg + 36)
    entry_count = u32(d, lg + 40)
    entry_ptr = u32(d, lg + 44)
    color_count = u32(d, lg + 48)
    color_ptr = u32(d, lg + 52)
    coeff_count = u32(d, lg + 56)
    coeff_ptr = u32(d, lg + 60)
    sky_count = u32(d, lg + 64)
    sky_ptr = u32(d, lg + 68)

    if row_axis not in (0, 1) or col_axis not in (0, 1) or row_axis == col_axis:
        raise SystemExit(f'bad row/col axes: {row_axis}/{col_axis}')
    row_count = maxs[row_axis] - mins[row_axis] + 1

    expected = {
        'sunPrimaryLightIndex': 1,
        'mins': [4027, 4035, 2046],
        'maxs': [4163, 4166, 2065],
        'offset': 12.0,
        'rowAxis': 1,
        'colAxis': 0,
        'rowDataStartPointer': FOLLOWING,
        'rawRowDataSize': 3524,
        'rawRowDataPointer': FOLLOWING,
        'entryCount': 37685,
        'entriesPointer': FOLLOWING,
        'colorCount': 0,
        'colorsPointer': 0,
        'coeffCount': 40615,
        'coeffsPointer': FOLLOWING,
        'skyGridVolumeCount': 0,
        'skyGridVolumesPointer': 0,
        'rowCount': 132,
    }
    actual = {
        'sunPrimaryLightIndex': sun, 'mins': mins, 'maxs': maxs, 'offset': offset,
        'rowAxis': row_axis, 'colAxis': col_axis,
        'rowDataStartPointer': row_ptr, 'rawRowDataSize': raw_size,
        'rawRowDataPointer': raw_ptr, 'entryCount': entry_count,
        'entriesPointer': entry_ptr, 'colorCount': color_count,
        'colorsPointer': color_ptr, 'coeffCount': coeff_count,
        'coeffsPointer': coeff_ptr, 'skyGridVolumeCount': sky_count,
        'skyGridVolumesPointer': sky_ptr, 'rowCount': row_count,
    }
    for k, v in expected.items():
        if actual[k] != v:
            raise SystemExit(f'fixed-record drift: {k}: got {actual[k]!r}, expected {v!r}')

    if u32(d, GFXWORLD_START + MODEL_COUNT_OFFSET) != EXPECTED_MODEL_COUNT:
        raise SystemExit('GfxWorld.modelCount control drift')
    if u32(d, GFXWORLD_START + MODELS_PTR_OFFSET) != FOLLOWING:
        raise SystemExit('GfxWorld.models pointer is not FOLLOWING')

    row_start = DRAW_INDEX_END
    raw_start = row_start + row_count * 2
    entries_start = raw_start + raw_size
    coeff_start = entries_start + entry_count * 4
    coeff_end = coeff_start + coeff_count * 54

    row_blob = d[row_start:raw_start]
    raw_blob = d[raw_start:entries_start]
    entry_blob = d[entries_start:coeff_start]
    coeff_blob = d[coeff_start:coeff_end]
    if len(coeff_blob) != coeff_count * 54:
        raise SystemExit('truncated coefficient payload')

    # rowDataStart values are 4-byte units into rawRowData. Validate every row
    # as the established 12-byte GfxLightGridRow header without interpreting the
    # trailing RLE bytecode beyond its bounds here.
    row_units = list(struct.unpack_from(f'<{row_count}H', row_blob, 0))
    row_headers = []
    for i, unit in enumerate(row_units):
        if unit == 0xFFFF:
            row_headers.append(None)
            continue
        ro = unit * 4
        if ro + 12 > raw_size:
            raise SystemExit(f'row {i}: header outside rawRowData')
        col_start, col_count, z_start, z_count, first_entry = struct.unpack_from('<HHHHI', raw_blob, ro)
        if not col_count or not z_count or first_entry >= entry_count:
            raise SystemExit(f'row {i}: invalid row header')
        row_headers.append({
            'rowIndex': i, 'rawOffsetUnits4': unit, 'rawByteOffset': ro,
            'colStart': col_start, 'colCount': col_count,
            'zStart': z_start, 'zCount': z_count, 'firstEntry': first_entry,
        })
    concrete_rows = [r for r in row_headers if r is not None]
    if len(concrete_rows) != row_count:
        raise SystemExit('unexpected absent row on Nuketown')
    if len({r['rawOffsetUnits4'] for r in concrete_rows}) != row_count:
        raise SystemExit('row offsets are not unique')
    if any(a['firstEntry'] >= b['firstEntry'] for a, b in zip(concrete_rows, concrete_rows[1:])):
        raise SystemExit('row firstEntry values are not strictly increasing')

    entries = []
    grid_coeff_indices = set()
    grid_primary = collections.Counter()
    visibility = collections.Counter()
    for i in range(entry_count):
        ci, pli, vis = struct.unpack_from('<HBB', entry_blob, i * 4)
        if ci >= coeff_count:
            raise SystemExit(f'entry {i}: colorsIndex {ci} >= coeffCount {coeff_count}')
        if pli != 0xFF and pli >= 18:
            raise SystemExit(f'entry {i}: primaryLightIndex {pli} outside 18-light ComWorld')
        grid_coeff_indices.add(ci)
        grid_primary[pli] += 1
        visibility[vis] += 1
        entries.append((ci, pli, vis))

    placements = json.loads(a.placements.read_text(encoding='utf-8'))
    if placements.get('map') != 'mp_nuketown_2020':
        raise SystemExit('wrong placement manifest map')
    instances = placements.get('instances', [])
    if len(instances) != EXPECTED_STATIC_COUNT:
        raise SystemExit(f'static placement count drift: {len(instances)}')
    proof = placements.get('proof', {})
    if proof.get('resolvedInstances') != EXPECTED_STATIC_COUNT or proof.get('unresolvedInstances') != 0:
        raise SystemExit('placement proof is not fully resolved')

    static_coeff_indices = set()
    static_primary = collections.Counter()
    static_visibility = collections.Counter()
    duplicate_static_coeff = []
    for x in instances:
        ci = int(x['colorsIndex'])
        pli = int(x['primaryLightIndex'])
        vis = int(x['visibility'])
        if ci >= coeff_count:
            raise SystemExit(f"static {x.get('index')}: colorsIndex {ci} >= coeffCount")
        if ci in static_coeff_indices:
            duplicate_static_coeff.append(ci)
        static_coeff_indices.add(ci)
        if pli >= 18:
            raise SystemExit(f"static {x.get('index')}: primaryLightIndex {pli} outside ComWorld")
        static_primary[pli] += 1
        static_visibility[vis] += 1
    if duplicate_static_coeff:
        raise SystemExit(f'static colorsIndex values are not unique: {duplicate_static_coeff[:8]}')

    overlap = grid_coeff_indices & static_coeff_indices
    union = grid_coeff_indices | static_coeff_indices
    missing_coeff_indices = sorted(set(range(coeff_count)) - union)
    if overlap:
        raise SystemExit(f'grid/static coefficient ownership overlaps: {sorted(overlap)[:8]}')
    if len(grid_coeff_indices) != 37622:
        raise SystemExit(f'grid unique coeff-index count drift: {len(grid_coeff_indices)}')
    if len(static_coeff_indices) != 2992:
        raise SystemExit(f'static unique coeff-index count drift: {len(static_coeff_indices)}')
    if missing_coeff_indices != [1]:
        raise SystemExit(f'unexpected coefficient ownership gap: {missing_coeff_indices[:20]}')

    # Independent next-structure control: first serialized GfxBrushModel follows
    # light-grid arrays and has retail-plausible world bounds + 5597 surfaces.
    first_model = coeff_end
    writable = list(struct.unpack_from('<8f', d, first_model))
    bounds_and_counts = struct.unpack_from('<6fII', d, first_model + 32)
    if writable != [0.0] * 8:
        raise SystemExit('first GfxBrushModel writable block drift')
    if list(bounds_and_counts[:6]) != [-45748.0, -70148.0, -3840.0, 60820.0, 63488.0, 23284.0]:
        raise SystemExit('first GfxBrushModel bounds drift')
    if bounds_and_counts[6:] != (5597, 0):
        raise SystemExit('first GfxBrushModel surface range drift')

    out = {
        'format': 't6-nuketown-gfxworld-lightgrid-coeff-ownership-v1',
        'map': 'mp_nuketown_2020',
        'source': {
            'expandedBytes': len(d), 'expandedSha256': got_sha,
            'gfxWorldXAssetIndex': 624, 'gfxWorldFixedStart': GFXWORLD_START,
            'lightGridFixedStart': lg, 'lightGridFixedOffset': LIGHTGRID_FIXED_OFFSET,
            'lightGridFixedBytes': LIGHTGRID_SIZE,
            'drawIndexEndAndLightGridPayloadStart': DRAW_INDEX_END,
        },
        'fixed': actual,
        'serializedPayload': {
            'start': row_start, 'end': coeff_end, 'bytes': coeff_end-row_start,
            'sha256': sha(d[row_start:coeff_end]),
            'sections': {
                'rowDataStart': {'start': row_start, 'end': raw_start, 'bytes': len(row_blob), 'sha256': sha(row_blob)},
                'rawRowData': {'start': raw_start, 'end': entries_start, 'bytes': len(raw_blob), 'sha256': sha(raw_blob)},
                'entries': {'start': entries_start, 'end': coeff_start, 'bytes': len(entry_blob), 'sha256': sha(entry_blob)},
                'coeffs': {'start': coeff_start, 'end': coeff_end, 'bytes': len(coeff_blob), 'sha256': sha(coeff_blob), 'recordBytes': 54},
            },
        },
        'rowHeaders': {
            'count': len(concrete_rows), 'absentCount': row_count-len(concrete_rows),
            'uniqueOffsets': len({r['rawOffsetUnits4'] for r in concrete_rows}),
            'unitBytes': 4, 'headerBytes': 12,
            'colStartMin': min(r['colStart'] for r in concrete_rows),
            'colStartMax': max(r['colStart'] for r in concrete_rows),
            'colCountMin': min(r['colCount'] for r in concrete_rows),
            'colCountMax': max(r['colCount'] for r in concrete_rows),
            'zStartMin': min(r['zStart'] for r in concrete_rows),
            'zStartMax': max(r['zStart'] for r in concrete_rows),
            'zCountMin': min(r['zCount'] for r in concrete_rows),
            'zCountMax': max(r['zCount'] for r in concrete_rows),
            'firstEntryMin': min(r['firstEntry'] for r in concrete_rows),
            'firstEntryMax': max(r['firstEntry'] for r in concrete_rows),
            'lastRowEntrySpanToEnd': entry_count - concrete_rows[-1]['firstEntry'],
            'rows': concrete_rows,
        },
        'gridEntries': {
            'count': entry_count, 'uniqueCoeffIndices': len(grid_coeff_indices),
            'minCoeffIndex': min(grid_coeff_indices), 'maxCoeffIndex': max(grid_coeff_indices),
            'primaryLightIndexCounts': {str(k): v for k,v in sorted(grid_primary.items())},
            'primaryLightSentinel255Count': grid_primary[255],
            'visibilityCounts': {str(k): v for k,v in sorted(visibility.items())},
        },
        'staticDrawInstances': {
            'sourceManifest': a.placements.name,
            'count': len(instances), 'uniqueCoeffIndices': len(static_coeff_indices),
            'minCoeffIndex': min(static_coeff_indices), 'maxCoeffIndex': max(static_coeff_indices),
            'primaryLightIndexCounts': {str(k): v for k,v in sorted(static_primary.items())},
            'visibilityCounts': {str(k): v for k,v in sorted(static_visibility.items())},
            'allLightingHandlesZero': all(int(x['lightingHandle']) == 0 for x in instances),
        },
        'coeffOwnership': {
            'coeffCount': coeff_count,
            'gridUniqueCoeffIndices': len(grid_coeff_indices),
            'staticUniqueCoeffIndices': len(static_coeff_indices),
            'gridStaticOverlapCount': len(overlap),
            'unionUniqueCoeffIndices': len(union),
            'unownedCoeffIndices': missing_coeff_indices,
            'exactPartitionExceptIndex1': len(union)==coeff_count-1 and missing_coeff_indices==[1] and not overlap,
            'interpretation': (
                'Retail T6 keeps the legacy field name colorsIndex, but Nuketown has colorCount=0. '
                'Every GfxLightGridEntry.colorsIndex and every source-derived GfxStaticModelDrawInst.colorsIndex '
                'is in [0, coeffCount), the grid/static sets are disjoint, and together they own every '
                'GfxCompressedLightGridCoeffs record except index 1. This source-closes colorsIndex as a '
                'coefficient-table index for this T6 map; coefficient numeric decode remains a separate proof.'
            ),
        },
        'nextStructureControl': {
            'gfxBrushModelArrayStart': first_model, 'modelCount': EXPECTED_MODEL_COUNT,
            'firstModelBounds': list(bounds_and_counts[:6]),
            'firstModelSurfaceCount': bounds_and_counts[6],
            'firstModelStartSurfIndex': bounds_and_counts[7],
        },
        'proofBoundary': {
            'proven': (
                'Exact Nuketown GfxLightGrid fixed record, serialized row/raw/entry/coeff payload boundaries, '
                'entry primary-light ownership, and exact coefficient-index partition between the light grid '
                'and all 2,992 source-derived static draw instances.'
            ),
            'notYetProven': (
                'T6 numeric decompression of the 9x3 uint16 coefficient records into renderer SH values, and '
                'full semantic interpretation of the raw-row RLE bytecode/visibility byte.'
            ),
        },
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, indent=2, sort_keys=True) + '\n'
    a.out.write_text(text, encoding='utf-8')
    print(json.dumps({
        'payloadStart': row_start, 'payloadEnd': coeff_end,
        'entryCount': entry_count, 'coeffCount': coeff_count,
        'gridUniqueCoeffIndices': len(grid_coeff_indices),
        'staticUniqueCoeffIndices': len(static_coeff_indices),
        'unownedCoeffIndices': missing_coeff_indices,
        'outputBytes': len(text.encode()), 'outputSha256': hashlib.sha256(text.encode()).hexdigest(),
    }, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
