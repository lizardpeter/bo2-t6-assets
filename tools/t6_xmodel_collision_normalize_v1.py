#!/usr/bin/env python3
"""Normalize native T6 XModel collision without discarding engine semantics.

Consumes a single XModel through t6_xmodel_serialized_walker and expands the
collision-bearing owned records into stable JSON:
- XSurface packed vertices, triangle indices, rigid lists and collision trees
- XModelCollSurf bounds/contents/surface flags and exact plane/svec/tvec tris
- XBoneInfo bounds/offset/radius/collmap selectors
- inline PhysPreset physical parameters
- Collmap -> PhysGeomList -> PhysGeomInfo -> BrushWrapper collision
- optional links back to normalized ClipMap static placements by XAsset index

Packed/reused pointers remain explicit pointer metadata. This is a normalized
lossless representation, not a triangles-only conversion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from t6_clipmap_serialized_walker import ptr_kind
from t6_xmodel_serialized_walker import XModelWalker


def f32s(data: bytes, off: int, count: int) -> list[float]:
    vals = list(struct.unpack_from('<' + 'f' * count, data, off))
    if not all(math.isfinite(v) for v in vals):
        raise ValueError(f'non-finite float sequence at {off}')
    return vals


def section_map(walk: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for sec in walk['sections']:
        out.setdefault(sec['name'], []).append(sec)
    return out


def one_section(secs: dict, name: str, required: bool = True) -> dict | None:
    rows = secs.get(name, [])
    if not rows:
        if required:
            raise ValueError(f'missing walker section {name!r}')
        return None
    if len(rows) != 1:
        raise ValueError(f'ambiguous walker section {name!r}: {len(rows)}')
    return rows[0]


def decode_cplane(data: bytes, off: int) -> dict:
    return {
        'normal': f32s(data, off, 3),
        'dist': f32s(data, off + 12, 1)[0],
        'type': data[off + 16],
        'signbits': data[off + 17],
        'reserved': list(data[off + 18:off + 20]),
    }


def decode_packed_vertices(data: bytes, sec: dict) -> list[dict]:
    if sec['bytes'] % 32:
        raise ValueError(f"{sec['name']}: packed vertex bytes not divisible by 32")
    rows = []
    for i, off in enumerate(range(sec['start'], sec['end'], 32)):
        xyz = f32s(data, off, 3)
        binormal = f32s(data, off + 12, 1)[0]
        color, texcoord, normal, tangent = struct.unpack_from('<4I', data, off + 16)
        rows.append({
            'index': i,
            'xyz': xyz,
            'binormalSign': binormal,
            'colorPacked': color,
            'texCoordPacked': texcoord,
            'normalPacked': normal,
            'tangentPacked': tangent,
        })
    return rows


def decode_surface_triangles(data: bytes, sec: dict) -> list[list[int]]:
    if sec['bytes'] % 6:
        raise ValueError(f"{sec['name']}: tri bytes not divisible by 6")
    return [list(struct.unpack_from('<3H', data, off)) for off in range(sec['start'], sec['end'], 6)]


def decode_collision_tree(data: bytes, secs: dict, surf_index: int, rigid_index: int, meta: dict) -> dict:
    prefix = f'XModel.surfs[{surf_index}].vertList[{rigid_index}].collisionTree'
    ns = one_section(secs, prefix + '.nodes', required=False)
    ls = one_section(secs, prefix + '.leafs', required=False)
    nodes = []
    if ns:
        if ns['bytes'] % 16:
            raise ValueError(f'{prefix}.nodes invalid size')
        for i, off in enumerate(range(ns['start'], ns['end'], 16)):
            mins = list(struct.unpack_from('<3H', data, off))
            maxs = list(struct.unpack_from('<3H', data, off + 6))
            child_begin, child_count = struct.unpack_from('<HH', data, off + 12)
            nodes.append({'index': i, 'mins': mins, 'maxs': maxs, 'childBeginIndex': child_begin, 'childCount': child_count})
    leaves = []
    if ls:
        if ls['bytes'] % 2:
            raise ValueError(f'{prefix}.leafs invalid size')
        leaves = [{'index': i, 'triangleBeginIndex': struct.unpack_from('<H', data, off)[0]}
                  for i, off in enumerate(range(ls['start'], ls['end'], 2))]
    return {
        'trans': meta['trans'],
        'scale': meta['scale'],
        'nodeCount': meta['nodeCount'],
        'leafCount': meta['leafCount'],
        'nodes': nodes,
        'leaves': leaves,
    }


def decode_render_surfaces(data: bytes, walk: dict, secs: dict) -> list[dict]:
    out = []
    for surf in walk['xmodel']['surfaces']:
        i = surf['index']
        vs = one_section(secs, f'XModel.surfs[{i}].verts0', required=False)
        ts = one_section(secs, f'XModel.surfs[{i}].triIndices', required=False)
        rigids = []
        for r in surf['rigidVertLists']:
            row = dict(r)
            tree = r.get('collisionTree')
            if tree is not None:
                row['collisionTree'] = decode_collision_tree(data, secs, i, r['index'], tree)
            rigids.append(row)
        out.append({
            'index': i,
            'tileMode': surf['tileMode'],
            'flags': surf['flags'],
            'baseVertIndex': surf['baseVertIndex'],
            'vertCount': surf['vertCount'],
            'triCount': surf['triCount'],
            'vertices': decode_packed_vertices(data, vs) if vs else [],
            'triangles': decode_surface_triangles(data, ts) if ts else [],
            'vertexBlendCounts': surf['vertInfo']['vertCount'],
            'rigidVertLists': rigids,
            'sourcePointers': {
                'verts0': surf['verts0Pointer'],
                'triIndices': surf['triIndicesPointer'],
                'vertList': surf['vertListPointer'],
                'vertsBlend': surf['vertInfo']['vertsBlendPointer'],
                'tensionData': surf['vertInfo']['tensionDataPointer'],
            },
        })
    return out


def decode_model_collision_surfaces(data: bytes, walk: dict, secs: dict) -> list[dict]:
    rows = []
    for surf in walk['xmodel']['collisionSurfaces']:
        i = surf['index']
        sec = one_section(secs, f'XModel.collSurfs[{i}].collTris', required=False)
        tris = []
        if sec:
            if sec['bytes'] % 48:
                raise ValueError(f'collSurf {i}: invalid collTri byte count')
            for j, off in enumerate(range(sec['start'], sec['end'], 48)):
                tris.append({
                    'index': j,
                    'plane': f32s(data, off, 4),
                    'svec': f32s(data, off + 16, 4),
                    'tvec': f32s(data, off + 32, 4),
                })
        row = dict(surf)
        row['triangles'] = tris
        rows.append(row)
    return rows


def decode_bone_info(data: bytes, walk: dict, secs: dict) -> list[dict]:
    sec = one_section(secs, 'XModel.boneInfo', required=False)
    if not sec:
        return []
    count = walk['xmodel']['numBones']
    if sec['bytes'] != count * 44:
        raise ValueError('XBoneInfo source size mismatch')
    rows = []
    for i in range(count):
        off = sec['start'] + i * 44
        rows.append({
            'index': i,
            'bounds': [f32s(data, off, 3), f32s(data, off + 12, 3)],
            'offset': f32s(data, off + 24, 3),
            'radiusSquared': f32s(data, off + 36, 1)[0],
            'collmap': data[off + 40],
            'reserved': list(data[off + 41:off + 44]),
        })
    return rows


def inline_string(data: bytes, sec: dict | None) -> str | None:
    if sec is None:
        return None
    raw = data[sec['start']:sec['end']]
    if raw.endswith(b'\0'):
        raw = raw[:-1]
    return raw.decode('latin1')


def decode_phys_preset(data: bytes, secs: dict) -> dict | None:
    sec = one_section(secs, 'XModel.physPreset.PhysPreset.fixed', required=False)
    if not sec:
        return None
    if sec['bytes'] != 84:
        raise ValueError('PhysPreset fixed size mismatch')
    off = sec['start']
    name_ptr = struct.unpack_from('<I', data, off)[0]
    snd_ptr = struct.unpack_from('<I', data, off + 28)[0]
    return {
        'name': inline_string(data, one_section(secs, 'XModel.physPreset.PhysPreset.name', required=False)),
        'namePointer': ptr_kind(name_ptr),
        'flags': struct.unpack_from('<i', data, off + 4)[0],
        'mass': f32s(data, off + 8, 1)[0],
        'bounce': f32s(data, off + 12, 1)[0],
        'friction': f32s(data, off + 16, 1)[0],
        'bulletForceScale': f32s(data, off + 20, 1)[0],
        'explosiveForceScale': f32s(data, off + 24, 1)[0],
        'sndAliasPrefix': inline_string(data, one_section(secs, 'XModel.physPreset.PhysPreset.sndAliasPrefix', required=False)),
        'sndAliasPrefixPointer': ptr_kind(snd_ptr),
        'piecesSpreadFraction': f32s(data, off + 32, 1)[0],
        'piecesUpwardVelocity': f32s(data, off + 36, 1)[0],
        'canFloat': bool(struct.unpack_from('<i', data, off + 40)[0]),
        'gravityScale': f32s(data, off + 44, 1)[0],
        'centerOfMassOffset': f32s(data, off + 48, 3),
        'buoyancyBoxMin': f32s(data, off + 60, 3),
        'buoyancyBoxMax': f32s(data, off + 72, 3),
    }


def decode_brush(data: bytes, secs: dict, prefix: str, meta: dict) -> dict:
    fixed = one_section(secs, prefix + '.fixed')
    off = fixed['start']
    numsides = meta['numSides']
    sides_sec = one_section(secs, prefix + '.sides.fixed', required=False)
    sides = []
    if sides_sec:
        if sides_sec['bytes'] != numsides * 12:
            raise ValueError(f'{prefix}: side count mismatch')
        for i in range(numsides):
            b = sides_sec['start'] + i * 12
            pp = struct.unpack_from('<I', data, b)[0]
            plane_sec = one_section(secs, f'{prefix}.sides[{i}].plane', required=False)
            sides.append({
                'index': i,
                'planePointer': ptr_kind(pp),
                'plane': decode_cplane(data, plane_sec['start']) if plane_sec else None,
                'cflags': struct.unpack_from('<i', data, b + 4)[0],
                'sflags': struct.unpack_from('<i', data, b + 8)[0],
            })
    verts_sec = one_section(secs, prefix + '.verts', required=False)
    verts = []
    if verts_sec:
        verts = [f32s(data, b, 3) for b in range(verts_sec['start'], verts_sec['end'], 12)]
    planes_sec = one_section(secs, prefix + '.planes', required=False)
    planes = []
    if planes_sec:
        planes = [decode_cplane(data, b) for b in range(planes_sec['start'], planes_sec['end'], 20)]
    return {
        'mins': meta['mins'], 'maxs': meta['maxs'], 'contents': meta['contents'],
        'numSides': numsides,
        'sides': sides,
        'axialCFlags': [list(struct.unpack_from('<3i', data, off + 36)), list(struct.unpack_from('<3i', data, off + 48))],
        'axialSFlags': [list(struct.unpack_from('<3i', data, off + 60)), list(struct.unpack_from('<3i', data, off + 72))],
        'numVerts': meta['numVerts'], 'verts': verts,
        'planes': planes,
        'sourcePointers': {'sides': meta['sidesPointer'], 'verts': meta['vertsPointer'], 'planes': meta['planesPointer']},
    }


def decode_collmaps(data: bytes, walk: dict, secs: dict) -> list[dict]:
    out = []
    for collmap in walk['xmodel']['collmaps']:
        i = collmap['index']
        row = {'index': i, 'geomListPointer': collmap['geomListPointer']}
        gl = collmap.get('geomList')
        if gl is not None:
            geoms = []
            for geom in gl['geoms']:
                g = dict(geom)
                brush = geom.get('brush')
                if brush is not None:
                    prefix = f'XModel.collmaps[{i}].geomList.geoms[{geom["index"]}].brush'
                    g['brush'] = decode_brush(data, secs, prefix, brush)
                geoms.append(g)
            row['geomList'] = {'count': gl['count'], 'contents': gl['contents'], 'geomsPointer': gl['geomsPointer'], 'geoms': geoms}
        out.append(row)
    return out


def clipmap_links(path: Path | None, xasset_index: int | None) -> dict | None:
    if path is None or xasset_index is None:
        return None
    cm = json.loads(path.read_text(encoding='utf-8'))
    placements = []
    for row in cm.get('staticModels', []):
        if row.get('xModelAssetIndex') == xasset_index:
            placements.append({
                'placementIndex': row.get('index'),
                'origin': row.get('origin'),
                'invScaledAxis': row.get('invScaledAxis'),
                'absmin': row.get('absmin'),
                'absmax': row.get('absmax'),
                'contents': row.get('contents'),
            })
    target = None
    for row in cm.get('staticModelXModelNameResolution', {}).get('uniqueTargets', []):
        if row.get('assetIndex') == xasset_index:
            target = row
            break
    return {
        'clipMapNormalizedFormat': cm.get('format'),
        'clipMapSource': cm.get('source'),
        'xassetIndex': xasset_index,
        'resolvedXModelIdentity': target.get('name') if target else None,
        'placementCount': len(placements),
        'placements': placements,
    }


def normalize(data: bytes, asset_start: int, xasset_index: int | None = None, clipmap_path: Path | None = None) -> dict:
    walk = XModelWalker(data, asset_start).walk_xmodel()
    if walk['blockers']:
        raise ValueError(f"XModel walk has blockers: {walk['blockers']}")
    secs = section_map(walk)
    links = clipmap_links(clipmap_path, xasset_index)
    resolved_name = walk['xmodel']['name']
    if resolved_name is None and links:
        resolved_name = links['resolvedXModelIdentity']
    out = {
        'format': 't6-xmodel-collision-normalized-v1',
        'source': {
            'expandedSha256': hashlib.sha256(data).hexdigest(),
            'fixedStart': walk['assetFixedStart'],
            'serializedEnd': walk['assetSerializedEnd'],
            'serializedBytes': walk['assetSerializedBytes'],
            'serializedSha256': walk['assetSerializedSha256'],
        },
        'identity': {
            'xassetIndex': xasset_index,
            'name': resolved_name,
            'serializedName': walk['xmodel']['name'],
            'namePointer': walk['xmodel']['namePointer'],
        },
        'model': {
            k: walk['xmodel'][k] for k in ('numBones','numRootBones','numSurfs','lodRampType','numLods','collLod','numCollSurfs','contents','radius','mins','maxs','memUsage','flags','bad','numCollmaps')
        },
        'renderSurfaces': decode_render_surfaces(data, walk, secs),
        'collisionSurfaces': decode_model_collision_surfaces(data, walk, secs),
        'boneCollisionInfo': decode_bone_info(data, walk, secs),
        'physPreset': decode_phys_preset(data, secs),
        'collmaps': decode_collmaps(data, walk, secs),
        'placementLinks': links,
        'rawPointerMetadata': {
            'materialHandles': walk['xmodel']['materialHandles'],
            'physPreset': walk['xmodel']['physPresetPointer'],
            'physConstraints': walk['xmodel']['physConstraintsPointer'],
        },
        'sourceStrideRules': walk['sourceStrideRules'],
        'inlineAssetDetails': walk['details'],
        'unresolved': [],
    }
    # PhysConstraints is safe only when null/packed; inline would have blocked.
    if walk['xmodel']['physConstraintsPointer']['kind'] == 'packed':
        out['unresolved'].append({'kind': 'packed_phys_constraints_reference', 'pointer': walk['xmodel']['physConstraintsPointer']})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--asset-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--xasset-index', type=int)
    ap.add_argument('--clipmap-normalized', type=Path)
    ap.add_argument('--expect-end', type=lambda x: int(x, 0))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    out = normalize(data, args.asset_start, args.xasset_index, args.clipmap_normalized)
    if args.expect_end is not None and out['source']['serializedEnd'] != args.expect_end:
        raise SystemExit(f"normalized walk ended {out['source']['serializedEnd']} expected {args.expect_end}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({
        'out': str(args.out),
        'bytes': args.out.stat().st_size,
        'sha256': hashlib.sha256(args.out.read_bytes()).hexdigest(),
        'identity': out['identity'],
        'placements': out['placementLinks']['placementCount'] if out['placementLinks'] else None,
        'renderSurfaceCount': len(out['renderSurfaces']),
        'collisionSurfaceCount': len(out['collisionSurfaces']),
        'collisionTriCount': sum(len(x['triangles']) for x in out['collisionSurfaces']),
        'boneCollisionCount': len(out['boneCollisionInfo']),
        'collmapCount': len(out['collmaps']),
        'unresolved': out['unresolved'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
