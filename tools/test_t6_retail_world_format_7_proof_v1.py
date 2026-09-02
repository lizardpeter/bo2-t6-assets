#!/usr/bin/env python3
"""Regression for the retained T6 world format-7 retail proof."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

EXPECTED = {
    'summary': {
        'mapCount': 2,
        'format7DirectAllocations': 11,
        'format7ObservedRawStrides': [16],
        'contradictionCount': 0,
        'formatPromotable': 7,
    },
    'maps': {
        'zm_prison': {
            'sha': 'e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487',
            'surfaceCount': 11988, 'materialCount': 607,
            'base': 34760, 'block': [986,1113], 'direct': 10,
        },
        'zm_tomb': {
            'sha': '4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219',
            'surfaceCount': 6469, 'materialCount': 280,
            'base': 46940, 'block': [1271,1327], 'direct': 1,
        },
    },
}

def validate(doc: dict) -> None:
    assert doc['format'] == 't6-retail-world-format-7-proof-v1'
    assert doc['summary'] == EXPECTED['summary']
    maps = {m['map']:m for m in doc['maps']}
    assert set(maps) == set(EXPECTED['maps'])
    for name, exp in EXPECTED['maps'].items():
        m = maps[name]
        assert m['expandedSha256'] == exp['sha']
        assert m['gfxWorld']['surfaceCount'] == exp['surfaceCount']
        assert m['materialMemory']['count'] == exp['materialCount']
        assert m['materialMemory']['postArrayBytesHex'] == 'ffffffff52000000'
        assert m['materialMemory']['firstMaterialFixedStart'] == m['materialMemory']['end'] + 8
        assert m['techniqueBinding']['assetPointerVirtualBase'] == exp['base']
        assert m['techniqueBinding']['block'] == exp['block']
        row = m['format7']
        assert row['directAllocationCount'] == exp['direct']
        assert row['expectedStride'] == 16
        assert row['rawStrides'] == [16]
        assert row['sharedNonseparableCount'] == 0
        assert row['contradictions'] == 0
        for e in row['examples']:
            assert e['rawStride'] == 16
            assert e['span'] == e['vertexCount'] * 16

def rerun(verifier: Path, root: Path, manifest: Path) -> None:
    spec = importlib.util.spec_from_file_location('fmt7', verifier)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    maps = [mod.prove(name,(root/f'{name}.expanded.bin').read_bytes(),cfg) for name,cfg in mod.MAPS.items()]
    doc = {
        'format':'t6-retail-world-format-7-proof-v1',
        'producer':'tools/t6_retail_world_format_7_proof_v1.py',
        'maps':maps,
        'summary':{
            'mapCount':len(maps),
            'format7DirectAllocations':sum(m['format7']['directAllocationCount'] for m in maps),
            'format7ObservedRawStrides':sorted({s for m in maps for s in m['format7']['rawStrides']}),
            'contradictionCount':0,
            'formatPromotable':7,
        },
        'proofBoundary':'worldVertFormat=7 is read from each retail MaterialTechniqueSet reached through GfxSurface -> MaterialMemory -> Material -> TechniqueSet XAsset. Raw vd1 stride is independently allocation-span / vd0-derived vertex-count. No shared/mixed format-7 allocation is used as proof. Shader meaning of normalTransform0 remains outside this proof.',
    }
    doc=json.loads(json.dumps(doc));validate(doc)
    assert doc == json.loads(manifest.read_text(encoding='utf-8'))

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',type=Path,default=Path('manifests/world/T6_RETAIL_WORLD_FORMAT_7_PROOF_V1.json'))
    ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_world_format_7_proof_v1.py'))
    ap.add_argument('--root',type=Path)
    a=ap.parse_args();doc=json.loads(a.manifest.read_text(encoding='utf-8'));validate(doc)
    if a.root: rerun(a.verifier,a.root,a.manifest)
    print('PASS: T6 retail world format 7 proof regression');return 0
if __name__=='__main__': raise SystemExit(main())
