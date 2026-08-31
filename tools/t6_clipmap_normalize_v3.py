#!/usr/bin/env python3
"""T6 ClipMap normalized collision exporter v3.

Extends v2 by strictly resolving ClipInfo::leafbrushes as a same-ClipMap
reusable VIRTUAL alias over the prefix of the serialized per-node LeafBrush
arrays. The resolver proves the alias from independent packed references to the
global brush-side and brush-vertex pools plus the exact serialized leaf-node
layout; it does not scan for a plausible uint16 blob.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from t6_clipmap_normalize_v1 import normalize as normalize_v1
from t6_clipmap_normalize_v2 import resolve_planes

PTR_FOLLOWING = 0xFFFFFFFF
LEAFBRUSH_SIZE = 2
CBRUSHSIDE_SIZE = 12
CLEAFBRUSHNODE_SIZE = 20
VEC3_SIZE = 12
VIRTUAL_BLOCK = 5


def align_up(v: int, a: int) -> int:
    return (v + a - 1) // a * a


def _section_map(walk: dict) -> dict[str, dict]:
    return {s['name']: s for s in walk['sections']}


def _packed_virtual_offset(q: dict, label: str) -> int:
    if q.get('kind') != 'packed' or q.get('block') != VIRTUAL_BLOCK:
        raise ValueError(f'{label} is not a packed VIRTUAL pointer: {q}')
    return int(q['offset'])


def resolve_leafbrushes(out: dict, walk: dict, data: bytes) -> dict:
    dep_key = 'clipMap.info.leafbrushes'
    dep = out.get('dependencies', {}).get(dep_key)
    if not dep:
        raise ValueError('normalized output does not contain unresolved clipMap.info.leafbrushes dependency')
    ptr = dep['pointer']
    leaf_base = _packed_virtual_offset(ptr, dep_key)
    global_count = int(dep['count'])
    global_bytes = global_count * LEAFBRUSH_SIZE

    ci = walk['header']['info']
    for field in ('brushsides', 'leafbrushNodes', 'brushVerts'):
        p = ci['pointers'][field]
        if p.get('kind') != 'following':
            raise ValueError(f'ClipInfo::{field} must be FOLLOWING for same-asset leafbrush proof: {p}')

    side_offsets = []
    side_ref_count = 0
    for b in out['brushes']:
        q = b['sidesPointer']
        n = int(b['numSides'])
        if q.get('kind') == 'null':
            if n:
                raise ValueError(f'brush {b["index"]} has numSides={n} but null sides pointer')
            continue
        off = _packed_virtual_offset(q, f'brushes[{b["index"]}].sidesPointer')
        side_offsets.append((off, n, b['index']))
        side_ref_count += 1
    if not side_offsets:
        raise ValueError('no packed cbrush_t::sides references available to anchor brush-side VIRTUAL pool')
    side_base = min(x[0] for x in side_offsets)
    side_count = int(out['counts']['numBrushSides'])
    side_end = side_base + side_count * CBRUSHSIDE_SIZE
    bad_sides = []
    for off, n, bi in side_offsets:
        if off < side_base or off >= side_end or (off - side_base) % CBRUSHSIDE_SIZE:
            bad_sides.append({'brushIndex': bi, 'offset': off, 'reason': 'outside_or_misaligned'})
        elif off + n * CBRUSHSIDE_SIZE > side_end:
            bad_sides.append({'brushIndex': bi, 'offset': off, 'numSides': n, 'reason': 'range_past_pool'})
    if bad_sides:
        raise ValueError(f'{len(bad_sides)} invalid cbrush_t::sides references; first={bad_sides[0]}')

    leaf_node_count = int(out['counts']['leafbrushNodesCount'])
    leaf_nodes_logical_base = side_end
    expected_leaf_base = leaf_nodes_logical_base + leaf_node_count * CLEAFBRUSHNODE_SIZE
    if leaf_base != expected_leaf_base:
        raise ValueError(
            f'leafbrush packed base {leaf_base} != brushSidesBase + brushSidesBytes + '
            f'leafBrushNodesBytes ({expected_leaf_base})'
        )

    sections = _section_map(walk)
    leaf_fixed = sections.get('clipMap.info.leafbrushNodes.fixed')
    if not leaf_fixed:
        raise ValueError('missing serialized leafBrushNodes fixed section')
    if leaf_fixed['bytes'] != leaf_node_count * CLEAFBRUSHNODE_SIZE:
        raise ValueError('serialized leafBrushNodes fixed byte count mismatch')

    positive_nodes = [n for n in out['leafBrushNodes'] if int(n['leafBrushCount']) > 0]
    leaf_sections = [
        s for s in walk['sections']
        if s['name'].startswith('clipMap.info.leafbrushNodes[') and s['name'].endswith('].brushes')
    ]
    if len(leaf_sections) != len(positive_nodes):
        raise ValueError(f'positive leaf nodes {len(positive_nodes)} != serialized leaf arrays {len(leaf_sections)}')
    if not leaf_sections:
        raise ValueError('no serialized leaf-brush arrays found')
    if leaf_sections[0]['start'] != leaf_fixed['end']:
        raise ValueError('first leaf-brush array does not immediately follow leafBrushNodes fixed records')
    for a, b in zip(leaf_sections, leaf_sections[1:]):
        if a['end'] != b['start']:
            raise ValueError(f'leaf-brush arrays are not source-contiguous: {a["name"]} -> {b["name"]}')

    cumulative = 0
    for node, sec in zip(positive_nodes, leaf_sections):
        cnt = int(node['leafBrushCount'])
        expected_bytes = cnt * LEAFBRUSH_SIZE
        if sec['bytes'] != expected_bytes:
            raise ValueError(f'{sec["name"]} bytes {sec["bytes"]} != leafBrushCount*2 {expected_bytes}')
        vals = node.get('data', {}).get('brushes')
        if vals is None or len(vals) != cnt:
            raise ValueError(f'{sec["name"]} normalized values missing/truncated')
        node['serializedLeafBrushRange'] = {'start': cumulative, 'count': cnt, 'end': cumulative + cnt}
        if cumulative + cnt <= global_count:
            node['globalLeafBrushRange'] = {'start': cumulative, 'count': cnt, 'end': cumulative + cnt}
        else:
            node['globalLeafBrushRange'] = None
            node['localOnlyLeafBrushRange'] = {
                'start': max(cumulative, global_count),
                'count': cumulative + cnt - max(cumulative, global_count),
                'end': cumulative + cnt,
            }
        cumulative += cnt

    inline_total_count = cumulative
    inline_total_bytes = inline_total_count * LEAFBRUSH_SIZE
    inline_logical_end = leaf_base + inline_total_bytes
    raw_inline_start = leaf_sections[0]['start']
    raw_inline_end = leaf_sections[-1]['end']
    if raw_inline_end - raw_inline_start != inline_total_bytes:
        raise ValueError('source-contiguous leaf-brush byte span != summed leafBrushCount*2')
    if global_count > inline_total_count:
        raise ValueError('global numLeafBrushes exceeds serialized inline leaf-brush sequence')

    raw_global_end = raw_inline_start + global_bytes
    if raw_global_end > raw_inline_end:
        raise ValueError('global leafbrush prefix extends past serialized inline sequence')
    if not any(s['end'] == raw_global_end for s in leaf_sections):
        raise ValueError('global leafbrush prefix does not end on a serialized leaf-node array boundary')

    vertex_offsets = []
    for b in out['brushes']:
        q = b['vertsPointer']
        n = int(b['numVerts'])
        off = _packed_virtual_offset(q, f'brushes[{b["index"]}].vertsPointer')
        vertex_offsets.append((off, n, b['index']))
    if not vertex_offsets:
        raise ValueError('no packed cbrush_t::verts references available to anchor brush-vertex VIRTUAL pool')
    vertex_base = min(x[0] for x in vertex_offsets)
    vertex_count = int(out['counts']['numBrushVerts'])
    vertex_end = vertex_base + vertex_count * VEC3_SIZE
    bad_verts = []
    for off, n, bi in vertex_offsets:
        if off < vertex_base or off >= vertex_end or (off - vertex_base) % VEC3_SIZE:
            bad_verts.append({'brushIndex': bi, 'offset': off, 'reason': 'outside_or_misaligned'})
        elif off + n * VEC3_SIZE > vertex_end:
            bad_verts.append({'brushIndex': bi, 'offset': off, 'numVerts': n, 'reason': 'range_past_pool'})
    if bad_verts:
        raise ValueError(f'{len(bad_verts)} invalid cbrush_t::verts references; first={bad_verts[0]}')
    expected_vertex_base = align_up(inline_logical_end, 4)
    if vertex_base != expected_vertex_base:
        raise ValueError(
            f'brushVerts packed base {vertex_base} != align4(leafbrushBase + inlineLeafBytes) '
            f'({expected_vertex_base})'
        )

    raw_global = data[raw_inline_start:raw_global_end]
    if len(raw_global) != global_bytes:
        raise ValueError('global leafbrush serialized source prefix is truncated')
    global_values = list(struct.unpack_from(f'<{global_count}H', data, raw_inline_start)) if global_count else []
    # struct.unpack_from above returns directly from data; assert the exact prefix agrees with the sliced bytes.
    if global_count and struct.pack(f'<{global_count}H', *global_values) != raw_global:
        raise ValueError('global leafbrush unpack/repack mismatch')
    num_brushes = int(out['counts']['numBrushes'])
    bad_values = [(i, v) for i, v in enumerate(global_values) if v >= num_brushes]
    if bad_values:
        raise ValueError(f'global leafbrush pool contains out-of-range brush index; first={bad_values[0]} numBrushes={num_brushes}')

    # Cross-check every normalized node slice that falls inside the global prefix.
    for node in positive_nodes:
        gr = node.get('globalLeafBrushRange')
        if not gr:
            continue
        a, b = gr['start'], gr['end']
        if node['data']['brushes'] != global_values[a:b]:
            raise ValueError(f'leaf node {node["index"]} values do not match global leafbrush prefix slice')

    out['leafBrushes'] = global_values
    unique_values = sorted(set(global_values))
    resolved = {
        'pointer': ptr,
        'count': global_count,
        'logicalRange': {'start': leaf_base, 'end': leaf_base + global_bytes, 'bytes': global_bytes},
        'owner': {
            'assetType': 'clipMap_t',
            'scope': 'same asset reusable allocation',
            'construction': 'prefix of serialized cLeafBrushNode_s::data.leaf.brushes arrays',
            'brushSidesLogicalBase': side_base,
            'brushSidesLogicalEnd': side_end,
            'leafBrushNodesLogicalBase': leaf_nodes_logical_base,
            'leafBrushNodesLogicalEnd': expected_leaf_base,
            'derivedLeafBrushLogicalBase': expected_leaf_base,
            'ownershipProof': 'packed leafbrush base equals brush-side pool end plus exact leafBrushNodes fixed bytes',
        },
        'serializedSource': {
            'start': raw_inline_start,
            'end': raw_global_end,
            'bytes': global_bytes,
            'sha256': hashlib.sha256(raw_global).hexdigest(),
            'recordSize': LEAFBRUSH_SIZE,
            'sourceSequenceTotalStart': raw_inline_start,
            'sourceSequenceTotalEnd': raw_inline_end,
            'sourceSequenceTotalBytes': inline_total_bytes,
            'sourceSequenceArrayCount': len(leaf_sections),
            'prefixEndsOnNodeArrayBoundary': True,
        },
        'allocationProof': {
            'brushSideReferenceCount': side_ref_count,
            'allBrushSideReferencesPackedVirtualInPool': True,
            'inlineLeafBrushArrayCount': len(leaf_sections),
            'inlineLeafBrushRefCount': inline_total_count,
            'inlineLeafBrushBytes': inline_total_bytes,
            'trailingLocalOnlyLeafBrushRefs': inline_total_count - global_count,
            'brushVertsLogicalBase': vertex_base,
            'expectedBrushVertsLogicalBaseAfterLeafSequenceAlign4': expected_vertex_base,
            'brushVertReferenceCount': len(vertex_offsets),
            'allBrushVertReferencesPackedVirtualInPool': True,
        },
        'semanticProof': {
            'allGlobalLeafBrushValuesInBrushRange': True,
            'minBrushIndex': min(global_values) if global_values else None,
            'maxBrushIndex': max(global_values) if global_values else None,
            'uniqueBrushIndices': len(unique_values),
            'numBrushes': num_brushes,
            'coversEveryBrushIndexExactlyAsASet': unique_values == list(range(num_brushes)),
            'allNodeSlicesInsidePrefixMatchGlobalPool': True,
        },
        'status': 'resolved_same_clipmap_reusable_leafnode_prefix_pool',
    }
    out.setdefault('resolvedDependencies', {})[dep_key] = resolved
    del out['dependencies'][dep_key]
    out['normalizationStatus']['unresolvedCrossAssetDependencies'] = sorted(out['dependencies'])
    out['normalizationStatus']['resolvedDependencies'] = sorted(out['resolvedDependencies'])
    out['normalizationStatus']['resolvedCrossAssetDependencies'] = sorted(
        k for k, v in out['resolvedDependencies'].items() if v.get('owner', {}).get('assetType') != 'clipMap_t'
    )
    out['normalizationStatus']['resolvedSameAssetReusableDependencies'] = sorted(
        k for k, v in out['resolvedDependencies'].items() if v.get('owner', {}).get('assetType') == 'clipMap_t'
    )
    out['normalizationStatus']['leafBrushPoolResolved'] = True
    out['normalizationStatus']['decodedOwnedSections'] = list(out['normalizationStatus']['decodedOwnedSections']) + [
        'leafBrushes(reused:same ClipMap leaf-node prefix)'
    ]
    out['format'] = 't6-clipmap-normalized-v3'
    return resolved


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
    leafbrushes = resolve_leafbrushes(out, walk, data)
    out['expandedSha256'] = hashlib.sha256(data).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({
        'out': str(args.out),
        'bytes': args.out.stat().st_size,
        'sha256': hashlib.sha256(args.out.read_bytes()).hexdigest(),
        'serializedEnd': walk['assetSerializedEnd'],
        'planes': planes,
        'leafbrushes': leafbrushes,
        'remainingDependencies': out['dependencies'],
        'status': out['normalizationStatus'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
