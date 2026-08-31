#!/usr/bin/env python3
"""T6 ClipMap normalized collision exporter v2.

Extends v1 with strict resolution of the GfxWorld-owned reusable cplane_s pool.
No packed pointer is resolved from arithmetic alone: the owner header, exact raw
plane span, and every ClipMap plane reference must all validate.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from pathlib import Path
from t6_clipmap_normalize_v1 import normalize as normalize_v1

PTR_FOLLOWING = 0xFFFFFFFF
CPLANE_SIZE = 20
GFXWORLD_FIXED_SIZE_PC32 = 1028
GFXWORLD_PLANE_COUNT_OFF = 0x08
GFXWORLD_NODE_COUNT_OFF = 0x0C
GFXWORLD_DPVS_PLANES_OFF = 0x174
GFXWORLD_DPVS_PLANES_PLANES_PTR_OFF = GFXWORLD_DPVS_PLANES_OFF + 4
GFXWORLD_DPVS_PLANES_NODES_PTR_OFF = GFXWORLD_DPVS_PLANES_OFF + 8


def u32(d: bytes, o: int) -> int:
    return struct.unpack_from('<I', d, o)[0]


def parse_plane(d: bytes, o: int) -> dict:
    x, y, z, dist = struct.unpack_from('<4f', d, o)
    typ, signbits, p0, p1 = d[o + 16:o + 20]
    if not all(math.isfinite(v) for v in (x, y, z, dist)):
        raise ValueError(f'non-finite cplane_s at raw source {o}')
    n2 = x * x + y * y + z * z
    if not (0.999 <= n2 <= 1.001):
        raise ValueError(f'non-unit cplane_s normal at raw source {o}: len^2={n2}')
    if typ > 5 or signbits > 7 or p0 != 0 or p1 != 0:
        raise ValueError(
            f'invalid cplane_s trailer at raw source {o}: '
            f'type={typ} signbits={signbits} pad={p0:02x}{p1:02x}'
        )
    return {
        'normal': [x, y, z],
        'dist': dist,
        'type': typ,
        'signbits': signbits,
    }


def resolve_planes(out: dict, data: bytes, *, gfxworld_start: int, plane_source_start: int) -> dict:
    dep_key = 'clipMap.info.planes'
    dep = out.get('dependencies', {}).get(dep_key)
    if not dep:
        raise ValueError('v1 output does not contain unresolved clipMap.info.planes dependency')
    ptr = dep['pointer']
    if ptr.get('kind') != 'packed' or ptr.get('block') != 5:
        raise ValueError(f'ClipMap planes pointer is not packed VIRTUAL: {ptr}')

    count = int(dep['count'])
    if gfxworld_start < 0 or gfxworld_start + GFXWORLD_FIXED_SIZE_PC32 > len(data):
        raise ValueError('GfxWorld fixed record is outside expanded stream')
    owner_count = u32(data, gfxworld_start + GFXWORLD_PLANE_COUNT_OFF)
    owner_node_count = u32(data, gfxworld_start + GFXWORLD_NODE_COUNT_OFF)
    owner_planes_ptr = u32(data, gfxworld_start + GFXWORLD_DPVS_PLANES_PLANES_PTR_OFF)
    owner_nodes_ptr = u32(data, gfxworld_start + GFXWORLD_DPVS_PLANES_NODES_PTR_OFF)
    if owner_count != count:
        raise ValueError(f'GfxWorld planeCount {owner_count} != ClipMap planeCount {count}')
    if owner_planes_ptr != PTR_FOLLOWING:
        raise ValueError(f'GfxWorld dpvsPlanes.planes is not FOLLOWING: 0x{owner_planes_ptr:08x}')
    if owner_nodes_ptr != PTR_FOLLOWING:
        raise ValueError(f'GfxWorld dpvsPlanes.nodes is not FOLLOWING: 0x{owner_nodes_ptr:08x}')

    source_end = plane_source_start + count * CPLANE_SIZE
    if plane_source_start < gfxworld_start + GFXWORLD_FIXED_SIZE_PC32 or source_end > out['source']['fixedStart']:
        raise ValueError('candidate GfxWorld plane source span is outside GfxWorld->ClipMap serialized interval')
    raw = data[plane_source_start:source_end]
    if len(raw) != count * CPLANE_SIZE:
        raise ValueError('candidate plane source span is truncated')

    base = int(ptr['offset'])
    logical_end = base + count * CPLANE_SIZE
    planes = []
    for i in range(count):
        source_off = plane_source_start + i * CPLANE_SIZE
        p = parse_plane(data, source_off)
        p.update({'index': i, 'logicalOffset': base + i * CPLANE_SIZE, 'sourceOffset': source_off})
        planes.append(p)

    ref_counts = {}
    unique_indices = set()
    for collection_name in ('brushSides', 'bspNodes'):
        rows = out[collection_name]
        bad = []
        for row in rows:
            q = row['planePointer']
            if q.get('kind') != 'packed' or q.get('block') != 5:
                bad.append({'index': row['index'], 'pointer': q, 'reason': 'not_packed_virtual'})
                continue
            off = int(q['offset'])
            delta = off - base
            if delta < 0 or off >= logical_end or delta % CPLANE_SIZE:
                bad.append({'index': row['index'], 'offset': off, 'reason': 'outside_or_misaligned'})
                continue
            pi = delta // CPLANE_SIZE
            row['planeIndex'] = pi
            unique_indices.add(pi)
        if bad:
            raise ValueError(f'{collection_name} has {len(bad)} invalid plane references; first={bad[0]}')
        ref_counts[collection_name] = {
            'count': len(rows),
            'allPackedVirtualInPool': True,
            'uniquePlaneIndices': len({r['planeIndex'] for r in rows}),
        }

    out['planes'] = planes
    resolved = {
        'pointer': ptr,
        'count': count,
        'logicalRange': {'start': base, 'end': logical_end, 'bytes': count * CPLANE_SIZE},
        'owner': {
            'assetType': 'GfxWorld',
            'fixedStart': gfxworld_start,
            'fixedSize': GFXWORLD_FIXED_SIZE_PC32,
            'planeCount': owner_count,
            'nodeCount': owner_node_count,
            'dpvsPlanesPlanesPointerRaw': owner_planes_ptr,
            'dpvsPlanesNodesPointerRaw': owner_nodes_ptr,
            'ownershipProof': 'GfxWorld dpvsPlanes.planes is FOLLOWING with same planeCount',
        },
        'serializedSource': {
            'start': plane_source_start,
            'end': source_end,
            'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'recordSize': CPLANE_SIZE,
            'allRecordsStructurallyValid': True,
        },
        'referenceProof': {
            **ref_counts,
            'uniquePlaneIndicesAcrossClipMapRefs': len(unique_indices),
            'allReferencesResolveAsBasePlusIndexTimes20': True,
        },
        'status': 'resolved_gfxworld_owned_reusable_virtual_pool',
    }
    out.setdefault('resolvedDependencies', {})[dep_key] = resolved
    del out['dependencies'][dep_key]
    out['normalizationStatus']['unresolvedCrossAssetDependencies'] = sorted(out['dependencies'])
    out['normalizationStatus']['resolvedCrossAssetDependencies'] = sorted(out['resolvedDependencies'])
    out['normalizationStatus']['planePoolResolved'] = True
    out['normalizationStatus']['decodedOwnedSections'] = list(out['normalizationStatus']['decodedOwnedSections']) + ['planes(reused:GfxWorld)']
    out['format'] = 't6-clipmap-normalized-v2'
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
    resolved = resolve_planes(out, data, gfxworld_start=args.gfxworld_start, plane_source_start=args.plane_source_start)
    out['expandedSha256'] = hashlib.sha256(data).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({
        'out': str(args.out),
        'bytes': args.out.stat().st_size,
        'sha256': hashlib.sha256(args.out.read_bytes()).hexdigest(),
        'serializedEnd': walk['assetSerializedEnd'],
        'planes': resolved,
        'remainingDependencies': out['dependencies'],
        'status': out['normalizationStatus'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
