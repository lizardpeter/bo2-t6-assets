#!/usr/bin/env python3
"""Regression for strict character Material* loader-replay admission."""
from __future__ import annotations
import importlib.util, json, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location('binding_v2',HERE/'t6_character_material_binding_plan_v2.py')
M=importlib.util.module_from_spec(S);sys.modules[S.name]=M;assert S.loader is not None;S.loader.exec_module(M)


def enc(zone:int,segment:int,offset:int)->int:
    return ((zone&7)<<29)|((segment&3)<<27)|(offset&0x07ffffff)


def exact_doc(evidence:str):
    decoded=enc(1,0,0x2000)
    return {
        'format':'t6-xmodel-surface-material-assignments-v1',
        'summary':{'surfaces':2},
        'assignments':[
            {'surfaceIndex':0,'lodIndex':0,'lodLocalSurfaceIndex':0,'material':'mc/inline',
             'handleRaw':'0xffffffff','handleKind':'inline-following'},
            {'surfaceIndex':1,'lodIndex':0,'lodLocalSurfaceIndex':1,'material':'mc/alias',
             'handleRaw':'0x13579bdf','handleKind':'packed','loaderReplay':{
                 'status':'exact','decodedPointer':hex(decoded),'decodedPointerEvidence':evidence,
                 'zoneSegmentBases':{'1':[0x10000000,None,None,None]},
                 'resolvedTargetPointerSlotVirtual':'0x10002000','sameOwnerBackreference':True,
                 'inlineOwner':{'material':'mc/alias','pointerSlotVirtual':'0x10002000',
                                'objectVirtual':'0x10003000','rawToken':'0xffffffff'}}},
        ],
    }


def main()->int:
    # Production accepts only source-backed decoded-pointer evidence.
    out=M.adapt_surface_assignment_doc(exact_doc('retail-Sys_DecodePointer-replay'))
    proof=out['adapterProof']
    assert proof['inlineSentinelRows']==1
    assert proof['packedRowsExactByLoaderReplay']==1
    assert proof['packedRowsSameOwnerBackreferences']==1
    assert proof['runtimeObfuscatedTokensGuessed']==0
    assert out['bodyMaterials']['surfaceAssignments'][1]['evidence']=='exact-packed-virtual-material-owner-loader-replay'

    # Synthetic evidence is test-only and cannot leak into production adaptation.
    synthetic=exact_doc(M.replay.SYNTHETIC_DECODER_EVIDENCE)
    try:M.adapt_surface_assignment_doc(synthetic)
    except RuntimeError as exc:assert 'decoder-evidence-unaccepted' in str(exc)
    else:raise AssertionError('synthetic decoder evidence accepted in production mode')
    assert M.adapt_surface_assignment_doc(synthetic,allow_synthetic=True)['adapterProof']['packedRowsExactByLoaderReplay']==1

    # Historical v1 durable rows do not contain loaderReplay and must now fail closed.
    old=exact_doc('retail-Sys_DecodePointer-replay')
    old['assignments'][1].pop('loaderReplay')
    try:M.adapt_surface_assignment_doc(old)
    except RuntimeError as exc:assert 'loader-replay-missing' in str(exc)
    else:raise AssertionError('old packed assignment promoted without retail loader replay')

    # Inline classification also has to agree with an actual inline sentinel.
    bad_inline=exact_doc('retail-Sys_DecodePointer-replay')
    bad_inline['assignments'][0]['handleRaw']='0x1234'
    try:M.adapt_surface_assignment_doc(bad_inline)
    except RuntimeError as exc:assert 'non-inline token' in str(exc)
    else:raise AssertionError('non-inline token accepted as inline-following')

    print(json.dumps({'status':'pass','sourceBackedPackedAccepted':True,
                      'legacyPackedRejected':True,'syntheticProductionRejected':True,
                      'inlineSentinelChecked':True},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
