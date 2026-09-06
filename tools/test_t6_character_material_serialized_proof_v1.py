#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location('serialized_producer_tested',HERE/'t6_character_material_serialized_proof_v1.py')
M=importlib.util.module_from_spec(S);sys.modules[S.name]=M;assert S.loader is not None;S.loader.exec_module(M)

def docs():
    a={'format':'t6-xmodel-surface-material-assignments-v1','source':{'expandedSha256':'abc'},
       'summary':{'surfaces':3},'assignments':[
        {'surfaceIndex':0,'lodIndex':0,'lodLocalSurfaceIndex':0,'handleRaw':'0xA0000101','handleKind':'packed-reference','material':'mc/a'},
        {'surfaceIndex':1,'lodIndex':0,'lodLocalSurfaceIndex':1,'handleRaw':'0xA0000101','handleKind':'packed-reference','material':'mc/a'},
        {'surfaceIndex':2,'lodIndex':0,'lodLocalSurfaceIndex':2,'handleRaw':'0xFFFFFFFF','handleKind':'inline-following','material':'mc/b'}]}
    o={'format':'t6-test-material-handle-proof-v1','source':{'expandedSha256':'abc','materialCatalogSha256':'def'},
       'uniqueHandleOwners':[
        {'materialPointerRaw':'0xA0000101','materialName':'mc/a','evidence':'exact-xmodel-materialHandles-field-alias',
         'ownerModel':'c_owner','ownerSlotIndex':7,'ownerFieldVirtualOffset':0x100,'ownerMaterialRawStart':0x500},
        {'materialPointerRaw':'0xffffffff','materialName':'mc/b','evidence':'direct-inline-material-asset',
         'ownerModel':'c_target','ownerSlotIndex':2,'ownerFieldVirtualOffset':0x200}]}
    return a,o

def main():
    a,o=docs(); out=M.attach_serialized_replays(a,o); p=out['serializedPointerProof']
    assert p['packedRowsExact']==2 and p['uniquePackedTokens']==1 and p['sameOwnerBackreferences']==1
    assert out['assignments'][0]['serializedReplay']['sameOwnerBackreference'] is False
    assert out['assignments'][1]['serializedReplay']['sameOwnerBackreference'] is True
    assert 'serializedReplay' not in out['assignments'][2]
    assert out['assignments'][0]['serializedReplay']['decodedBlockOffset']=='0x00000100'

    a2,o2=docs(); o2['source']['expandedSha256']='wrong'
    try:M.attach_serialized_replays(a2,o2)
    except RuntimeError as e: assert 'same expanded retail XFile' in str(e)
    else:raise AssertionError('source mismatch accepted')

    a3,o3=docs(); o3['uniqueHandleOwners'].append(dict(o3['uniqueHandleOwners'][0],ownerFieldVirtualOffset=0x104))
    try:M.attach_serialized_replays(a3,o3)
    except RuntimeError as e: assert 'conflicting duplicate owner records' in str(e)
    else:raise AssertionError('conflicting owner accepted')

    a4,o4=docs(); o4['uniqueHandleOwners'][0]['ownerFieldVirtualOffset']=0x104
    try:M.attach_serialized_replays(a4,o4)
    except RuntimeError as e: assert 'decoded offset' in str(e)
    else:raise AssertionError('wrong owner slot accepted')

    print(json.dumps({'status':'pass','packedRows':2,'uniquePackedTokens':1,'backreferences':1,'failClosedCases':3},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
