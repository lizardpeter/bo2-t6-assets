#!/usr/bin/env python3
"""Close current-R2 MP7 SEAL6 visible-viewhands mesh/local-rig data.

This layer intentionally separates two facts:
1. The physical visible XModels, skeleton arrays, render meshes, skin weights,
   and their local bind transforms can be closed directly from retail bytes.
2. Multi-XModel DObj assembly semantics remain separate when a shared bone has
   a different authored parent in the generic carrier versus the visible model.

Authority chain:
- exact SHA-pinned current-R2 common_mp for the generic 70-bone carrier;
- exact SHA-pinned faction_seals_mp, whose physical ownership of both visible
  SEAL6 XModels was independently established by dependency-free native OAT;
- exact inline serialized XModel identity + full XModel walker is only a locator
  inside that already-proven physical owner;
- native OAT geometry counts are independent canaries, not ownership evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from t6_xmodel_serialized_walker import XModelWalker, XMODEL_SIZE
from t6_xmodel_skeleton_normalize_v2 import normalize_skeleton
from t6_xmodel_mesh_normalize_v3 import normalize_mesh

CARRIER_START = 58906792
CARRIER_NAME = 'viewmodel_hands_no_model'
FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
TARGETS = {
    'c_usa_mp_seal6_longsleeve_viewhands': {
        'vertices': 5935, 'triangles': 9278, 'surfaces': 4, 'bones': 72,
        'nativeLod0GlbSha256': '5436069f14fa2b1d630836541c865709713c23002115f8211b45994770f2c7a5',
    },
    'c_usa_mp_seal6_shortsleeve_viewhands': {
        'vertices': 6782, 'triangles': 9592, 'surfaces': 5, 'bones': 72,
        'nativeLod0GlbSha256': '593208e7a1bc5b3691c90b59f19723fabd811e6494cc3ac4fd798f63a213703f',
    },
}
EXPECTED_VISIBLE_EXTRAS = ['tag_gasmask2', 'tag_weapon1']
EXPECTED_SHARED_PARENT_DIFFERENCES = [
    {'name': 'tag_torso', 'carrierParent': 'tag_view', 'visibleParent': 'tag_ads'},
]


def _find_exact_inline_xmodel(data: bytes, name: str) -> dict:
    needle = name.encode('ascii') + b'\0'
    occurrences = []
    p = 0
    while True:
        hit = data.find(needle, p)
        if hit < 0:
            break
        occurrences.append(hit)
        p = hit + 1
    matches = []
    for hit in occurrences:
        start = hit - XMODEL_SIZE
        if start < 0:
            continue
        if struct.unpack_from('<I', data, start)[0] not in (FOLLOWING, INSERT):
            continue
        try:
            walk = XModelWalker(data, start).walk_xmodel()
        except Exception:
            continue
        if walk.get('xmodel', {}).get('name') == name and walk.get('assetFixedStart') == start:
            matches.append(walk)
    if len(matches) != 1:
        raise ValueError(
            f'{name}: expected one exact inline serialized XModel identity in its proven physical owner; '
            f'got {len(matches)} structural matches from {len(occurrences)} literal occurrences'
        )
    return matches[0]


def _parent_name(rows: list[dict], bone: dict) -> str | None:
    pi = bone['parentIndex']
    return None if pi is None else rows[int(pi)]['name']


def _skeleton_witness(skel: dict) -> dict:
    bones = skel['skeleton']['bones']
    rows = [{
        'index': int(b['index']),
        'scriptStringId': int(b['scriptStringId']),
        'name': b['name'],
        'parentName': _parent_name(bones, b),
        'localRotationInt16': b['localRotationInt16'],
        'localTranslation': b['localTranslation'],
    } for b in bones]
    payload = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()
    return {
        'boneCount': len(rows),
        'bones': rows,
        'canonicalSha256': hashlib.sha256(payload).hexdigest(),
    }


def _shared_binding_comparison(carrier: dict, visible: dict) -> dict:
    cbones = carrier['skeleton']['bones']
    vbones = visible['skeleton']['bones']
    c = {b['name']: b for b in cbones}
    v = {b['name']: b for b in vbones}
    if len(c) != len(cbones) or len(v) != len(vbones):
        raise ValueError('duplicate bone name in XModel skeleton')
    cset, vset = set(c), set(v)
    missing = sorted(cset - vset)
    extras = sorted(vset - cset)
    rows = []
    for name in sorted(cset & vset):
        cb, vb = c[name], v[name]
        cp = _parent_name(cbones, cb)
        vp = _parent_name(vbones, vb)
        rows.append({
            'name': name,
            'carrierIndex': int(cb['index']),
            'visibleIndex': int(vb['index']),
            'carrierParent': cp,
            'visibleParent': vp,
            'parentExact': cp == vp,
            'localRotationInt16Exact': cb['localRotationInt16'] == vb['localRotationInt16'],
            'localTranslationExact': cb['localTranslation'] == vb['localTranslation'],
        })
    parent_diffs = [
        {'name': r['name'], 'carrierParent': r['carrierParent'], 'visibleParent': r['visibleParent']}
        for r in rows if not r['parentExact']
    ]
    return {
        'carrierBoneCount': len(cbones),
        'visibleBoneCount': len(vbones),
        'sharedBoneCount': len(rows),
        'missingCarrierBones': missing,
        'visibleOnlyBones': extras,
        'expectedVisibleOnlyBones': EXPECTED_VISIBLE_EXTRAS,
        'namespaceSupersetExact': not missing and extras == EXPECTED_VISIBLE_EXTRAS,
        'sharedLocalRotationExact': all(r['localRotationInt16Exact'] for r in rows),
        'sharedLocalTranslationExact': all(r['localTranslationExact'] for r in rows),
        'sharedHierarchyExact': not parent_diffs,
        'parentDifferences': parent_diffs,
        'expectedParentDifferences': EXPECTED_SHARED_PARENT_DIFFERENCES,
        'parentDifferencesMatchRetailCanary': parent_diffs == EXPECTED_SHARED_PARENT_DIFFERENCES,
        'rotationMismatchCount': sum(not r['localRotationInt16Exact'] for r in rows),
        'translationMismatchCount': sum(not r['localTranslationExact'] for r in rows),
    }


def _mesh_summary(doc: dict) -> dict:
    return {
        'meshSourceMode': doc['meshSource']['mode'],
        'surfaceCount': len(doc['surfaces']),
        'vertexCount': sum(int(s['vertCount']) for s in doc['surfaces']),
        'triangleCount': sum(int(s['triCount']) for s in doc['surfaces']),
        'unweightedVertexCount': sum(int(s['unweightedVertexCount']) for s in doc['surfaces']),
        'normalizedCanonicalSha256': hashlib.sha256(
            json.dumps(doc, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest(),
        'owner': doc['meshSource'].get('owner'),
        'comparisonCount': doc['meshSource'].get('comparisonCount', 0),
        'surfaceComparisonCount': doc['meshSource'].get('surfaceComparisonCount', 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--common-stream', type=Path, required=True)
    ap.add_argument('--faction-stream', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    common = a.common_stream.read_bytes()
    faction = a.faction_stream.read_bytes()

    out = {
        'format': 't6-mp7-r2-seal6-viewhands-mesh-closure-v1',
        'source': {
            'expandedCommonMp': {'bytes': len(common), 'sha256': hashlib.sha256(common).hexdigest()},
            'expandedFactionSealsMp': {'bytes': len(faction), 'sha256': hashlib.sha256(faction).hexdigest()},
        },
        'targets': [],
    }
    failure = None
    try:
        carrier = normalize_skeleton(common, CARRIER_START, identity_name=CARRIER_NAME)
        if carrier['identity']['name'] != CARRIER_NAME or carrier['skeleton']['numBones'] != 70:
            raise ValueError('carrier identity/bone count changed')
        out['genericCarrier'] = {
            'name': CARRIER_NAME,
            'assetFixedStart': CARRIER_START,
            'skeletonSource': carrier['skeletonSource'],
            'skeletonWitness': _skeleton_witness(carrier),
        }

        matches = {name: _find_exact_inline_xmodel(faction, name) for name in TARGETS}
        mesh_ok_all = True
        local_rig_ok_all = True
        retail_diff_ok_all = True
        for name, oracle in TARGETS.items():
            walk = matches[name]
            start = int(walk['assetFixedStart'])
            if walk.get('blockers'):
                raise ValueError(f'{name}: serialized XModel walker blockers {walk["blockers"]}')
            skel = normalize_skeleton(faction, start, identity_name=name)
            bind = _shared_binding_comparison(carrier, skel)
            mesh = normalize_mesh(faction, start, identity_name=name)
            ms = _mesh_summary(mesh)
            canary = (
                ms['surfaceCount'] == oracle['surfaces'] and
                ms['vertexCount'] == oracle['vertices'] and
                ms['triangleCount'] == oracle['triangles'] and
                ms['unweightedVertexCount'] == 0 and
                skel['skeleton']['numBones'] == oracle['bones']
            )
            local_rig_ok = (
                bind['namespaceSupersetExact'] and
                bind['sharedLocalRotationExact'] and
                bind['sharedLocalTranslationExact']
            )
            retail_diff_ok = bind['parentDifferencesMatchRetailCanary']
            row = {
                'name': name,
                'assetFixedStart': start,
                'assetSerializedEnd': walk['assetSerializedEnd'],
                'assetSerializedBytes': walk['assetSerializedBytes'],
                'assetSerializedSha256': walk['assetSerializedSha256'],
                'identityLocator': {
                    'mode': 'exact_inline_serialized_name_in_independently_proven_physical_owner',
                    'literalOccurrenceCount': faction.count(name.encode('ascii') + b'\0'),
                },
                'skeletonSource': skel['skeletonSource'],
                'skeletonWitness': _skeleton_witness(skel),
                'bindingTo70BoneCarrier': bind,
                'shared70NamespaceAndLocalBindExact': local_rig_ok,
                'nativeOracle': oracle,
                'mesh': ms,
                'nativeGeometryCanaryExact': canary,
            }
            out['targets'].append(row)
            mesh_ok_all = mesh_ok_all and canary
            local_rig_ok_all = local_rig_ok_all and local_rig_ok
            retail_diff_ok_all = retail_diff_ok_all and retail_diff_ok

        all_weighted = all(r['mesh']['unweightedVertexCount'] == 0 for r in out['targets'])
        mesh_authoritative = mesh_ok_all and all_weighted and local_rig_ok_all and retail_diff_ok_all
        out['summary'] = {
            'targetCount': len(out['targets']),
            'allNativeGeometryCanariesExact': mesh_ok_all,
            'allVerticesWeighted': all_weighted,
            'allShared70NamespaceAndLocalBindExact': local_rig_ok_all,
            'allParentDifferencesMatchRetailCanary': retail_diff_ok_all,
            'retailAuthoredSharedParentDifference': EXPECTED_SHARED_PARENT_DIFFERENCES,
            'visibleOnlyBones': EXPECTED_VISIBLE_EXTRAS,
            'meshAndLocalRigClosureAuthoritative': mesh_authoritative,
            'finalDObjAssemblySemanticsAuthoritative': False,
        }
        if not mesh_authoritative:
            failure = 'SEAL6 visible-hands mesh/local-rig closure did not close'
    except Exception as exc:
        failure = repr(exc)
        out['fatalError'] = failure
        out.setdefault('summary', {'meshAndLocalRigClosureAuthoritative': False})

    out['proofBoundary'] = (
        'This closes physical SEAL6 visible-hand XModel identity, 72-bone skeleton payloads, local bind rotations and '
        'translations, render vertices, triangles, and skin weights from exact current-R2 bytes. The two visible rigs '
        'are exact 70-bone namespace/local-transform supersets of viewmodel_hands_no_model plus tag_gasmask2 and '
        'tag_weapon1. Both retail visible rigs author tag_torso under tag_ads while the generic carrier authors it under '
        'tag_view; that one exact parent difference is retained as a canary and is NOT interpreted here as final DObj '
        'hierarchy. Native OAT geometry counts are independent canaries only. Materials, visible-model selection, and '
        'multi-XModel DObj assembly/order remain separate gates.'
    )
    text = json.dumps(out, indent=2, sort_keys=True) + '\n'
    a.out.write_text(text, encoding='utf-8')
    print(json.dumps(out.get('summary', {}), sort_keys=True))
    print('manifestSha256', hashlib.sha256(text.encode()).hexdigest())
    if failure:
        raise SystemExit(failure)


if __name__ == '__main__':
    main()
