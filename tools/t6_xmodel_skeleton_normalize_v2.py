#!/usr/bin/env python3
"""Lossless T6 XModel skeleton normalizer v2 with reusable-owner resolution.

Extends v1 by resolving packed VIRTUAL skeleton arrays.  A reusable owner is
accepted only when a unique earlier top-level XModel with inline skeleton data
replays the alias's native VIRTUAL allocation signature exactly.  The replay
uses the target's own packed boneNames address as its logical base and compares
all available packed skeleton and XSurface nested pointers.

No model-name matching or map-specific logical/source offsets are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from t6_clipmap_serialized_walker import PTR_FOLLOWING, PTR_INSERT, ptr_kind
from t6_clipmap_normalize_v5 import parse_top_level_xasset_table
from t6_clipmap_normalize_v6 import walk_map_prefix_stringtable, scan_required_xmodels
from t6_xmodel_serialized_walker import XModelWalker, XSURFACE_SIZE
from t6_xmodel_skeleton_normalize_v1 import parse_script_strings, INT16_MAX

ASSET_TYPE_XMODEL = 5


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _align(v: int, a: int) -> int:
    return (v + (a - 1)) & ~(a - 1)


def _is_inline(raw: int) -> bool:
    return raw in (PTR_FOLLOWING, PTR_INSERT)


def _packed_virtual_offset(raw: int) -> int | None:
    p = ptr_kind(raw)
    if p['kind'] == 'packed' and p.get('block') == 5:
        return int(p['offset'])
    return None


def _sections_by_name(walk: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for s in walk['sections']:
        out.setdefault(s['name'], []).append(s)
    return out


def _one(sections: dict[str, list[dict]], name: str, required=True):
    rows = sections.get(name, [])
    if not rows:
        if required:
            raise ValueError(f'missing section {name}')
        return None
    if len(rows) != 1:
        raise ValueError(f'ambiguous section {name}: {len(rows)}')
    return rows[0]


def _finite(vals, label: str):
    vals = [float(x) for x in vals]
    if not all(math.isfinite(x) for x in vals):
        raise ValueError(f'{label}: non-finite float')
    return vals


def _read_surface_fixed(data: bytes, start: int, count: int) -> list[dict]:
    rows = []
    for i in range(count):
        b = start + i * XSURFACE_SIZE
        blends = [struct.unpack_from('<h', data, b + 16 + j * 2)[0] for j in range(4)]
        if any(x < 0 for x in blends):
            raise ValueError(f'surface {i}: negative blend count')
        rows.append({
            'index': i,
            'tileMode': data[b],
            'vertListCount': data[b + 1],
            'flags': _u16(data, b + 2),
            'vertCount': _u16(data, b + 4),
            'triCount': _u16(data, b + 6),
            'baseVertIndex': _u16(data, b + 8),
            'triIndicesRaw': _u32(data, b + 12),
            'blendCounts': blends,
            'vertsBlendRaw': _u32(data, b + 24),
            'tensionRaw': _u32(data, b + 28),
            'verts0Raw': _u32(data, b + 32),
            'vertListRaw': _u32(data, b + 40),
            'fixedSourceStart': b,
        })
    return rows


def _surface_scalar_signature(s: dict) -> tuple:
    return (s['tileMode'], s['vertListCount'], s['flags'], s['vertCount'], s['triCount'], s['baseVertIndex'], tuple(s['blendCounts']))


def _alloc(cur: int, align: int, size: int) -> tuple[int, int]:
    start = _align(cur, align)
    return start, start + size


def _record_comparison(comparisons: list, field: str, target_raw: int, predicted: int) -> bool:
    actual = _packed_virtual_offset(target_raw)
    if actual is None:
        return True
    ok = actual == predicted
    comparisons.append({'field': field, 'predictedOffset': predicted, 'actualOffset': actual, 'match': ok})
    return ok


def replay_owner_signature(data: bytes, owner_start: int, target_start: int) -> dict | None:
    """Replay an inline owner's VIRTUAL allocations against one packed alias."""
    tw = XModelWalker(data, target_start).walk_xmodel()
    ow = XModelWalker(data, owner_start).walk_xmodel()
    if tw['blockers'] or ow['blockers']:
        return None
    tx, ox = tw['xmodel'], ow['xmodel']
    if (tx['numBones'], tx['numRootBones'], tx['numSurfs']) != (ox['numBones'], ox['numRootBones'], ox['numSurfs']):
        return None
    n, roots, ns = tx['numBones'], tx['numRootBones'], tx['numSurfs']
    nr = n - roots
    ts = _sections_by_name(tw)
    os = _sections_by_name(ow)
    required = ['XModel.boneNames', 'XModel.partClassification', 'XModel.baseMat', 'XModel.surfs.fixed']
    if nr:
        required += ['XModel.parentList', 'XModel.quats', 'XModel.trans']
    if any(_one(os, k, False) is None for k in required):
        return None
    tfix = _one(ts, 'XModel.fixed')['start']
    raw_fields = {
        'boneNames': _u32(data, tfix + 8), 'parentList': _u32(data, tfix + 12),
        'quats': _u32(data, tfix + 16), 'trans': _u32(data, tfix + 20),
        'partClassification': _u32(data, tfix + 24), 'baseMat': _u32(data, tfix + 28),
    }
    base = _packed_virtual_offset(raw_fields['boneNames'])
    if base is None:
        return None
    comparisons = []
    cur = base
    for field, align, size in [
        ('boneNames', 2, n * 2), ('parentList', 1, nr), ('quats', 2, nr * 8),
        ('trans', 4, nr * 16), ('partClassification', 1, n), ('baseMat', 4, n * 32),
    ]:
        if size == 0:
            continue
        start, cur = _alloc(cur, align, size)
        if not _record_comparison(comparisons, f'XModel.{field}', raw_fields[field], start):
            return None
    _, cur = _alloc(cur, 16, ns * 80)

    osurf_sec = _one(os, 'XModel.surfs.fixed')
    tsurf_sec = _one(ts, 'XModel.surfs.fixed')
    owner_surfs = _read_surface_fixed(data, osurf_sec['start'], ns)
    target_surfs = _read_surface_fixed(data, tsurf_sec['start'], ns)
    for i, (o, t) in enumerate(zip(owner_surfs, target_surfs)):
        if _surface_scalar_signature(o) != _surface_scalar_signature(t):
            return None
        blend_total = o['blendCounts'][0] + 3*o['blendCounts'][1] + 5*o['blendCounts'][2] + 7*o['blendCounts'][3]
        tension_total = sum(o['blendCounts'])
        if _is_inline(o['vertsBlendRaw']):
            start, cur = _alloc(cur, 2, blend_total * 2)
            if not _record_comparison(comparisons, f'surfs[{i}].vertsBlend', t['vertsBlendRaw'], start): return None
        elif _packed_virtual_offset(t['vertsBlendRaw']) is not None:
            return None
        if _is_inline(o['tensionRaw']):
            start, cur = _alloc(cur, 4, tension_total * 4)
            if not _record_comparison(comparisons, f'surfs[{i}].tensionData', t['tensionRaw'], start): return None
        elif _packed_virtual_offset(t['tensionRaw']) is not None:
            return None
        if not (o['flags'] & 1) and _is_inline(o['verts0Raw']):
            start, cur = _alloc(cur, 16, o['vertCount'] * 32)
            if not _record_comparison(comparisons, f'surfs[{i}].verts0', t['verts0Raw'], start): return None
        elif _packed_virtual_offset(t['verts0Raw']) is not None:
            return None
        if _is_inline(o['vertListRaw']):
            start, cur = _alloc(cur, 4, o['vertListCount'] * 12)
            if not _record_comparison(comparisons, f'surfs[{i}].vertList', t['vertListRaw'], start): return None
            orows = ox['surfaces'][i].get('rigidVertLists', [])
            for r in orows:
                cp = r['collisionTreePointer']
                if cp['kind'] in ('following', 'insert'):
                    _, cur = _alloc(cur, 4, 40)
                    tree = r.get('collisionTree')
                    if tree is None: return None
                    if tree['nodesPointer']['kind'] in ('following', 'insert'):
                        _, cur = _alloc(cur, 16, int(tree['nodeCount']) * 16)
                    if tree['leafsPointer']['kind'] in ('following', 'insert'):
                        _, cur = _alloc(cur, 2, int(tree['leafCount']) * 2)
        elif _packed_virtual_offset(t['vertListRaw']) is not None:
            return None
        if _is_inline(o['triIndicesRaw']):
            start, cur = _alloc(cur, 16, o['triCount'] * 6)
            if not _record_comparison(comparisons, f'surfs[{i}].triIndices', t['triIndicesRaw'], start): return None
        elif _packed_virtual_offset(t['triIndicesRaw']) is not None:
            return None
    surface_matches = [c for c in comparisons if c['field'].startswith('surfs[')]
    if not surface_matches:
        return None
    return {
        'ownerFixedStart': owner_start, 'targetFixedStart': target_start,
        'virtualReplayBase': base, 'comparisonCount': len(comparisons),
        'surfaceComparisonCount': len(surface_matches), 'comparisons': comparisons,
        'allMatch': all(c['match'] for c in comparisons), 'ownerWalk': ow, 'targetWalk': tw,
    }


def build_xmodel_catalog(data: bytes, max_asset_index: int) -> dict[int, dict]:
    table = parse_top_level_xasset_table(data)
    entries = table['entries']
    if max_asset_index >= len(entries):
        raise ValueError('max asset index outside XAsset table')
    indices = [i for i, e in enumerate(entries) if e['type'] == ASSET_TYPE_XMODEL and i <= max_asset_index]
    prefix = walk_map_prefix_stringtable(data, table)
    records = scan_required_xmodels(data, prefix['sourceEnd'], len(indices), prefix['logicalToText'])
    if len(records) != len(indices):
        raise ValueError('XModel catalog cardinality mismatch')
    return {idx: dict(rec, assetIndex=idx) for idx, rec in zip(indices, records)}


def resolve_reusable_owner(data: bytes, target_start: int, target_asset_index: int) -> dict:
    catalog = build_xmodel_catalog(data, target_asset_index)
    matches = []
    for idx in sorted(catalog):
        if idx >= target_asset_index:
            break
        rec = catalog[idx]
        try:
            proof = replay_owner_signature(data, rec['fixedSourceStart'], target_start)
        except Exception:
            proof = None
        if proof:
            proof['ownerAssetIndex'] = idx
            proof['ownerName'] = rec['name']
            matches.append(proof)
    if len(matches) != 1:
        slim = [{'assetIndex': m['ownerAssetIndex'], 'name': m['ownerName'], 'comparisons': m['comparisonCount']} for m in matches]
        raise ValueError(f'reusable skeleton owner is not unique: {slim}')
    return matches[0]


def _skeleton_section_sources(target_walk: dict, owner_proof: dict | None) -> tuple[dict[str, dict], dict]:
    target_sections = _sections_by_name(target_walk)
    names = ['XModel.boneNames','XModel.parentList','XModel.quats','XModel.trans','XModel.partClassification','XModel.baseMat']
    if owner_proof is None:
        return {k: _one(target_sections, k, False) for k in names}, {'mode':'inline_owned','owner':None}
    owner_sections = _sections_by_name(owner_proof['ownerWalk'])
    src = {k: _one(owner_sections, k, False) for k in names}
    return src, {
        'mode':'packed_reusable_owner',
        'owner': {'xassetIndex': owner_proof['ownerAssetIndex'], 'name': owner_proof['ownerName'], 'fixedSourceStart': owner_proof['ownerFixedStart']},
        'virtualReplayBase': owner_proof['virtualReplayBase'], 'comparisonCount': owner_proof['comparisonCount'],
        'surfaceComparisonCount': owner_proof['surfaceComparisonCount'], 'comparisons': owner_proof['comparisons'],
    }


def normalize_skeleton(data: bytes, asset_start: int, *, xasset_index: int | None = None, identity_name: str | None = None) -> dict:
    walk = XModelWalker(data, asset_start).walk_xmodel()
    if walk['blockers']:
        raise ValueError(f'XModel walk has blockers: {walk["blockers"]}')
    x = walk['xmodel']; n, roots = int(x['numBones']), int(x['numRootBones']); nr = n - roots
    fix = _one(_sections_by_name(walk), 'XModel.fixed')['start']
    owner_proof = None
    if _packed_virtual_offset(_u32(data, fix + 8)) is not None:
        if xasset_index is None:
            raise ValueError('packed reusable skeleton requires --xasset-index for unique owner resolution')
        owner_proof = resolve_reusable_owner(data, asset_start, xasset_index)
    src, provenance = _skeleton_section_sources(walk, owner_proof)
    required = ['XModel.boneNames','XModel.partClassification','XModel.baseMat'] + (['XModel.parentList','XModel.quats','XModel.trans'] if nr else [])
    if any(src[k] is None for k in required):
        raise ValueError('skeleton source arrays unresolved')

    scripts = parse_script_strings(data)
    bone_ids = list(struct.unpack_from(f'<{n}H', data, src['XModel.boneNames']['start'])) if n else []
    parent_raw = list(data[src['XModel.parentList']['start']:src['XModel.parentList']['end']]) if nr else []
    quat_raw = [list(struct.unpack_from('<4h', data, src['XModel.quats']['start'] + i*8)) for i in range(nr)] if nr else []
    quat_float = [[v/INT16_MAX for v in q] for q in quat_raw]
    serialized_trans = list(struct.unpack_from(f'<{nr*4}f', data, src['XModel.trans']['start'])) if nr else []
    semantic_trans = serialized_trans[:nr*3]; allocation_tail = serialized_trans[nr*3:]
    if len(allocation_tail) != nr: raise ValueError('translation tail length mismatch')
    local_trans = [semantic_trans[i*3:i*3+3] for i in range(nr)]
    classes = list(data[src['XModel.partClassification']['start']:src['XModel.partClassification']['end']]) if n else []
    base_mats=[]
    for i in range(n):
        off=src['XModel.baseMat']['start']+i*32
        base_mats.append({'quat':_finite(struct.unpack_from('<4f',data,off),f'base[{i}].quat'),'trans':_finite(struct.unpack_from('<3f',data,off+16),f'base[{i}].trans'),'transWeight':struct.unpack_from('<f',data,off+28)[0]})
    invalid_sid=[]; invalid_parent=[]; bones=[]
    for i in range(n):
        sid=bone_ids[i]; name=scripts['strings'][sid] if sid < scripts['count'] else None
        if sid>=scripts['count']: invalid_sid.append({'boneIndex':i,'scriptStringId':sid})
        if i<roots:
            pd=None; pi=None; qr=None; q=[0.,0.,0.,1.]; tr=[0.,0.,0.]
        else:
            j=i-roots; pd=parent_raw[j]; pi=i-pd; qr=quat_raw[j]; q=quat_float[j]; tr=_finite(local_trans[j],f'bone[{i}].trans')
            if not (0 <= pi < i): invalid_parent.append({'boneIndex':i,'parentDelta':pd,'parentIndex':pi})
        bones.append({'index':i,'scriptStringId':sid,'name':name,'parentIndex':pi,'parentDeltaRaw':pd,'partClassificationRaw':classes[i],'localRotationInt16':qr,'localRotation':q,'localTranslation':tr,'globalBaseMat':base_mats[i]})
    nonzero=[i for i,v in enumerate(allocation_tail) if v != 0.0]
    return {
        'format':'t6-xmodel-skeleton-normalized-v2',
        'source':{'expandedSha256':hashlib.sha256(data).hexdigest(),'xmodelFixedStart':asset_start,'xmodelSerializedEnd':walk['assetSerializedEnd'],'xmodelSerializedBytes':walk['assetSerializedBytes'],'xmodelSerializedSha256':walk['assetSerializedSha256']},
        'identity':{'xassetIndex':xasset_index,'name':identity_name if identity_name is not None else x['name'],'serializedName':x['name'],'namePointer':x['namePointer']},
        'skeletonSource':provenance,
        'scriptStringTable':{'count':scripts['count'],'nullIndices':scripts['nullIndices'],'serializedEnd':scripts['serializedEnd']},
        'skeleton':{'numBones':n,'numRootBones':roots,'nonRootBoneCount':nr,'bones':bones,'rawParentList':parent_raw,'rawQuaternionsInt16':quat_raw,'serializedTranslationFloatCount':len(serialized_trans),'semanticTranslationFloatCount':len(semantic_trans),'serializedTranslationFloats':serialized_trans,'allocationTailFloats':allocation_tail,'allocationTailAllZero':not nonzero,'allocationTailNonZeroIndices':nonzero,'partClassificationRaw':classes},
        'validation':{'invalidScriptStringIds':invalid_sid,'invalidParents':invalid_parent,'allBoneNamesResolved':not invalid_sid and all(b['name'] is not None for b in bones),'hierarchyValid':not invalid_parent,'translationAllocationRule':{'serializedFloatsPerNonRootBone':4,'semanticFloatsPerNonRootBone':3,'allocationTailFloats':nr,'tailAllZeroInThisFixture':not nonzero},'quatConversion':'int16 / 32767.0','parentRule':'parentIndex = boneIndex - parentList[boneIndex - numRootBones]'}
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('expanded',type=Path); ap.add_argument('--asset-start',type=lambda x:int(x,0),required=True); ap.add_argument('--xasset-index',type=int); ap.add_argument('--name'); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    data=a.expanded.read_bytes(); out=normalize_skeleton(data,a.asset_start,xasset_index=a.xasset_index,identity_name=a.name); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,separators=(',',':'))+'\n',encoding='utf-8'); raw=a.out.read_bytes(); print(json.dumps({'out':str(a.out),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'identity':out['identity'],'numBones':out['skeleton']['numBones'],'allBoneNamesResolved':out['validation']['allBoneNamesResolved'],'hierarchyValid':out['validation']['hierarchyValid'],'skeletonSource':out['skeletonSource']['mode']},indent=2))
if __name__=='__main__': main()
