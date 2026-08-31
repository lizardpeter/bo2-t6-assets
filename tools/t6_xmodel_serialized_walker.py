#!/usr/bin/env python3
"""General T6 PC32 serialized XModel source-byte walker.

Walks one serialized XModel from a caller-provided fixed-record source offset.
All source consumption is derived from the pinned T6 structure/ZoneCode
contract. Native alignment affects destination-memory allocation only; it does
not add padding bytes to the FastFile source stream.

Retail-proven source strides encoded here:
- XModel fixed: 248 bytes
- XSurface fixed: 80 bytes
- XSurfaceTri16 source record: 6 bytes (native destination alignment is 16)
- PhysGeomInfo16 source record: 68 bytes (native destination alignment is 16)

Unsupported inline external XAssets fail closed through blockers rather than
being skipped. Packed/null references consume no source bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from t6_clipmap_serialized_walker import WalkError, is_inline, ptr_kind
from t6_clipmap_serialized_walker_v3 import Walker as AssetDispatchWalker

XMODEL_SIZE = 248
XSURFACE_SIZE = 80
XSURFACE_TRI_SOURCE_SIZE = 6
GFX_PACKED_VERTEX_SIZE = 32
XRIGID_VERT_LIST_SIZE = 12
XSURFACE_COLLISION_TREE_SIZE = 40
XSURFACE_COLLISION_NODE_SIZE = 16
XSURFACE_COLLISION_LEAF_SIZE = 2
DOBJ_ANIM_MAT_SIZE = 32
XMODEL_QUAT_SIZE = 8
XMODEL_COLL_SURF_SIZE = 44
XMODEL_COLL_TRI_SIZE = 48
XBONE_INFO_SIZE = 44
COLLMAP_SIZE = 4
PHYS_GEOM_LIST_SIZE = 12
PHYS_GEOM_INFO_SOURCE_SIZE = 68
BRUSH_WRAPPER_SIZE = 96
CBRUSHSIDE_SIZE = 12
CPLANE_SIZE = 20
VEC3_SIZE = 12
PHYS_CONSTRAINTS_SIZE = 8 + 16 * 168


class XModelWalker(AssetDispatchWalker):
    def _nonnegative(self, value: int, field: str) -> int:
        if value < 0:
            raise WalkError(f"{field}: negative count {value}")
        return value

    def _finite3(self, base: int) -> list[float]:
        vals = list(struct.unpack_from('<3f', self.data, base))
        if not all(math.isfinite(v) for v in vals):
            raise WalkError(f'non-finite vec3 at {base}')
        return vals

    def _collision_scale3(self, base: int) -> list[float]:
        vals = list(struct.unpack_from('<3f', self.data, base))
        # Retail T6 writes +INF for a degenerate quantization axis in some
        # XSurfaceCollisionTree records (zero extent => reciprocal scale INF).
        # NaN and -INF remain invalid.
        if not all(math.isfinite(v) or (math.isinf(v) and v > 0) for v in vals):
            raise WalkError(f'invalid collision-tree scale vec3 at {base}')
        return vals

    def walk_collision_tree(self, label: str) -> dict:
        base, _ = self.take(XSURFACE_COLLISION_TREE_SIZE, f'{label}.fixed')
        trans = self._finite3(base)
        scale = self._collision_scale3(base + 12)
        node_count = self.u32at(base, 24)
        nodes_ptr = self.u32at(base, 28)
        leaf_count = self.u32at(base, 32)
        leafs_ptr = self.u32at(base, 36)
        if is_inline(nodes_ptr):
            self.take(node_count * XSURFACE_COLLISION_NODE_SIZE, f'{label}.nodes',
                      meta={'count': node_count, 'recordBytes': XSURFACE_COLLISION_NODE_SIZE})
        if is_inline(leafs_ptr):
            self.take(leaf_count * XSURFACE_COLLISION_LEAF_SIZE, f'{label}.leafs',
                      meta={'count': leaf_count, 'recordBytes': XSURFACE_COLLISION_LEAF_SIZE})
        return {
            'trans': trans, 'scale': scale,
            'nodeCount': node_count, 'nodesPointer': ptr_kind(nodes_ptr),
            'leafCount': leaf_count, 'leafsPointer': ptr_kind(leafs_ptr),
        }

    def walk_xsurface(self, fixed_base: int, index: int) -> dict:
        label = f'XModel.surfs[{index}]'
        tile_mode = self.data[fixed_base]
        vert_list_count = self.data[fixed_base + 1]
        flags = self.u16at(fixed_base, 2)
        vert_count = self.u16at(fixed_base, 4)
        tri_count = self.u16at(fixed_base, 6)
        base_vert_index = self.u16at(fixed_base, 8)
        tri_indices_ptr = self.u32at(fixed_base, 12)
        blend_counts = [self.i16at(fixed_base, 16 + 2 * i) for i in range(4)]
        if any(v < 0 for v in blend_counts):
            raise WalkError(f'{label}: negative vertInfo count {blend_counts}')
        verts_blend_ptr = self.u32at(fixed_base, 24)
        tension_ptr = self.u32at(fixed_base, 28)
        verts0_ptr = self.u32at(fixed_base, 32)
        vert_list_ptr = self.u32at(fixed_base, 40)

        blend_count = blend_counts[0] + 3 * blend_counts[1] + 5 * blend_counts[2] + 7 * blend_counts[3]
        tension_count = sum(blend_counts)

        # XSurface serializer reorder: vertInfo -> verts0 -> vertList -> triIndices.
        if is_inline(verts_blend_ptr):
            self.take(blend_count * 2, f'{label}.vertInfo.vertsBlend',
                      meta={'count': blend_count, 'recordBytes': 2})
        if is_inline(tension_ptr):
            self.take(tension_count * 4, f'{label}.vertInfo.tensionData',
                      meta={'count': tension_count, 'recordBytes': 4})

        if not (flags & 1) and is_inline(verts0_ptr):
            self.take(vert_count * GFX_PACKED_VERTEX_SIZE, f'{label}.verts0',
                      meta={'count': vert_count, 'recordBytes': GFX_PACKED_VERTEX_SIZE})

        trees = []
        if is_inline(vert_list_ptr):
            a, _ = self.take(vert_list_count * XRIGID_VERT_LIST_SIZE, f'{label}.vertList.fixed',
                             meta={'count': vert_list_count, 'recordBytes': XRIGID_VERT_LIST_SIZE})
            for j in range(vert_list_count):
                b = a + j * XRIGID_VERT_LIST_SIZE
                tree_ptr = self.u32at(b, 8)
                row = {
                    'index': j,
                    'boneOffset': self.u16at(b, 0),
                    'vertCount': self.u16at(b, 2),
                    'triOffset': self.u16at(b, 4),
                    'triCount': self.u16at(b, 6),
                    'collisionTreePointer': ptr_kind(tree_ptr),
                }
                if is_inline(tree_ptr):
                    row['collisionTree'] = self.walk_collision_tree(f'{label}.vertList[{j}].collisionTree')
                trees.append(row)

        if is_inline(tri_indices_ptr):
            self.take(tri_count * XSURFACE_TRI_SOURCE_SIZE, f'{label}.triIndices',
                      meta={'count': tri_count, 'recordBytes': XSURFACE_TRI_SOURCE_SIZE,
                            'nativeDestinationAlignment': 16})

        return {
            'index': index,
            'tileMode': tile_mode,
            'vertListCount': vert_list_count,
            'flags': flags,
            'vertCount': vert_count,
            'triCount': tri_count,
            'baseVertIndex': base_vert_index,
            'triIndicesPointer': ptr_kind(tri_indices_ptr),
            'vertInfo': {
                'vertCount': blend_counts,
                'vertsBlendPointer': ptr_kind(verts_blend_ptr),
                'tensionDataPointer': ptr_kind(tension_ptr),
            },
            'verts0Pointer': ptr_kind(verts0_ptr),
            'vertListPointer': ptr_kind(vert_list_ptr),
            'rigidVertLists': trees,
        }

    def walk_brush_wrapper(self, label: str) -> dict:
        base, _ = self.take(BRUSH_WRAPPER_SIZE, f'{label}.fixed')
        mins = self._finite3(base)
        contents = self.i32at(base, 12)
        maxs = self._finite3(base + 16)
        numsides = self.u32at(base, 28)
        sides_ptr = self.u32at(base, 32)
        numverts = self.u32at(base, 84)
        verts_ptr = self.u32at(base, 88)
        planes_ptr = self.u32at(base, 92)

        if is_inline(sides_ptr):
            a, _ = self.take(numsides * CBRUSHSIDE_SIZE, f'{label}.sides.fixed',
                             meta={'count': numsides, 'recordBytes': CBRUSHSIDE_SIZE})
            for i in range(numsides):
                plane_ptr = self.u32at(a + i * CBRUSHSIDE_SIZE, 0)
                if is_inline(plane_ptr):
                    self.take(CPLANE_SIZE, f'{label}.sides[{i}].plane')
        if is_inline(verts_ptr):
            self.take(numverts * VEC3_SIZE, f'{label}.verts',
                      meta={'count': numverts, 'recordBytes': VEC3_SIZE})
        if is_inline(planes_ptr):
            self.take(numsides * CPLANE_SIZE, f'{label}.planes',
                      meta={'count': numsides, 'recordBytes': CPLANE_SIZE})

        return {
            'mins': mins, 'maxs': maxs, 'contents': contents,
            'numSides': numsides, 'sidesPointer': ptr_kind(sides_ptr),
            'numVerts': numverts, 'vertsPointer': ptr_kind(verts_ptr),
            'planesPointer': ptr_kind(planes_ptr),
        }

    def walk_phys_geom_list(self, label: str) -> dict:
        base, _ = self.take(PHYS_GEOM_LIST_SIZE, f'{label}.fixed')
        count = self.u32at(base, 0)
        geoms_ptr = self.u32at(base, 4)
        contents = self.i32at(base, 8)
        geoms = []
        if is_inline(geoms_ptr):
            a, _ = self.take(count * PHYS_GEOM_INFO_SOURCE_SIZE, f'{label}.geoms.fixed',
                             meta={'count': count, 'recordBytes': PHYS_GEOM_INFO_SOURCE_SIZE,
                                   'nativeDestinationAlignment': 16})
            for i in range(count):
                b = a + i * PHYS_GEOM_INFO_SOURCE_SIZE
                brush_ptr = self.u32at(b, 0)
                typ = self.i32at(b, 4)
                row = {
                    'index': i,
                    'brushPointer': ptr_kind(brush_ptr),
                    'type': typ,
                    'orientation': [self._finite3(b + 8 + 12 * k) for k in range(3)],
                    'offset': self._finite3(b + 44),
                    'halfLengths': self._finite3(b + 56),
                }
                if is_inline(brush_ptr):
                    row['brush'] = self.walk_brush_wrapper(f'{label}.geoms[{i}].brush')
                geoms.append(row)
        return {'count': count, 'geomsPointer': ptr_kind(geoms_ptr), 'contents': contents, 'geoms': geoms}

    def walk_phys_constraints_asset(self, label: str) -> None:
        # Fixed size/strings are known, but the nested material-pointer behavior
        # has not yet been retail-boundary validated for this asset class.
        self.blockers.append({
            'kind': 'inline_PhysConstraints_dispatch_not_yet_retail_closed',
            'field': label,
            'fixedRecordBytesExpected': PHYS_CONSTRAINTS_SIZE,
        })

    def external_asset_ref(self, field, ptr, owner_index=None, asset_type=None):
        if not is_inline(ptr):
            return
        if asset_type == 'PhysConstraints':
            return self.walk_phys_constraints_asset(field)
        return super().external_asset_ref(field, ptr, owner_index, asset_type)

    def walk_xmodel(self) -> dict:
        fixed_start = self.pos
        base, _ = self.take(XMODEL_SIZE, 'XModel.fixed')
        name_ptr = self.u32at(base, 0)
        num_bones = self.data[base + 4]
        num_root_bones = self.data[base + 5]
        num_surfs = self.data[base + 6]
        lod_ramp_type = self.data[base + 7]
        if num_root_bones > num_bones:
            raise WalkError(f'XModel: numRootBones {num_root_bones} > numBones {num_bones}')
        non_root = num_bones - num_root_bones

        bone_names_ptr = self.u32at(base, 8)
        parent_list_ptr = self.u32at(base, 12)
        quats_ptr = self.u32at(base, 16)
        trans_ptr = self.u32at(base, 20)
        part_class_ptr = self.u32at(base, 24)
        base_mat_ptr = self.u32at(base, 28)
        surfs_ptr = self.u32at(base, 32)
        material_handles_ptr = self.u32at(base, 36)
        coll_surfs_ptr = self.u32at(base, 152)
        num_coll_surfs = self._nonnegative(self.i32at(base, 156), 'numCollSurfs')
        contents = self.i32at(base, 160)
        bone_info_ptr = self.u32at(base, 164)
        radius = struct.unpack_from('<f', self.data, base + 168)[0]
        mins = self._finite3(base + 172)
        maxs = self._finite3(base + 184)
        num_lods = self.u16at(base, 196)
        coll_lod = self.i16at(base, 198)
        himip_ptr = self.u32at(base, 200)
        mem_usage = self.i32at(base, 204)
        flags = self.u32at(base, 208)
        bad = self.data[base + 212]
        phys_preset_ptr = self.u32at(base, 216)
        num_collmaps = self.data[base + 220]
        collmaps_ptr = self.u32at(base, 224)
        phys_constraints_ptr = self.u32at(base, 228)

        name = self.walk_string_ptr(name_ptr, 'XModel.name')
        if is_inline(bone_names_ptr):
            self.take(num_bones * 2, 'XModel.boneNames', meta={'count': num_bones, 'recordBytes': 2})
        if is_inline(parent_list_ptr):
            self.take(non_root, 'XModel.parentList', meta={'count': non_root, 'recordBytes': 1})
        if is_inline(quats_ptr):
            self.take(non_root * XMODEL_QUAT_SIZE, 'XModel.quats', meta={'count': non_root, 'recordBytes': XMODEL_QUAT_SIZE})
        if is_inline(trans_ptr):
            self.take(non_root * 16, 'XModel.trans', meta={'count': non_root * 4, 'recordBytes': 4})
        if is_inline(part_class_ptr):
            self.take(num_bones, 'XModel.partClassification', meta={'count': num_bones, 'recordBytes': 1})
        if is_inline(base_mat_ptr):
            self.take(num_bones * DOBJ_ANIM_MAT_SIZE, 'XModel.baseMat', meta={'count': num_bones, 'recordBytes': DOBJ_ANIM_MAT_SIZE})

        surfaces = []
        if is_inline(surfs_ptr):
            a, _ = self.take(num_surfs * XSURFACE_SIZE, 'XModel.surfs.fixed',
                             meta={'count': num_surfs, 'recordBytes': XSURFACE_SIZE})
            for i in range(num_surfs):
                surfaces.append(self.walk_xsurface(a + i * XSURFACE_SIZE, i))

        material_handles = []
        if is_inline(material_handles_ptr):
            a, _ = self.take(num_surfs * 4, 'XModel.materialHandles.fixed',
                             meta={'count': num_surfs, 'recordBytes': 4})
            for i in range(num_surfs):
                p = self.u32at(a + i * 4, 0)
                material_handles.append(ptr_kind(p))
                self.external_asset_ref(f'XModel.materialHandles[{i}]', p, i, asset_type='Material')

        coll_surfs = []
        if is_inline(coll_surfs_ptr):
            a, _ = self.take(num_coll_surfs * XMODEL_COLL_SURF_SIZE, 'XModel.collSurfs.fixed',
                             meta={'count': num_coll_surfs, 'recordBytes': XMODEL_COLL_SURF_SIZE})
            for i in range(num_coll_surfs):
                b = a + i * XMODEL_COLL_SURF_SIZE
                tris_ptr = self.u32at(b, 0)
                ntris = self._nonnegative(self.i32at(b, 4), f'collSurfs[{i}].numCollTris')
                row = {
                    'index': i,
                    'collTrisPointer': ptr_kind(tris_ptr),
                    'numCollTris': ntris,
                    'mins': self._finite3(b + 8),
                    'maxs': self._finite3(b + 20),
                    'boneIdx': self.i32at(b, 32),
                    'contents': self.i32at(b, 36),
                    'surfFlags': self.i32at(b, 40),
                }
                if is_inline(tris_ptr):
                    self.take(ntris * XMODEL_COLL_TRI_SIZE, f'XModel.collSurfs[{i}].collTris',
                              meta={'count': ntris, 'recordBytes': XMODEL_COLL_TRI_SIZE})
                coll_surfs.append(row)

        if is_inline(bone_info_ptr):
            self.take(num_bones * XBONE_INFO_SIZE, 'XModel.boneInfo',
                      meta={'count': num_bones, 'recordBytes': XBONE_INFO_SIZE})
        if is_inline(himip_ptr):
            self.take(num_surfs * 4, 'XModel.himipInvSqRadii',
                      meta={'count': num_surfs, 'recordBytes': 4})

        self.external_asset_ref('XModel.physPreset', phys_preset_ptr, asset_type='PhysPreset')

        collmaps = []
        if is_inline(collmaps_ptr):
            a, _ = self.take(num_collmaps * COLLMAP_SIZE, 'XModel.collmaps.fixed',
                             meta={'count': num_collmaps, 'recordBytes': COLLMAP_SIZE})
            for i in range(num_collmaps):
                gp = self.u32at(a + i * COLLMAP_SIZE, 0)
                row = {'index': i, 'geomListPointer': ptr_kind(gp)}
                if is_inline(gp):
                    row['geomList'] = self.walk_phys_geom_list(f'XModel.collmaps[{i}].geomList')
                collmaps.append(row)

        self.external_asset_ref('XModel.physConstraints', phys_constraints_ptr, asset_type='PhysConstraints')

        result = {
            'format': 't6-xmodel-serialized-walk-v1',
            'assetFixedStart': fixed_start,
            'assetSerializedEnd': self.pos,
            'assetSerializedBytes': self.pos - fixed_start,
            'assetSerializedSha256': hashlib.sha256(self.data[fixed_start:self.pos]).hexdigest(),
            'xmodel': {
                'name': name,
                'namePointer': ptr_kind(name_ptr),
                'numBones': num_bones,
                'numRootBones': num_root_bones,
                'numSurfs': num_surfs,
                'lodRampType': lod_ramp_type,
                'numLods': num_lods,
                'collLod': coll_lod,
                'numCollSurfs': num_coll_surfs,
                'contents': contents,
                'radius': radius,
                'mins': mins,
                'maxs': maxs,
                'memUsage': mem_usage,
                'flags': flags,
                'bad': bool(bad),
                'numCollmaps': num_collmaps,
                'physPresetPointer': ptr_kind(phys_preset_ptr),
                'physConstraintsPointer': ptr_kind(phys_constraints_ptr),
                'surfaces': surfaces,
                'materialHandles': material_handles,
                'collisionSurfaces': coll_surfs,
                'collmaps': collmaps,
            },
            'sections': self.sections,
            'details': self.details,
            'blockers': self.blockers,
            'sourceStrideRules': {
                'XSurfaceTri16': {'serializedRecordBytes': XSURFACE_TRI_SOURCE_SIZE, 'nativeDestinationAlignment': 16},
                'PhysGeomInfo16': {'serializedRecordBytes': PHYS_GEOM_INFO_SOURCE_SIZE, 'nativeDestinationAlignment': 16},
                'sourceAlignmentPaddingBytes': 0,
            },
        }
        return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path, help='decrypted/decompressed T6 XFile byte stream')
    ap.add_argument('--asset-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--expect-end', type=lambda x: int(x, 0))
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    result = XModelWalker(data, args.asset_start).walk_xmodel()
    result['expandedBytes'] = len(data)
    result['expandedSha256'] = hashlib.sha256(data).hexdigest()
    if args.expect_end is not None:
        result['expectedEnd'] = args.expect_end
        result['expectedEndMatches'] = result['assetSerializedEnd'] == args.expect_end
        if not result['expectedEndMatches']:
            raise SystemExit(f"walk ended at {result['assetSerializedEnd']}, expected {args.expect_end}; blockers={result['blockers']}")
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + '\n', encoding='utf-8')
    else:
        print(text)
    if result['blockers']:
        raise SystemExit(f"walk completed with blockers: {result['blockers']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
