#!/usr/bin/env python3
"""Normalize native T6 XModel skeleton data losslessly.

Source-derived semantics:
- boneNames are uint16 ScriptString ids into the zone ScriptStringList.
- for non-root bone b: parentIndex = b - parentList[b - numRootBones].
- XModelQuat int16 components convert as component / INT16_MAX (32767).
- non-root local translations consume 3 floats per semantic bone, while retail
  T6 serializes a 4-float allocation per non-root. The trailing allocation tail
  is preserved verbatim.
- baseMat is the native global DObjAnimMat (quat, trans, transWeight) per bone.

No hierarchy transform is reconstructed by guesswork: native local and global
representations are both retained, alongside all raw packed values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from t6_clipmap_serialized_walker import PTR_FOLLOWING, ptr_kind
from t6_xmodel_serialized_walker import XModelWalker

INT16_MAX = 32767.0
XASSETLIST_RAW_START = 40


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _one(sections: dict[str, list[dict]], name: str, required: bool = True) -> dict | None:
    rows = sections.get(name, [])
    if not rows:
        if required:
            raise ValueError(f'missing section {name}')
        return None
    if len(rows) != 1:
        raise ValueError(f'ambiguous section {name}: {len(rows)}')
    return rows[0]


def parse_script_strings(data: bytes) -> dict:
    p = XASSETLIST_RAW_START
    count = _u32(data, p)
    ptr = _u32(data, p + 4)
    if ptr != PTR_FOLLOWING:
        raise ValueError(f'ScriptStringList pointer must be FOLLOWING, got {ptr_kind(ptr)}')
    cur = p + 24
    if cur + count * 4 > len(data):
        raise ValueError('truncated ScriptString pointer table')
    raw_ptrs = struct.unpack_from(f'<{count}I', data, cur) if count else ()
    table_start = cur
    cur += count * 4
    strings: list[str | None] = []
    for i, raw in enumerate(raw_ptrs):
        kind = ptr_kind(raw)['kind']
        if kind == 'null':
            strings.append(None)
        elif kind == 'following':
            end = data.find(b'\0', cur)
            if end < 0:
                raise ValueError(f'unterminated ScriptString {i} at {cur}')
            strings.append(data[cur:end].decode('latin1'))
            cur = end + 1
        else:
            raise ValueError(f'ScriptString {i}: unsupported serialized pointer {ptr_kind(raw)}')
    return {
        'count': count,
        'pointerTableStart': table_start,
        'pointerTableEnd': table_start + count * 4,
        'serializedEnd': cur,
        'strings': strings,
        'nullIndices': [i for i, s in enumerate(strings) if s is None],
    }


def _finite(vals, label: str) -> list[float]:
    out = [float(v) for v in vals]
    if not all(math.isfinite(v) for v in out):
        raise ValueError(f'{label}: non-finite float')
    return out


def normalize_skeleton(data: bytes, asset_start: int, *, xasset_index: int | None = None, identity_name: str | None = None) -> dict:
    walk = XModelWalker(data, asset_start).walk_xmodel()
    if walk['blockers']:
        raise ValueError(f'XModel walk has blockers: {walk["blockers"]}')
    sections: dict[str, list[dict]] = {}
    for sec in walk['sections']:
        sections.setdefault(sec['name'], []).append(sec)

    x = walk['xmodel']
    n = int(x['numBones'])
    roots = int(x['numRootBones'])
    if roots > n:
        raise ValueError('numRootBones > numBones')
    non_root = n - roots
    scripts = parse_script_strings(data)

    bone_sec = _one(sections, 'XModel.boneNames', required=(n > 0))
    parent_sec = _one(sections, 'XModel.parentList', required=(non_root > 0))
    quat_sec = _one(sections, 'XModel.quats', required=(non_root > 0))
    trans_sec = _one(sections, 'XModel.trans', required=(non_root > 0))
    class_sec = _one(sections, 'XModel.partClassification', required=(n > 0))
    base_sec = _one(sections, 'XModel.baseMat', required=(n > 0))

    bone_ids = list(struct.unpack_from(f'<{n}H', data, bone_sec['start'])) if n else []
    parent_raw = list(data[parent_sec['start']:parent_sec['end']]) if non_root else []
    if len(parent_raw) != non_root:
        raise ValueError('parentList count mismatch')
    quat_raw = [list(struct.unpack_from('<4h', data, quat_sec['start'] + i * 8)) for i in range(non_root)] if non_root else []
    quat_float = [[v / INT16_MAX for v in q] for q in quat_raw]

    serialized_trans = list(struct.unpack_from(f'<{non_root * 4}f', data, trans_sec['start'])) if non_root else []
    semantic_trans = serialized_trans[:non_root * 3]
    allocation_tail = serialized_trans[non_root * 3:]
    if len(allocation_tail) != non_root:
        raise ValueError('T6 translation allocation-tail size mismatch')
    local_trans = [semantic_trans[i * 3:i * 3 + 3] for i in range(non_root)]
    classes = list(data[class_sec['start']:class_sec['end']]) if n else []
    if len(classes) != n:
        raise ValueError('partClassification count mismatch')

    base_mats = []
    for i in range(n):
        off = base_sec['start'] + i * 32
        quat = _finite(struct.unpack_from('<4f', data, off), f'baseMat[{i}].quat')
        trans = _finite(struct.unpack_from('<3f', data, off + 16), f'baseMat[{i}].trans')
        trans_weight = struct.unpack_from('<f', data, off + 28)[0]
        if not math.isfinite(trans_weight):
            raise ValueError(f'baseMat[{i}].transWeight non-finite')
        base_mats.append({'quat': quat, 'trans': trans, 'transWeight': trans_weight})

    bones = []
    invalid_script_ids = []
    invalid_parents = []
    for i in range(n):
        sid = bone_ids[i]
        if sid >= scripts['count']:
            name = None
            invalid_script_ids.append({'boneIndex': i, 'scriptStringId': sid})
        else:
            name = scripts['strings'][sid]
        if i < roots:
            parent_index = None
            parent_delta = None
            local_q_raw = None
            local_q = [0.0, 0.0, 0.0, 1.0]
            local_t = [0.0, 0.0, 0.0]
        else:
            j = i - roots
            parent_delta = parent_raw[j]
            parent_index = i - parent_delta
            if not (0 <= parent_index < i):
                invalid_parents.append({'boneIndex': i, 'parentDelta': parent_delta, 'parentIndex': parent_index})
            local_q_raw = quat_raw[j]
            local_q = quat_float[j]
            local_t = _finite(local_trans[j], f'bone[{i}].localTranslation')
        bones.append({
            'index': i,
            'scriptStringId': sid,
            'name': name,
            'parentIndex': parent_index,
            'parentDeltaRaw': parent_delta,
            'partClassificationRaw': classes[i],
            'localRotationInt16': local_q_raw,
            'localRotation': local_q,
            'localTranslation': local_t,
            'globalBaseMat': base_mats[i],
        })

    # Retail evidence shows the serializer allocation tail is zero-filled. Do
    # not require this for decoding, but expose it as a strict validation fact.
    tail_nonzero = [i for i, v in enumerate(allocation_tail) if v != 0.0]

    result = {
        'format': 't6-xmodel-skeleton-normalized-v1',
        'source': {
            'expandedSha256': hashlib.sha256(data).hexdigest(),
            'xmodelFixedStart': asset_start,
            'xmodelSerializedEnd': walk['assetSerializedEnd'],
            'xmodelSerializedBytes': walk['assetSerializedBytes'],
            'xmodelSerializedSha256': walk['assetSerializedSha256'],
        },
        'identity': {
            'xassetIndex': xasset_index,
            'name': identity_name if identity_name is not None else x['name'],
            'serializedName': x['name'],
            'namePointer': x['namePointer'],
        },
        'scriptStringTable': {
            'count': scripts['count'],
            'nullIndices': scripts['nullIndices'],
            'serializedEnd': scripts['serializedEnd'],
        },
        'skeleton': {
            'numBones': n,
            'numRootBones': roots,
            'nonRootBoneCount': non_root,
            'bones': bones,
            'rawParentList': parent_raw,
            'rawQuaternionsInt16': quat_raw,
            'serializedTranslationFloatCount': len(serialized_trans),
            'semanticTranslationFloatCount': len(semantic_trans),
            'serializedTranslationFloats': serialized_trans,
            'allocationTailFloats': allocation_tail,
            'allocationTailAllZero': not tail_nonzero,
            'allocationTailNonZeroIndices': tail_nonzero,
            'partClassificationRaw': classes,
        },
        'validation': {
            'invalidScriptStringIds': invalid_script_ids,
            'invalidParents': invalid_parents,
            'allBoneNamesResolved': not invalid_script_ids and all(b['name'] is not None for b in bones),
            'hierarchyValid': not invalid_parents,
            'translationAllocationRule': {
                'serializedFloatsPerNonRootBone': 4,
                'semanticFloatsPerNonRootBone': 3,
                'allocationTailFloats': non_root,
                'tailAllZeroInThisFixture': not tail_nonzero,
            },
            'quatConversion': 'int16 / 32767.0 (QuatInt16::ToFloat)',
            'parentRule': 'parentIndex = boneIndex - parentList[boneIndex - numRootBones]',
        },
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--asset-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--xasset-index', type=int)
    ap.add_argument('--name')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    out = normalize_skeleton(data, args.asset_start, xasset_index=args.xasset_index, identity_name=args.name)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
    raw = args.out.read_bytes()
    print(json.dumps({
        'out': str(args.out),
        'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'identity': out['identity'],
        'numBones': out['skeleton']['numBones'],
        'numRootBones': out['skeleton']['numRootBones'],
        'allBoneNamesResolved': out['validation']['allBoneNamesResolved'],
        'hierarchyValid': out['validation']['hierarchyValid'],
        'translationAllocationTailAllZero': out['skeleton']['allocationTailAllZero'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
