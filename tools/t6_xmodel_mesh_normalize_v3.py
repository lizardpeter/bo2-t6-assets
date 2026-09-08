#!/usr/bin/env python3
"""Lossless T6 PC32 XModel mesh normalizer v3 with reusable-owner replay.

v3 preserves the strict inline decoder from t6_xmodel_mesh_normalize_v2 and
adds one fail-closed path for packed VIRTUAL XModel mesh/skeleton storage.  The
packed target is accepted only when t6_xmodel_skeleton_normalize_v2 finds one
unique earlier top-level XModel whose native VIRTUAL allocation sequence
replays the target's packed pointers exactly, including XSurface nested
allocations.  Geometry is then decoded from that proven physical owner while
the target keeps its own XAsset identity.

Inline XModels do not require any map/StringTable prefix parser.  StringTable
mapping is requested lazily only when a packed name actually needs it.
Materials remain outside this layer.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

from t6_clipmap_normalize_v5 import parse_top_level_xasset_table
from t6_clipmap_normalize_v6 import walk_map_prefix_stringtable
from t6_xmodel_mesh_normalize_v2 import Normalizer, MeshError, ptr_kind, XMODEL_LOD_INFO
from t6_xmodel_skeleton_normalize_v2 import resolve_reusable_owner


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _fixed_geometry_signature(data: bytes, start: int) -> dict:
    """Fixed-header fields that define skeleton/surface/LOD geometry shape."""
    num_bones = data[start + 4]
    num_root_bones = data[start + 5]
    num_surfs = data[start + 6]
    num_lods = _u16(data, start + 196)
    lods = []
    for i in range(4):
        b = start + 40 + i * XMODEL_LOD_INFO
        lods.append({
            'index': i,
            'distBits': f'0x{_u32(data,b):08X}',
            'numSurfs': _u16(data, b + 4),
            'surfIndex': _u16(data, b + 6),
            'partBits': [_u32(data, b + 8 + 4*k) for k in range(5)],
        })
    return {
        'numBones': num_bones,
        'numRootBones': num_root_bones,
        'numSurfs': num_surfs,
        'numLods': num_lods,
        'lods': lods,
    }


def _logical_map_if_needed(data: bytes, current: dict[int, str] | None) -> dict[int, str]:
    if current is not None:
        return current
    try:
        table = parse_top_level_xasset_table(data)
        return walk_map_prefix_stringtable(data, table)['logicalToText']
    except Exception as exc:
        raise MeshError(
            'packed-name/reusable mesh path requires a proven StringTable logical map; '
            f'available prefix parser did not apply: {exc!r}'
        ) from exc


def normalize_mesh(
    data: bytes,
    asset_start: int,
    *,
    xasset_index: int | None = None,
    identity_name: str | None = None,
    logical_to_text: dict[int, str] | None = None,
) -> dict:
    """Normalize one XModel, resolving packed reusable geometry only by replay."""
    direct_error = None
    try:
        # The v2 decoder needs logical_to_text only for a packed XModel name.
        # Passing None keeps ordinary inline physical XModels zone-agnostic.
        out = Normalizer(data, asset_start, logical_to_text=logical_to_text).normalize()
        if identity_name is not None and out['identity']['name'] != identity_name:
            raise MeshError(
                f'direct XModel identity mismatch {out["identity"]["name"]!r} != {identity_name!r}'
            )
        out['format'] = 't6-xmodel-mesh-normalized-v3'
        out['meshSource'] = {
            'mode': 'inline_owned',
            'targetFixedStart': asset_start,
            'owner': None,
        }
        return out
    except Exception as exc:
        direct_error = repr(exc)

    bone_ptr = _u32(data, asset_start + 8)
    pk = ptr_kind(bone_ptr)
    if pk.get('kind') != 'packed' or pk.get('block') != 5:
        raise MeshError(
            f'direct mesh decode failed and boneNames is not packed VIRTUAL: '
            f'direct={direct_error}; boneNames={pk}'
        )
    if xasset_index is None:
        raise MeshError(
            f'direct mesh decode failed ({direct_error}); packed reusable geometry '
            'requires xasset_index for unique owner replay'
        )

    logical_to_text = _logical_map_if_needed(data, logical_to_text)
    proof = resolve_reusable_owner(data, asset_start, xasset_index)
    if not proof.get('allMatch') or proof.get('surfaceComparisonCount', 0) <= 0:
        raise MeshError('reusable-owner proof did not close all surface pointer comparisons')
    owner_start = int(proof['ownerFixedStart'])

    target_sig = _fixed_geometry_signature(data, asset_start)
    owner_sig = _fixed_geometry_signature(data, owner_start)
    if target_sig != owner_sig:
        raise MeshError(
            'reusable owner fixed geometry/LOD signature differs from target: '
            + json.dumps({'target': target_sig, 'owner': owner_sig}, sort_keys=True)
        )

    owner_doc = Normalizer(data, owner_start, logical_to_text=logical_to_text).normalize()
    target_name = identity_name
    if target_name is None:
        name_ptr = ptr_kind(_u32(data, asset_start))
        if name_ptr.get('kind') == 'packed' and name_ptr.get('block') == 5:
            target_name = logical_to_text.get(int(name_ptr['offset']))
        if not target_name:
            raise MeshError('packed reusable target identity requires exact identity_name or StringTable mapping')

    out = copy.deepcopy(owner_doc)
    out['format'] = 't6-xmodel-mesh-normalized-v3'
    out['identity'] = {
        'name': target_name,
        'xassetIndex': xasset_index,
        'serializedNamePointer': ptr_kind(_u32(data, asset_start)),
    }
    out['source'] = {
        'targetAssetFixedStart': asset_start,
        'targetFixedHeaderSha256': hashlib.sha256(data[asset_start:asset_start+248]).hexdigest(),
        'ownerAssetFixedStart': owner_start,
        'ownerMeshOwnedSerializedEnd': owner_doc['source']['meshOwnedSerializedEnd'],
        'ownerMeshOwnedSerializedBytes': owner_doc['source']['meshOwnedSerializedBytes'],
        'ownerMeshOwnedSerializedSha256': owner_doc['source']['meshOwnedSerializedSha256'],
    }
    out['meshSource'] = {
        'mode': 'packed_reusable_owner',
        'directDecodeError': direct_error,
        'targetFixedStart': asset_start,
        'owner': {
            'xassetIndex': proof['ownerAssetIndex'],
            'name': proof['ownerName'],
            'fixedSourceStart': owner_start,
        },
        'virtualReplayBase': proof['virtualReplayBase'],
        'comparisonCount': proof['comparisonCount'],
        'surfaceComparisonCount': proof['surfaceComparisonCount'],
        'comparisons': proof['comparisons'],
        'fixedGeometrySignatureExact': True,
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--asset-start', required=True, type=lambda x: int(x, 0))
    ap.add_argument('--xasset-index', type=int)
    ap.add_argument('--name')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    data = a.expanded.read_bytes()
    d = normalize_mesh(
        data,
        a.asset_start,
        xasset_index=a.xasset_index,
        identity_name=a.name,
    )
    d['expandedSha256'] = hashlib.sha256(data).hexdigest()
    text = json.dumps(d, indent=2, sort_keys=True) + '\n'
    a.out.write_text(text, encoding='utf-8')
    print(json.dumps({
        'out': str(a.out),
        'bytes': len(text.encode()),
        'sha256': hashlib.sha256(text.encode()).hexdigest(),
        'name': d['identity']['name'],
        'meshSourceMode': d['meshSource']['mode'],
        'surfaces': len(d['surfaces']),
        'vertices': sum(s['vertCount'] for s in d['surfaces']),
        'triangles': sum(s['triCount'] for s in d['surfaces']),
        'unweightedVertices': sum(s['unweightedVertexCount'] for s in d['surfaces']),
    }, sort_keys=True))


if __name__ == '__main__':
    main()
