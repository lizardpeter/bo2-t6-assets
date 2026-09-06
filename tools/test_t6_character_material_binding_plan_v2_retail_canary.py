#!/usr/bin/env python3
"""Retail SEAL6 canary for strict packed Material* admission.

The durable v1 surface assignment manifest predates exact loaderReplay records.
This test intentionally locks that distinction: its 42-handle sequence is valid
retail evidence, but its 38 packed rows must not be promoted by binding-plan v2
until exact decoded-pointer + owner-slot replay is attached to them.
"""
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
MANIFEST=ROOT/'manifests/nonmap/retail/seal6_smg_surface_material_assignments_v1.json'
S=importlib.util.spec_from_file_location('binding_v2_canary',HERE/'t6_character_material_binding_plan_v2.py')
M=importlib.util.module_from_spec(S);sys.modules[S.name]=M;assert S.loader is not None;S.loader.exec_module(M)


def main()->int:
    doc=json.loads(MANIFEST.read_text(encoding='utf-8-sig'))
    rows=doc['assignments']
    assert doc['format']=='t6-xmodel-surface-material-assignments-v1'
    assert len(rows)==42 and doc['summary']['surfaces']==42
    assert doc['summary']['lodSurfaceCounts']==[14,10,9,9]
    assert sum(r['lodIndex']==0 for r in rows)==14
    assert len({r['material'] for r in rows})==13
    assert sum(r['handleKind']=='inline-following' for r in rows)==4
    assert sum(r['handleKind']!='inline-following' for r in rows)==38
    assert all('loaderReplay' not in r for r in rows if r['handleKind']!='inline-following')

    try:M.adapt_surface_assignment_doc(doc)
    except RuntimeError as exc:
        msg=str(exc)
        assert 'surface 0' in msg and 'loader-replay-missing' in msg,msg
    else:raise AssertionError('retail SEAL6 packed handles were promoted without exact loader replay')

    print(json.dumps({'status':'pass','retailHandles':42,'lod0Surfaces':14,
                      'uniqueMaterialsNamedByHistoricalProof':13,'inlineExactRows':4,
                      'packedRowsAwaitingStrictReplay':38,'falsePackedPromotions':0},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
