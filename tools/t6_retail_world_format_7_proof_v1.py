#!/usr/bin/env python3
"""Retail-byte proof that T6 world format 7 uses 16-byte vd1 records."""
from __future__ import annotations
import argparse, collections, hashlib, json, struct
from pathlib import Path
import t6_retail_world_formats_45_proof_v1 as h

EXPECTED_STRIDE = 16
MAPS = {
    'zm_prison': dict(
        sha='e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487',
        world=82099460, surfs=120530033, nSurf=11988,
        mm=119302137, nMat=607, base=34760, q0=986, q1=1113, direct=10,
    ),
    'zm_tomb': dict(
        sha='4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219',
        world=78964845, surfs=109422353, nSurf=6469,
        mm=108425210, nMat=280, base=46940, q0=1271, q1=1327, direct=1,
    ),
}


def prove(name: str, data: bytes, cfg: dict) -> dict:
    assert hashlib.sha256(data).hexdigest() == cfg['sha']
    blocks, assets = h.front(data)
    w = h.world(data, cfg['world'], cfg['nSurf'], cfg['nMat'])
    surfaces, groups, allocs = h.surfaces_and_groups(data, cfg['surfs'], cfg['nSurf'], w)
    ptrs = sorted({r[4] for r in surfaces})
    assert len(ptrs) == cfg['nMat'] and all(b-a == 8 for a,b in zip(ptrs,ptrs[1:]))
    pidx = {p:i for i,p in enumerate(ptrs)}
    for i in range(cfg['nMat']):
        assert struct.unpack_from('<I', data, cfg['mm'] + 8*i)[0] == h.FOLLOW
    mm_end = cfg['mm'] + 8*cfg['nMat']
    assert data[mm_end:mm_end+8] == bytes.fromhex('ffffffff52000000')
    m0 = mm_end + 8
    mats = h.scan_materials(data, blocks, m0, cfg['surfs'])
    assert len(mats) == cfg['nMat'] and mats[0]['start'] == m0
    base = h.solve_base({m['tech'] for m in mats}, assets, blocks)
    assert base == cfg['base']
    for m in mats:
        _, b, o = h.dec(m['tech'], blocks)
        q = (o-base-4)//8
        assert b == 5 and (o-base-4) % 8 == 0 and assets[q] == (7, h.FOLLOW)
        m['q'] = q
    q0, q1 = cfg['q0'], cfg['q1']
    assert all(assets[q] == (7, h.FOLLOW) for q in range(q0, q1+1))
    assert assets[q1+1][0] == 17
    body = h.scan_tech(data, blocks, cfg['world'])[-(q1-q0+1):]
    assert len(body) == q1-q0+1
    byq = {q0+i:r for i,r in enumerate(body)}
    for m in mats:
        m['fmt'] = byq[m['q']]['fmt']
        m['techName'] = byq[m['q']]['name']
    assert any(m['fmt'] == 7 for m in mats)
    for g in groups:
        fmts = sorted({mats[pidx[p]]['fmt'] for p in g['mats']})
        assert len(fmts) == 1
        g['fmt'] = fmts[0]
    gb = {g['i']:g for g in groups}
    direct, shared = [], []
    for a in allocs:
        fmts = sorted({gb[i]['fmt'] for i in a['groups']})
        a['fmts'] = fmts
        a['matIdx'] = sorted({pidx[p] for p in a['mats']})
        if fmts == [7]: direct.append(a)
        elif 7 in fmts: shared.append(a)
    assert len(direct) == cfg['direct']
    assert all(a['stride'] == EXPECTED_STRIDE for a in direct)
    assert not shared
    examples = []
    for a in direct[:10]:
        examples.append({
            'vd1Offset': a['off'], 'next': a['next'], 'span': a['span'],
            'vertexCount': a['vcs'][0], 'rawStride': a['stride'],
            'materials': [mats[i]['name'] for i in a['matIdx']],
            'techniqueSets': [mats[i]['techName'] for i in a['matIdx']],
        })
    return {
        'map': name,
        'expandedBytes': len(data),
        'expandedSha256': cfg['sha'],
        'gfxWorld': {'fixedStart': cfg['world'], **w},
        'surfaceArray': {'start': cfg['surfs'], 'count': cfg['nSurf'], 'end': cfg['surfs'] + 80*cfg['nSurf']},
        'vertexGroupCount': len(groups),
        'materialMemory': {'start': cfg['mm'], 'count': cfg['nMat'], 'end': mm_end, 'postArrayBytesHex': data[mm_end:mm_end+8].hex(), 'firstMaterialFixedStart': mats[0]['start']},
        'techniqueBinding': {'assetPointerVirtualBase': base, 'distinctReferenced': len({m['q'] for m in mats}), 'block': [q0,q1]},
        'materialFormatCounts': dict(collections.Counter(m['fmt'] for m in mats)),
        'groupFormatCounts': dict(collections.Counter(g['fmt'] for g in groups)),
        'format7': {
            'expectedStride': EXPECTED_STRIDE,
            'directAllocationCount': len(direct),
            'rawStrides': sorted({a['stride'] for a in direct}),
            'sharedNonseparableCount': len(shared),
            'contradictions': 0,
            'examples': examples,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=Path('/mnt/data/t6_xanim_corpus'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    maps = []
    for name,cfg in MAPS.items():
        maps.append(prove(name, (args.root/f'{name}.expanded.bin').read_bytes(), cfg))
    summary = {
        'mapCount': len(maps),
        'format7DirectAllocations': sum(m['format7']['directAllocationCount'] for m in maps),
        'format7ObservedRawStrides': sorted({s for m in maps for s in m['format7']['rawStrides']}),
        'contradictionCount': 0,
        'formatPromotable': 7,
    }
    out = {
        'format': 't6-retail-world-format-7-proof-v1',
        'producer': 'tools/t6_retail_world_format_7_proof_v1.py',
        'maps': maps,
        'summary': summary,
        'proofBoundary': 'worldVertFormat=7 is read from each retail MaterialTechniqueSet reached through GfxSurface -> MaterialMemory -> Material -> TechniqueSet XAsset. Raw vd1 stride is independently allocation-span / vd0-derived vertex-count. No shared/mixed format-7 allocation is used as proof. Shader meaning of normalTransform0 remains outside this proof.',
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
