#!/usr/bin/env python3
"""T6 ClipMap normalized collision exporter v6.

Extends v5 by resolving static-model top-level XMODEL asset indices to exact
serialized XModel fixed records and names.

The resolver is source-derived:
- it walks the small top-level KeyValuePairs / SkinnedVertsDef / StringTable
  prefix used by retail T6 map zones;
- it self-calibrates the StringTable's VIRTUAL inline-string allocation base
  from packed aliases whose StringTableCell hashes match unique inline strings;
- it scans for native-valid PC32 248-byte XModel fixed records in source order;
- packed XModel name pointers are accepted only when they resolve to that proven
  VIRTUAL string allocation;
- it consumes exactly as many XModel records as the XAsset table requires up to
  the highest static-model target XAsset index.

No model names, map byte offsets, or XAsset indices are hard-coded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter, defaultdict
from pathlib import Path

from t6_clipmap_normalize_v1 import normalize as normalize_v1
from t6_clipmap_normalize_v2 import resolve_planes
from t6_clipmap_normalize_v3 import resolve_leafbrushes
from t6_clipmap_normalize_v4 import decode_static_models, decode_constraints
from t6_clipmap_normalize_v5 import (
    ASSET_TYPE_XMODEL,
    parse_top_level_xasset_table,
    resolve_static_xmodel_assets,
)
from t6_clipmap_serialized_walker import ptr_kind

PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
XMODEL_FIXED_SIZE = 248
ASSET_TYPE_KEYVALUEPAIRS = 49
ASSET_TYPE_SKINNEDVERTS = 54
ASSET_TYPE_STRINGTABLE = 42


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _i32(data: bytes, off: int) -> int:
    return struct.unpack_from('<i', data, off)[0]


def _cstring(data: bytes, pos: int, max_len: int = 1 << 20) -> tuple[str, int]:
    end = data.find(b'\0', pos, min(len(data), pos + max_len))
    if end < 0:
        raise ValueError(f'unterminated string at raw offset {pos}')
    raw = data[pos:end]
    try:
        text = raw.decode('latin1')
    except UnicodeDecodeError as exc:
        raise ValueError(f'invalid string at raw offset {pos}') from exc
    return text, end + 1


def _packed(raw: int) -> tuple[int, int] | None:
    if raw in (0, PTR_FOLLOWING, PTR_INSERT):
        return None
    enc = (raw - 1) & 0xFFFFFFFF
    return enc >> 29, enc & 0x1FFFFFFF


def _valid_ptr(raw: int) -> bool:
    if raw in (0, PTR_FOLLOWING, PTR_INSERT):
        return True
    block, _ = _packed(raw)
    return 0 <= block < 8


def _printable_asset_name(text: str) -> bool:
    if not text or len(text) > 300:
        return False
    return all(32 <= ord(ch) < 127 for ch in text)


def walk_map_prefix_stringtable(data: bytes, table: dict) -> dict:
    """Walk the exact compact map-zone prefix through top-level asset 2.

    Retail MP fixtures used here begin with KeyValuePairs, SkinnedVertsDef,
    StringTable. This function checks those types rather than assuming them.
    """
    entries = table['entries']
    if len(entries) < 3:
        raise ValueError('XAsset table is too short for map prefix')
    expected = [ASSET_TYPE_KEYVALUEPAIRS, ASSET_TYPE_SKINNEDVERTS, ASSET_TYPE_STRINGTABLE]
    got = [entries[i]['type'] for i in range(3)]
    if got != expected:
        raise ValueError(f'unsupported map prefix asset types: got {got}, expected {expected}')

    pos = table['assetArrayRawEnd']

    # Asset 0: KeyValuePairs, PC32 12-byte fixed record.
    kv_start = pos
    name_ptr, num_vars, pairs_ptr = struct.unpack_from('<III', data, pos)
    pos += 12
    if name_ptr != PTR_FOLLOWING:
        raise ValueError(f'asset0 KeyValuePairs name is not FOLLOWING: 0x{name_ptr:08X}')
    kv_name, pos = _cstring(data, pos)
    if num_vars and pairs_ptr != PTR_FOLLOWING:
        raise ValueError(f'asset0 KeyValuePairs array is not FOLLOWING: 0x{pairs_ptr:08X}')
    pair_start = pos
    pair_bytes = num_vars * 12
    if pos + pair_bytes > len(data):
        raise ValueError('asset0 KeyValuePairs array truncated')
    pairs = [struct.unpack_from('<III', data, pair_start + i * 12) for i in range(num_vars)]
    pos += pair_bytes
    for _, _, value_ptr in pairs:
        if value_ptr == PTR_FOLLOWING:
            _, pos = _cstring(data, pos)
        elif value_ptr == 0 or _packed(value_ptr) is not None:
            pass
        else:
            raise ValueError(f'asset0 invalid value pointer 0x{value_ptr:08X}')
    kv_end = pos

    # Asset 1: SkinnedVertsDef, PC32 8-byte fixed record.
    skin_start = pos
    skin_name_ptr, max_skinned = struct.unpack_from('<II', data, pos)
    pos += 8
    if skin_name_ptr != PTR_FOLLOWING:
        raise ValueError(f'asset1 SkinnedVertsDef name is not FOLLOWING: 0x{skin_name_ptr:08X}')
    skin_name, pos = _cstring(data, pos)
    skin_end = pos

    # Asset 2: StringTable, PC32 20-byte fixed record.
    st_start = pos
    st_name_ptr, columns, rows, values_ptr, cell_index_ptr = struct.unpack_from('<IiiII', data, pos)
    pos += 20
    if st_name_ptr != PTR_FOLLOWING:
        raise ValueError(f'asset2 StringTable name is not FOLLOWING: 0x{st_name_ptr:08X}')
    if columns <= 0 or rows <= 0:
        raise ValueError(f'asset2 invalid StringTable dimensions {columns}x{rows}')
    st_name, pos = _cstring(data, pos)
    cell_count = columns * rows
    if values_ptr != PTR_FOLLOWING or cell_index_ptr != PTR_FOLLOWING:
        raise ValueError('asset2 StringTable values/cellIndex must be FOLLOWING in this retail prefix')
    values_start = pos
    values_bytes = cell_count * 8
    if pos + values_bytes > len(data):
        raise ValueError('asset2 StringTable values truncated')
    cells = [struct.unpack_from('<Ii', data, values_start + i * 8) for i in range(cell_count)]
    pos += values_bytes

    inline = []
    rel = 0
    hash_inline: dict[int, list[tuple[int, str, int]]] = defaultdict(list)
    for i, (string_ptr, string_hash) in enumerate(cells):
        if string_ptr == PTR_FOLLOWING:
            raw_start = pos
            text, pos = _cstring(data, pos)
            inline.append({'cellIndex': i, 'hash': string_hash, 'rawStart': raw_start, 'text': text, 'relativeOffset': rel})
            hash_inline[string_hash].append((i, text, rel))
            rel += len(text.encode('latin1')) + 1
        elif string_ptr == 0 or _packed(string_ptr) is not None:
            pass
        else:
            raise ValueError(f'asset2 invalid StringTable cell pointer 0x{string_ptr:08X}')

    cell_index_start = pos
    cell_index_bytes = cell_count * 2
    if pos + cell_index_bytes > len(data):
        raise ValueError('asset2 StringTable cellIndex truncated')
    pos += cell_index_bytes
    st_end = pos

    # Solve the VIRTUAL base of the StringTable inline strings from internal
    # aliases. Only hashes with exactly one inline source are used.
    base_votes = Counter()
    vote_examples = []
    for i, (string_ptr, string_hash) in enumerate(cells):
        dec = _packed(string_ptr)
        if dec is None or dec[0] != 5:
            continue
        opts = hash_inline.get(string_hash, [])
        if len(opts) != 1:
            continue
        _, text, inline_rel = opts[0]
        base = dec[1] - inline_rel
        base_votes[base] += 1
        if len(vote_examples) < 8:
            vote_examples.append({'cellIndex': i, 'packedOffset': dec[1], 'text': text, 'relativeOffset': inline_rel, 'base': base})
    if not base_votes:
        raise ValueError('asset2 StringTable produced no VIRTUAL alias base votes')
    base, votes = base_votes.most_common(1)[0]
    disagreement = sum(base_votes.values()) - votes
    if disagreement:
        raise ValueError(f'asset2 StringTable VIRTUAL base is not exact: {dict(base_votes)}')
    if votes < 32:
        raise ValueError(f'asset2 StringTable VIRTUAL base has too little evidence: {votes} votes')

    logical_to_text = {base + row['relativeOffset']: row['text'] for row in inline}
    return {
        'sourceStart': kv_start,
        'sourceEnd': st_end,
        'assets': {
            'keyValuePairs': {'sourceStart': kv_start, 'sourceEnd': kv_end, 'name': kv_name, 'numVariables': num_vars},
            'skinnedVertsDef': {'sourceStart': skin_start, 'sourceEnd': skin_end, 'name': skin_name, 'maxSkinnedVerts': max_skinned},
            'stringTable': {
                'sourceStart': st_start,
                'sourceEnd': st_end,
                'name': st_name,
                'columnCount': columns,
                'rowCount': rows,
                'cellCount': cell_count,
                'inlineStringCount': len(inline),
                'virtualStringBase': base,
                'virtualStringBaseVotes': votes,
                'virtualStringBaseDisagreementVotes': disagreement,
                'inlineStringLogicalEnd': base + rel,
                'voteExamples': vote_examples,
            },
        },
        'logicalToText': logical_to_text,
    }


def parse_xmodel_fixed(data: bytes, pos: int, logical_strings: dict[int, str]) -> dict | None:
    if pos < 0 or pos + XMODEL_FIXED_SIZE > len(data):
        return None
    name_ptr = _u32(data, pos)
    if name_ptr == 0 or not _valid_ptr(name_ptr):
        return None
    num_bones, num_root_bones, num_surfs, lod_ramp = struct.unpack_from('<BBBB', data, pos + 4)
    if num_bones < 1 or num_root_bones < 1 or num_root_bones > num_bones or num_surfs < 1 or lod_ramp not in (0, 1):
        return None

    def ptr(off: int) -> int:
        return _u32(data, pos + off)

    ptr_offsets = (8, 12, 16, 20, 24, 28, 32, 36, 152, 164, 200, 216, 224, 228)
    if any(not _valid_ptr(ptr(off)) for off in ptr_offsets):
        return None
    if any(ptr(off) == 0 for off in (8, 24, 28, 32, 36, 164)):
        return None
    if num_bones - num_root_bones > 0 and any(ptr(off) == 0 for off in (12, 16, 20)):
        return None

    num_coll_surfs = _i32(data, pos + 156)
    if not (0 <= num_coll_surfs <= 100):
        return None
    if num_coll_surfs and ptr(152) == 0:
        return None

    radius = struct.unpack_from('<f', data, pos + 168)[0]
    mins = struct.unpack_from('<3f', data, pos + 172)
    maxs = struct.unpack_from('<3f', data, pos + 184)
    num_lods, coll_lod = struct.unpack_from('<Hh', data, pos + 196)
    bad = data[pos + 212]
    num_collmaps = data[pos + 220]
    lighting_origin_offset = struct.unpack_from('<3f', data, pos + 232)
    lighting_origin_range = struct.unpack_from('<f', data, pos + 244)[0]
    floats = (radius, *mins, *maxs, *lighting_origin_offset, lighting_origin_range)
    if not all(math.isfinite(x) for x in floats):
        return None
    if radius <= 0 or lighting_origin_range < 0 or any(mins[i] > maxs[i] for i in range(3)):
        return None
    if not (1 <= num_lods <= 4) or not (-1 <= coll_lod <= 3) or bad not in (0, 1):
        return None
    if num_collmaps > 32 or (num_collmaps and ptr(224) == 0):
        return None

    lods = []
    expected_surface_index = 0
    prev_dist = -1.0
    for i in range(4):
        b = pos + 40 + i * 28
        dist = struct.unpack_from('<f', data, b)[0]
        lod_surfs, surf_index = struct.unpack_from('<HH', data, b + 4)
        part_bits = list(struct.unpack_from('<5I', data, b + 8))
        if not math.isfinite(dist) or dist < 0:
            return None
        if i < num_lods:
            if lod_surfs < 1 or surf_index != expected_surface_index or dist <= 0 or dist < prev_dist:
                return None
            expected_surface_index += lod_surfs
            prev_dist = dist
        else:
            if lod_surfs != 0 or surf_index != 0:
                return None
        lods.append({'distance': dist, 'surfaceCount': lod_surfs, 'surfaceIndex': surf_index, 'partBits': part_bits})
    if expected_surface_index != num_surfs:
        return None

    name = None
    name_source = None
    name_raw_start = None
    if name_ptr == PTR_FOLLOWING:
        try:
            text, _ = _cstring(data, pos + XMODEL_FIXED_SIZE, 300)
        except ValueError:
            return None
        if not _printable_asset_name(text):
            return None
        name = text
        name_source = 'following'
        name_raw_start = pos + XMODEL_FIXED_SIZE
    else:
        dec = _packed(name_ptr)
        if dec is None or dec[0] != 5:
            return None
        name = logical_strings.get(dec[1])
        if name is None or not _printable_asset_name(name):
            return None
        name_source = 'packed_virtual_stringtable_alias'

    return {
        'fixedSourceStart': pos,
        'fixedSourceEnd': pos + XMODEL_FIXED_SIZE,
        'namePointerRaw': name_ptr,
        'namePointer': ptr_kind(name_ptr),
        'name': name,
        'nameSource': name_source,
        'nameRawStart': name_raw_start,
        'numBones': num_bones,
        'numRootBones': num_root_bones,
        'numSurfs': num_surfs,
        'lodRampType': lod_ramp,
        'numLods': num_lods,
        'collLod': coll_lod,
        'numCollSurfs': num_coll_surfs,
        'contents': _i32(data, pos + 160),
        'radius': radius,
        'mins': list(mins),
        'maxs': list(maxs),
        'himipInvSqRadiiPointer': ptr_kind(ptr(200)),
        'memUsage': _i32(data, pos + 204),
        'flags': _u32(data, pos + 208),
        'bad': bool(bad),
        'physPresetPointer': ptr_kind(ptr(216)),
        'numCollmaps': num_collmaps,
        'collmapsPointer': ptr_kind(ptr(224)),
        'physConstraintsPointer': ptr_kind(ptr(228)),
        'lightingOriginOffset': list(lighting_origin_offset),
        'lightingOriginRange': lighting_origin_range,
        'lods': lods,
    }


def scan_required_xmodels(data: bytes, start: int, required_count: int, logical_strings: dict[int, str]) -> list[dict]:
    if required_count <= 0:
        return []
    found = []
    # Full byte stepping is intentional: T6 serialized source objects need not
    # begin at native destination alignment boundaries.
    limit = len(data) - XMODEL_FIXED_SIZE
    pos = start
    while pos <= limit and len(found) < required_count:
        # Cheap native-header prefilters before the full validator.
        if data[pos + 7] <= 1:
            nb = data[pos + 4]
            nr = data[pos + 5]
            ns = data[pos + 6]
            if nb >= 1 and nr >= 1 and nr <= nb and ns >= 1:
                raw = _u32(data, pos)
                if raw and _valid_ptr(raw):
                    rec = parse_xmodel_fixed(data, pos, logical_strings)
                    if rec is not None:
                        found.append(rec)
                        # The fixed object is at least 248 bytes. Skipping its
                        # interior cannot skip another top-level fixed XModel.
                        pos += XMODEL_FIXED_SIZE
                        continue
        pos += 1
    if len(found) != required_count:
        raise ValueError(f'found {len(found)} strict XModel headers, need {required_count}')
    return found


def resolve_static_xmodel_names(out: dict, data: bytes) -> dict:
    xasset = out['staticModelXModelAssetResolution']
    targets = sorted({int(row['xModelAssetIndex']) for row in out['staticModels']})
    if not targets:
        result = {'status': 'no_static_models', 'placementCount': 0, 'uniqueTargetCount': 0}
        out['staticModelXModelNameResolution'] = result
        return result
    max_target = max(targets)

    table = parse_top_level_xasset_table(data)
    entries = table['entries']
    if max_target >= len(entries):
        raise ValueError(f'max target XAsset index {max_target} outside table')
    xmodel_indices = [i for i, ent in enumerate(entries) if ent['type'] == ASSET_TYPE_XMODEL]
    required_indices = [i for i in xmodel_indices if i <= max_target]
    if not required_indices:
        raise ValueError('no XMODEL assets through max static-model target')

    prefix = walk_map_prefix_stringtable(data, table)
    records = scan_required_xmodels(data, prefix['sourceEnd'], len(required_indices), prefix['logicalToText'])
    if len(records) != len(required_indices):
        raise AssertionError('XModel record/index cardinality mismatch')
    by_asset = {}
    for idx, rec in zip(required_indices, records):
        rec = dict(rec)
        rec['assetIndex'] = idx
        rec['xAssetEntryRawStart'] = entries[idx]['rawStart']
        rec['xAssetHeaderPointerRaw'] = entries[idx]['headerPointerRaw']
        if entries[idx]['headerPointerRaw'] != PTR_FOLLOWING:
            raise ValueError(f'top-level XMODEL asset {idx} header is not FOLLOWING: 0x{entries[idx]["headerPointerRaw"]:08X}')
        by_asset[idx] = rec

    packed_name_count = 0
    source_counts = Counter()
    for row in out['staticModels']:
        idx = int(row['xModelAssetIndex'])
        rec = by_asset.get(idx)
        if rec is None:
            raise ValueError(f'no recovered XModel fixed record for static target asset {idx}')
        row['xModelAssetName'] = rec['name']
        row['xModelFixedSourceStart'] = rec['fixedSourceStart']
        row['xModelFixedSourceEnd'] = rec['fixedSourceEnd']
        row['xModelNamePointer'] = rec['namePointer']
        row['xModelNameSource'] = rec['nameSource']
        row['xModelNumBones'] = rec['numBones']
        row['xModelNumSurfs'] = rec['numSurfs']
        row['xModelNumLods'] = rec['numLods']
        row['xModelNumCollSurfs'] = rec['numCollSurfs']
        row['xModelNumCollmaps'] = rec['numCollmaps']
        source_counts[rec['nameSource']] += 1
        if rec['nameSource'] != 'following':
            packed_name_count += 1

    unique_targets = []
    for idx in targets:
        rec = by_asset[idx]
        unique_targets.append({
            'assetIndex': idx,
            'name': rec['name'],
            'fixedSourceStart': rec['fixedSourceStart'],
            'namePointerRaw': rec['namePointerRaw'],
            'namePointer': rec['namePointer'],
            'nameSource': rec['nameSource'],
            'numBones': rec['numBones'],
            'numSurfs': rec['numSurfs'],
            'numLods': rec['numLods'],
            'collLod': rec['collLod'],
            'numCollSurfs': rec['numCollSurfs'],
            'contents': rec['contents'],
            'bounds': {'mins': rec['mins'], 'maxs': rec['maxs'], 'radius': rec['radius']},
            'numCollmaps': rec['numCollmaps'],
            'physPresetPointer': rec['physPresetPointer'],
            'collmapsPointer': rec['collmapsPointer'],
            'physConstraintsPointer': rec['physConstraintsPointer'],
            'lods': rec['lods'],
        })

    result = {
        'status': 'resolved_from_serialized_xmodel_fixed_records',
        'placementCount': len(out['staticModels']),
        'uniqueTargetCount': len(targets),
        'maxTargetAssetIndex': max_target,
        'requiredTopLevelXModelCountThroughMaxTarget': len(required_indices),
        'firstRecoveredXModelAssetIndex': required_indices[0],
        'firstRecoveredXModelFixedSourceStart': records[0]['fixedSourceStart'],
        'lastRecoveredXModelAssetIndex': required_indices[-1],
        'lastRecoveredXModelFixedSourceStart': records[-1]['fixedSourceStart'],
        'nameSourceCountsAcrossPlacements': dict(sorted(source_counts.items())),
        'packedNamePlacementCount': packed_name_count,
        'prefixStringTableProof': prefix['assets']['stringTable'],
        'uniqueTargets': unique_targets,
    }
    out['staticModelXModelNameResolution'] = result
    out['normalizationStatus']['staticModelXModelAssetNamesResolved'] = True
    out['normalizationStatus']['staticModelXModelFixedHeadersResolved'] = True
    out['normalizationStatus']['unresolvedSemanticLinks'] = []
    out['format'] = 't6-clipmap-normalized-v6'
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--asset-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--gfxworld-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--plane-source-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    out, walk = normalize_v1(data, args.asset_start)
    planes = resolve_planes(out, data, gfxworld_start=args.gfxworld_start, plane_source_start=args.plane_source_start)
    leaf = resolve_leafbrushes(out, walk, data)
    sm = decode_static_models(out, walk, data)
    con = decode_constraints(out, walk, data)
    xm = resolve_static_xmodel_assets(out, data)
    names = resolve_static_xmodel_names(out, data)
    out['expandedSha256'] = hashlib.sha256(data).hexdigest()
    out['normalizationStatus']['unexpandedOwnedSections'] = sorted(out['unexpandedSections'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(json.dumps({
        'out': str(args.out),
        'bytes': args.out.stat().st_size,
        'sha256': digest,
        'planesResolved': planes['count'],
        'leafBrushesResolved': leaf['count'],
        'staticModels': sm,
        'constraints': con,
        'xModelAssetIndices': {'placements': xm['placementCount'], 'uniqueAssets': xm['uniqueXModelAssetCount']},
        'xModelNames': {
            'placements': names['placementCount'],
            'uniqueTargets': names['uniqueTargetCount'],
            'maxTargetAssetIndex': names['maxTargetAssetIndex'],
            'requiredXModels': names['requiredTopLevelXModelCountThroughMaxTarget'],
            'stringAliasVotes': names['prefixStringTableProof']['virtualStringBaseVotes'],
            'packedNamePlacements': names['packedNamePlacementCount'],
        },
        'unexpanded': out['unexpandedSections'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
