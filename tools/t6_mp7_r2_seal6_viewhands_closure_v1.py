#!/usr/bin/env python3
"""Close current-R2 MP7 SEAL6 visible viewhands from retail raw XModels.

Authority chain:
- exact SHA-pinned current-R2 common_mp for the 70-bone hands carrier;
- exact SHA-pinned faction_seals_mp, whose physical ownership of both visible
  SEAL6 XModels was independently established by dependency-free native OAT;
- exact inline serialized XModel identity + full XModel walker is used only to
  locate the already-owned physical record inside that SHA-pinned stream;
- reusable storage, if encountered, remains fail-closed unless the unique
  VIRTUAL allocation replay can be established;
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


def _find_exact_inline_xmodel(data: bytes, name: str) -> dict:
    """Locate one exact physical XModel record after ownership is already proven."""
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
        raw = struct.unpack_from('<I', data, start)[0]
        if raw not in (FOLLOWING, INSERT):
            continue
        try:
            walk = XModelWalker(data, start).walk_xmodel()
        except Exception:
            continue
        x = walk.get('xmodel', {})
        if x.get('name') == name and walk.get('assetFixedStart') == start:
            matches.append(walk)
    if len(matches) != 1:
        raise ValueError(
            f'{name}: expected one exact inline serialized XModel identity in its proven physical owner; '
            f'got {len(matches)} structural matches from {len(occurrences)} literal occurrences'
        )
    return matches[0]


def _by_name(skel: dict) -> dict[str, dict]:
    rows = skel['skeleton']['bones']
    if len({b['name'] for b in rows}) != len(rows):
        raise ValueError('duplicate bone name in XModel skeleton')
    return {b['name']: b for b in rows}


def _parent_name(rows: list[dict], bone: dict) -> str | None:
    pi = bone['parentIndex']
    return None if pi is None else rows[int(pi)]['name']


def _shared_binding_comparison(carrier: dict, visible: dict) -> dict:
    cbones = carrier['skeleton']['bones']
    vbones = visible['skeleton']['bones']
    c = _by_name(carrier); v = _by_name(visible)
    cset, vset = set(c), set(v)
    missing = sorted(cset - vset)
    extras = sorted(vset - cset)
    rows = []
    for name in sorted(cset & vset):
        cb, vb = c[name], v[name]
        cp = _parent_name(cbones, cb)
        vp = _parent_name(vbones, vb)
        rot_eq = cb['localRotationInt16'] == vb['localRotationInt16']
        trans_eq = cb['localTranslation'] == vb['localTranslation']
        rows.append({
            'name': name,
            'carrierIndex': cb['index'],
            'visibleIndex': vb['index'],
            'carrierParent': cp,
            'visibleParent': vp,
            'parentExact': cp == vp,
            'localRotationInt16Exact': rot_eq,
            'localTranslationExact': trans_eq,
        })
    return {
        'carrierBoneCount': len(cbones),
        'visibleBoneCount': len(vbones),
        'sharedBoneCount': len(rows),
        'missingCarrierBones': missing,
        'visibleOnlyBones': extras,
        'expectedVisibleOnlyBones': EXPECTED_VISIBLE_EXTRAS,
        'namespaceSupersetExact': not missing and extras == EXPECTED_VISIBLE_EXTRAS,
        'sharedHierarchyExact': all(r['parentExact'] for r in rows),
        'sharedLocalRotationExact': all(r['localRotationInt16Exact'] for r in rows),
        'sharedLocalTranslationExact': all(r['localTranslationExact'] for r in rows),
        'parentMismatchCount': sum(not r['parentExact'] for r in rows),
        'rotationMismatchCount': sum(not r['localRotationInt16Exact'] for r in rows),
        'translationMismatchCount': sum(not r['localTranslationExact'] for r in rows),
        'mismatches': [r for r in rows if not (r['parentExact'] and r['localRotationInt16Exact'] and r['localTranslationExact'])],
    }


def _mesh_summary(doc: dict) -> dict:
    return {
        'meshSourceMode': doc['meshSource']['mode'],
        'surfaceCount': len(doc['surfaces']),
        'vertexCount': sum(int(s['vertCount']) for s in doc['surfaces']),
        'triangleCount': sum(int(s['triCount']) for s in doc['surfaces']),
        'unweightedVertexCount': sum(int(s['unweightedVertexCount']) for s in doc['surfaces']),
        'normalizedCanonicalSha256': hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
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
        'format': 't6-mp7-r2-seal6-viewhands-closure-v1',
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

        matches = {name: _find_exact_inline_xmodel(faction, name) for name in TARGETS}
        all_ok = True
        for name, oracle in TARGETS.items():
            walk = matches[name]
            start = int(walk['assetFixedStart'])
            if walk.get('blockers'):
                raise ValueError(f'{name}: serialized XModel walker blockers {walk["blockers"]}')
            # Physical owner is already established independently.  These two
            # target records are inline identities; if their nested arrays are
            # packed, normalize_skeleton/normalize_mesh still fail closed here.
            skel = normalize_skeleton(faction, start, identity_name=name)
            bind = _shared_binding_comparison(carrier, skel)
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
                'numBones': skel['skeleton']['numBones'],
                'numRootBones': skel['skeleton']['numRootBones'],
                'bindingTo70BoneCarrier': bind,
                'nativeOracle': oracle,
            }
            try:
                mesh = normalize_mesh(faction, start, identity_name=name)
                ms = _mesh_summary(mesh)
                row['mesh'] = ms
                row['meshError'] = None
                canary = (
                    ms['surfaceCount'] == oracle['surfaces'] and
                    ms['vertexCount'] == oracle['vertices'] and
                    ms['triangleCount'] == oracle['triangles'] and
                    ms['unweightedVertexCount'] == 0 and
                    skel['skeleton']['numBones'] == oracle['bones']
                )
            except Exception as exc:
                row['mesh'] = None
                row['meshError'] = repr(exc)
                canary = False
            row['nativeGeometryCanaryExact'] = canary
            bind_ok = (
                bind['namespaceSupersetExact'] and bind['sharedHierarchyExact'] and
                bind['sharedLocalRotationExact'] and bind['sharedLocalTranslationExact']
            )
            row['shared70BindExact'] = bind_ok
            all_ok = all_ok and bind_ok and canary
            out['targets'].append(row)

        out['summary'] = {
            'targetCount': len(out['targets']),
            'allShared70BindExact': all(r['shared70BindExact'] for r in out['targets']),
            'allNativeGeometryCanariesExact': all(r['nativeGeometryCanaryExact'] for r in out['targets']),
            'allVerticesWeighted': all(r['mesh'] is not None and r['mesh']['unweightedVertexCount'] == 0 for r in out['targets']),
            'authoritative': all_ok,
        }
        if not all_ok:
            failure = 'SEAL6 visible-hands bind/mesh closure did not fully close'
    except Exception as exc:
        failure = repr(exc)
        out['fatalError'] = failure
        out.setdefault('summary', {'authoritative': False})

    out['proofBoundary'] = (
        'Native dependency-free OAT already establishes faction_seals_mp as a physical owner of both exact visible '
        'SEAL6 XModels. Exact inline serialized name plus a valid full XModel walk is therefore used only as a locator '
        'inside that SHA-pinned physical owner, not as ownership evidence. Packed VIRTUAL nested arrays remain fail-closed '
        'unless unique allocator replay can establish an earlier physical owner. Shared hands-rig compatibility requires '
        'the 70-bone common_mp carrier namespace, hierarchy, raw int16 local rotations, and local translations to match '
        'by resolved bone identity. Native OAT geometry counts are independent canaries. Materials and final DObj '
        'assembly/order remain separate gates.'
    )
    text = json.dumps(out, indent=2, sort_keys=True) + '\n'
    a.out.write_text(text, encoding='utf-8')
    print(json.dumps(out.get('summary', {}), sort_keys=True))
    print('manifestSha256', hashlib.sha256(text.encode()).hexdigest())
    if failure:
        raise SystemExit(failure)


if __name__ == '__main__':
    main()
