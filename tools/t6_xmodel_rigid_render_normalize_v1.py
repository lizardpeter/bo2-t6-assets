#!/usr/bin/env python3
"""Normalize owned rigid T6 XModel XSurfaces into render-ready geometry.

Scope v1:
- PC32 T6 XModel fixed header at a caller-provided source offset.
- owned/inlined XSurface array.
- rigid surfaces only (flags & 1 == 0, no vertsBlend/tension stream).
- owned GfxPackedVertex, XRigidVertList, XSurfaceCollisionTree and triIndices.
- material handle pointer array identity is retained, but Material assets are not
  decoded here.

This is intentionally fail-closed for blended/skinned XSurfaces. It preserves
raw packed vertex fields alongside decoded positions, UVs, colors, normals and
tangents, and derives the exact rigid joint for every vertex from
XRigidVertList::boneOffset / sizeof(DObjSkelMat) (64 bytes in T6).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
XMODEL_SIZE = 248
XSURFACE_SIZE = 80
GFX_PACKED_VERTEX_SIZE = 32
XRIGID_VERT_LIST_SIZE = 12
XSURFACE_COLLISION_TREE_SIZE = 40
XSURFACE_COLLISION_NODE_SIZE = 16
XSURFACE_COLLISION_LEAF_SIZE = 2
DOBJ_SKEL_MAT_SIZE = 64


class RenderNormalizeError(RuntimeError):
    pass


def is_inline(p: int) -> bool:
    return p in (PTR_FOLLOWING, PTR_INSERT)


def ptr_kind(p: int) -> dict:
    if p == 0:
        return {"raw": p, "rawHex": "0x00000000", "kind": "null"}
    if p == PTR_FOLLOWING:
        return {"raw": p, "rawHex": "0xFFFFFFFF", "kind": "following"}
    if p == PTR_INSERT:
        return {"raw": p, "rawHex": "0xFFFFFFFE", "kind": "insert"}
    enc = (p - 1) & 0xFFFFFFFF
    return {"raw": p, "rawHex": f"0x{p:08X}", "kind": "packed", "block": enc >> 29, "offset": enc & 0x1FFFFFFF}


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def i16(data: bytes, off: int) -> int:
    return struct.unpack_from('<h', data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from('<f', data, off)[0]


def cstring(data: bytes, off: int) -> tuple[str, int]:
    try:
        end = data.index(b'\0', off)
    except ValueError as e:
        raise RenderNormalizeError(f'unterminated string at {off}') from e
    return data[off:end].decode('latin1', 'replace'), end + 1


def half_to_float(bits: int) -> float:
    return struct.unpack('<e', struct.pack('<H', bits))[0]


def unpack_uv(packed: int) -> list[float]:
    return [half_to_float(packed & 0xFFFF), half_to_float((packed >> 16) & 0xFFFF)]


def _bits_to_f32(bits: int) -> float:
    return struct.unpack('<f', struct.pack('<I', bits & 0xFFFFFFFF))[0]


def unpack_unitvec_third_based(packed: int) -> list[float]:
    out = []
    for shift in (0, 10, 20):
        v = (packed >> shift) & 0x3FF
        bits = (v - 2 * (v & 0x200) + 0x40400000) & 0xFFFFFFFF
        out.append((_bits_to_f32(bits) - 3.0) * 8208.0312)
    return out


def normalize3(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    if not math.isfinite(n) or n <= 0:
        raise RenderNormalizeError(f'invalid vector norm {n}: {v}')
    return [x / n for x in v]


def unpack_color(packed: int) -> list[float]:
    return [((packed >> shift) & 0xFF) / 255.0 for shift in (0, 8, 16, 24)]


def decode_vertex(data: bytes, off: int, index: int) -> dict:
    xyz = list(struct.unpack_from('<3f', data, off))
    if not all(math.isfinite(x) for x in xyz):
        raise RenderNormalizeError(f'vertex {index}: non-finite position')
    binormal = f32(data, off + 12)
    if binormal not in (-1.0, 1.0):
        raise RenderNormalizeError(f'vertex {index}: invalid binormalSign {binormal}')
    color, tex, normal, tangent = struct.unpack_from('<4I', data, off + 16)
    decoded_normal = normalize3(unpack_unitvec_third_based(normal))
    decoded_tangent = normalize3(unpack_unitvec_third_based(tangent))
    uv = unpack_uv(tex)
    if not all(math.isfinite(x) for x in uv):
        raise RenderNormalizeError(f'vertex {index}: non-finite UV')
    return {
        'index': index,
        'position': xyz,
        'uv': uv,
        'color': unpack_color(color),
        'normal': decoded_normal,
        'tangent': decoded_tangent + [binormal],
        'raw': {
            'binormalSign': binormal,
            'colorPacked': color,
            'texCoordPacked': tex,
            'normalPacked': normal,
            'tangentPacked': tangent,
        },
    }


def parse_collision_tree(data: bytes, pos: int, label: str) -> tuple[dict, int]:
    if pos + XSURFACE_COLLISION_TREE_SIZE > len(data):
        raise RenderNormalizeError(f'{label}: truncated collision tree')
    trans = list(struct.unpack_from('<3f', data, pos))
    scale = list(struct.unpack_from('<3f', data, pos + 12))
    if not all(math.isfinite(x) for x in trans):
        raise RenderNormalizeError(f'{label}: non-finite collision translation')
    if not all(math.isfinite(x) or (math.isinf(x) and x > 0) for x in scale):
        raise RenderNormalizeError(f'{label}: invalid collision scale')
    node_count = u32(data, pos + 24)
    node_ptr = u32(data, pos + 28)
    leaf_count = u32(data, pos + 32)
    leaf_ptr = u32(data, pos + 36)
    cur = pos + XSURFACE_COLLISION_TREE_SIZE
    nodes_start = None
    leafs_start = None
    if is_inline(node_ptr):
        nodes_start = cur
        cur += node_count * XSURFACE_COLLISION_NODE_SIZE
    if is_inline(leaf_ptr):
        leafs_start = cur
        cur += leaf_count * XSURFACE_COLLISION_LEAF_SIZE
    if cur > len(data):
        raise RenderNormalizeError(f'{label}: collision payload outside file')
    return {
        'sourceStart': pos,
        'sourceEnd': cur,
        'trans': trans,
        'scale': scale,
        'nodeCount': node_count,
        'nodePointer': ptr_kind(node_ptr),
        'nodesSourceStart': nodes_start,
        'leafCount': leaf_count,
        'leafPointer': ptr_kind(leaf_ptr),
        'leafsSourceStart': leafs_start,
    }, cur


def normalize(data: bytes, start: int) -> dict:
    if start < 0 or start + XMODEL_SIZE > len(data):
        raise RenderNormalizeError('XModel fixed header outside file')
    name_ptr = u32(data, start)
    num_bones = data[start + 4]
    num_root = data[start + 5]
    num_surfs = data[start + 6]
    lod_ramp = data[start + 7]
    if num_root > num_bones:
        raise RenderNormalizeError('numRootBones > numBones')
    non_root = num_bones - num_root
    ptrs = {
        'boneNames': u32(data, start + 8),
        'parentList': u32(data, start + 12),
        'quats': u32(data, start + 16),
        'trans': u32(data, start + 20),
        'partClassification': u32(data, start + 24),
        'baseMat': u32(data, start + 28),
        'surfs': u32(data, start + 32),
        'materialHandles': u32(data, start + 36),
    }
    pos = start + XMODEL_SIZE
    if not is_inline(name_ptr):
        raise RenderNormalizeError(f'v1 requires inline model name, got {ptr_kind(name_ptr)}')
    name, pos = cstring(data, pos)

    skeleton_sections = [
        ('boneNames', num_bones * 2),
        ('parentList', non_root),
        ('quats', non_root * 8),
        ('trans', non_root * 16),
        ('partClassification', num_bones),
        ('baseMat', num_bones * 32),
    ]
    skeleton_source = {}
    for field, byte_count in skeleton_sections:
        p = ptrs[field]
        if is_inline(p):
            skeleton_source[field] = {'start': pos, 'end': pos + byte_count, 'bytes': byte_count}
            pos += byte_count
        else:
            skeleton_source[field] = {'pointer': ptr_kind(p), 'bytes': 0}
    if not is_inline(ptrs['surfs']):
        raise RenderNormalizeError(f'v1 requires inline XSurface array, got {ptr_kind(ptrs["surfs"])}')

    surfs_fixed = pos
    pos += num_surfs * XSURFACE_SIZE
    surface_meta = []
    for i in range(num_surfs):
        b = surfs_fixed + i * XSURFACE_SIZE
        blends = [i16(data, b + 16 + 2 * j) for j in range(4)]
        if any(x < 0 for x in blends):
            raise RenderNormalizeError(f'surface {i}: negative blend count')
        surface_meta.append({
            'index': i,
            'tileMode': data[b],
            'vertListCount': data[b + 1],
            'flags': u16(data, b + 2),
            'vertCount': u16(data, b + 4),
            'triCount': u16(data, b + 6),
            'baseVertIndex': u16(data, b + 8),
            'triIndicesPointer': u32(data, b + 12),
            'blendCounts': blends,
            'vertsBlendPointer': u32(data, b + 24),
            'tensionPointer': u32(data, b + 28),
            'verts0Pointer': u32(data, b + 32),
            'vertListPointer': u32(data, b + 40),
        })

    surfaces = []
    total_vertices = total_triangles = total_rigid_lists = 0
    for sm in surface_meta:
        i = sm['index']
        if sm['flags'] & 1:
            raise RenderNormalizeError(f'surface {i}: blended/skinned flags=0x{sm["flags"]:X} unsupported by rigid v1')
        if any(sm['blendCounts']) or sm['vertsBlendPointer'] or sm['tensionPointer']:
            raise RenderNormalizeError(f'surface {i}: blend/tension stream present; rigid v1 refuses it')
        if not is_inline(sm['verts0Pointer']):
            raise RenderNormalizeError(f'surface {i}: verts0 not inline')
        vertex_source_start = pos
        vertices = [decode_vertex(data, pos + j * GFX_PACKED_VERTEX_SIZE, j) for j in range(sm['vertCount'])]
        pos += sm['vertCount'] * GFX_PACKED_VERTEX_SIZE

        if not is_inline(sm['vertListPointer']):
            raise RenderNormalizeError(f'surface {i}: rigid vert list not inline')
        list_fixed_start = pos
        pos += sm['vertListCount'] * XRIGID_VERT_LIST_SIZE
        rigid_lists = []
        vertex_cursor = 0
        tri_cursor = 0
        for j in range(sm['vertListCount']):
            b = list_fixed_start + j * XRIGID_VERT_LIST_SIZE
            bone_offset = u16(data, b)
            vert_count = u16(data, b + 2)
            tri_offset = u16(data, b + 4)
            tri_count = u16(data, b + 6)
            tree_ptr = u32(data, b + 8)
            if bone_offset % DOBJ_SKEL_MAT_SIZE:
                raise RenderNormalizeError(f'surface {i} list {j}: boneOffset {bone_offset} not /64')
            joint = bone_offset // DOBJ_SKEL_MAT_SIZE
            if joint >= num_bones:
                raise RenderNormalizeError(f'surface {i} list {j}: joint {joint} >= {num_bones}')
            if tri_offset != tri_cursor:
                raise RenderNormalizeError(f'surface {i} list {j}: triOffset {tri_offset} != expected {tri_cursor}')
            if vertex_cursor + vert_count > sm['vertCount']:
                raise RenderNormalizeError(f'surface {i} list {j}: vertex range overflow')
            for vi in range(vertex_cursor, vertex_cursor + vert_count):
                vertices[vi]['jointIndex'] = joint
            collision = None
            if is_inline(tree_ptr):
                collision, pos = parse_collision_tree(data, pos, f'surface {i} rigid list {j}')
            rigid_lists.append({
                'index': j,
                'boneOffset': bone_offset,
                'jointIndex': joint,
                'vertexStart': vertex_cursor,
                'vertCount': vert_count,
                'triOffset': tri_offset,
                'triCount': tri_count,
                'collisionTreePointer': ptr_kind(tree_ptr),
                'collisionTree': collision,
            })
            vertex_cursor += vert_count
            tri_cursor += tri_count
        if vertex_cursor != sm['vertCount']:
            raise RenderNormalizeError(f'surface {i}: rigid lists cover {vertex_cursor}/{sm["vertCount"]} vertices')
        if tri_cursor != sm['triCount']:
            raise RenderNormalizeError(f'surface {i}: rigid lists cover {tri_cursor}/{sm["triCount"]} triangles')
        if any('jointIndex' not in v for v in vertices):
            raise RenderNormalizeError(f'surface {i}: unassigned rigid vertex')

        if not is_inline(sm['triIndicesPointer']):
            raise RenderNormalizeError(f'surface {i}: triIndices not inline')
        tri_source_start = pos
        triangles = [list(struct.unpack_from('<3H', data, pos + j * 6)) for j in range(sm['triCount'])]
        pos += sm['triCount'] * 6
        for j, tri in enumerate(triangles):
            if any(v >= sm['vertCount'] for v in tri):
                raise RenderNormalizeError(f'surface {i} tri {j}: index {tri} outside {sm["vertCount"]}')

        surfaces.append({
            **{k: sm[k] for k in ('index','tileMode','flags','baseVertIndex','vertCount','triCount')},
            'source': {
                'fixedStart': surfs_fixed + i * XSURFACE_SIZE,
                'vertexStart': vertex_source_start,
                'rigidListFixedStart': list_fixed_start,
                'triangleStart': tri_source_start,
                'serializedPayloadEnd': pos,
            },
            'vertices': vertices,
            'triangles': triangles,
            'rigidVertLists': rigid_lists,
        })
        total_vertices += sm['vertCount']
        total_triangles += sm['triCount']
        total_rigid_lists += sm['vertListCount']

    material_handles = []
    material_array_start = pos
    if is_inline(ptrs['materialHandles']):
        for i in range(num_surfs):
            material_handles.append(ptr_kind(u32(data, pos + i * 4)))
        pos += num_surfs * 4
    elif ptrs['materialHandles']:
        raise RenderNormalizeError('v1 requires inline material handle array when non-null')

    lods = []
    for i in range(4):
        b = start + 40 + i * 28
        dist = f32(data, b)
        nums = u16(data, b + 4)
        surf_index = u16(data, b + 6)
        bits = list(struct.unpack_from('<5I', data, b + 8))
        if not math.isfinite(dist):
            raise RenderNormalizeError(f'lod {i}: non-finite dist')
        lods.append({'index': i, 'dist': dist, 'numSurfs': nums, 'surfIndex': surf_index, 'partBits': bits})
    num_lods = u16(data, start + 196)
    for lod in lods[:num_lods]:
        if lod['surfIndex'] + lod['numSurfs'] > num_surfs:
            raise RenderNormalizeError(f'lod {lod["index"]}: surface range outside model')

    span = data[start:pos]
    return {
        'format': 't6-xmodel-rigid-render-normalized-v1',
        'source': {
            'expandedSha256': hashlib.sha256(data).hexdigest(),
            'xmodelFixedStart': start,
            'renderPrefixEnd': pos,
            'renderPrefixBytes': pos - start,
            'renderPrefixSha256': hashlib.sha256(span).hexdigest(),
            'surfaceFixedArrayStart': surfs_fixed,
            'materialHandleArrayStart': material_array_start,
        },
        'identity': {
            'name': name,
            'numBones': num_bones,
            'numRootBones': num_root,
            'numSurfs': num_surfs,
            'lodRampType': lod_ramp,
            'numLods': num_lods,
            'collLod': i16(data, start + 198),
        },
        'lods': lods,
        'surfaces': surfaces,
        'materialHandles': material_handles,
        'validation': {
            'scope': 'owned rigid XSurfaces only; blended/skinned surfaces fail closed',
            'allRigid': True,
            'totalVertices': total_vertices,
            'totalTriangles': total_triangles,
            'totalRigidVertLists': total_rigid_lists,
            'allVerticesJointAssigned': True,
            'allTriangleIndicesInBounds': True,
            'dobjSkelMatBytes': DOBJ_SKEL_MAT_SIZE,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--asset-start', required=True, type=lambda x: int(x, 0))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    result = normalize(data, args.asset_start)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'name': result['identity']['name'],
        'out': str(args.out),
        'vertices': result['validation']['totalVertices'],
        'triangles': result['validation']['totalTriangles'],
        'rigidVertLists': result['validation']['totalRigidVertLists'],
        'renderPrefixEnd': result['source']['renderPrefixEnd'],
        'renderPrefixSha256': result['source']['renderPrefixSha256'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
