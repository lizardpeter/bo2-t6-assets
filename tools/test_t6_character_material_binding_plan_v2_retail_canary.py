#!/usr/bin/env python3
"""Retail SEAL6 canary for strict packed Material* admission.

The historical surface manifest remains unchanged and must still fail closed by
itself.  The exact historical owner ledger is then joined through the pinned T6
serialized-XFile pointer producer; all 38 packed handles must pass strict replay
without name/LOD/appearance inference.
"""
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
MANIFEST=ROOT/'manifests/nonmap/retail/seal6_smg_surface_material_assignments_v1.json'
OWNER_LEDGER=ROOT/'manifests/nonmap/retail/seal6_smg_material_handle_alias_proof_v1.json'


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;assert s.loader is not None;s.loader.exec_module(m);return m

B=load('binding_v2_canary',HERE/'t6_character_material_binding_plan_v2.py')
P=load('serialized_proof_canary',HERE/'t6_character_material_serialized_proof_v1.py')


def main()->int:
    doc=json.loads(MANIFEST.read_text(encoding='utf-8-sig'))
    owners=json.loads(OWNER_LEDGER.read_text(encoding='utf-8-sig'))
    rows=doc['assignments']
    assert doc['format']=='t6-xmodel-surface-material-assignments-v1'
    assert len(rows)==42 and doc['summary']['surfaces']==42
    assert doc['summary']['lodSurfaceCounts']==[14,10,9,9]
    assert sum(r['lodIndex']==0 for r in rows)==14
    assert len({r['material'] for r in rows})==13
    assert sum(r['handleKind']=='inline-following' for r in rows)==4
    assert sum(r['handleKind']!='inline-following' for r in rows)==38
    assert all('serializedReplay' not in r and 'loaderReplay' not in r for r in rows if r['handleKind']!='inline-following')

    try:B.adapt_surface_assignment_doc(doc)
    except RuntimeError as exc:
        msg=str(exc)
        assert 'surface 0' in msg and 'loader-replay-missing' in msg,msg
    else:raise AssertionError('historical SEAL6 packed handles were promoted without a strict replay proof')

    enriched=P.attach_serialized_replays(doc,owners)
    erows=enriched['assignments']
    assert sum('serializedReplay' in r for r in erows)==38
    assert enriched['serializedPointerProof']['packedRowsExact']==38
    assert enriched['serializedPointerProof']['uniquePackedTokens']==12
    assert enriched['serializedPointerProof']['sameOwnerBackreferences']==26
    assert enriched['serializedPointerProof']['virtualBlockIndex']==5
    adapted=B.adapt_surface_assignment_doc(enriched)
    proof=adapted['adapterProof']
    assert proof['inputRows']==42
    assert proof['inlineSentinelRows']==4
    assert proof['packedRowsExact']==38
    assert proof['packedRowsExactBySerializedXFileReplay']==38
    assert proof['packedRowsExactByRuntimeLoaderReplay']==0
    assert proof['packedRowsSameOwnerBackreferences']==26
    assert proof['runtimeObfuscatedTokensGuessed']==0
    assert proof['serializedTokensGuessed']==0

    print(json.dumps({
        'status':'pass','retailHandles':42,'lod0Surfaces':14,'uniqueMaterials':13,
        'inlineExactRows':4,'packedRowsExactBySerializedXFileReplay':38,
        'uniquePackedTokens':12,'sameOwnerBackreferences':26,
        'strictAllHandlesExact':42,'falsePackedPromotions':0
    },indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
