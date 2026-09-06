#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path

P=Path(__file__).with_name('t6_material_pointer_replay_v1.py')
S=importlib.util.spec_from_file_location('replay',P)
M=importlib.util.module_from_spec(S); import sys; sys.modules[S.name]=M; assert S.loader is not None; S.loader.exec_module(M)


def enc(zone, segment, offset):
    return ((zone & 7)<<29)|((segment & 3)<<27)|(offset & 0x07ffffff)


def main():
    # Inline -1 establishes the owner pointer slot.
    st=M.MaterialPointerReplay()
    owner=st.load_inline(pointer_slot_virtual=0x10002000,raw_token=0xffffffff,
                         object_virtual=0x10003000,material='mc/test')
    assert st.pointer_slots[0x10002000] is owner

    # Packed decoded pointer resolves through zone/segment arithmetic.
    bases={1:[0x10000000,0x18000000,None,None]}
    decoded=enc(1,0,0x2000)
    r=st.resolve_packed(raw_token=0x12345678,decoded_pointer=decoded,
                        decoded_pointer_evidence=M.SYNTHETIC_DECODER_EVIDENCE,
                        zone_segment_bases=bases,allow_synthetic=True)
    assert r.exact and r.material=='mc/test' and r.target_pointer_slot_virtual==0x10002000,r

    # Repeating the alias is exact and resolves to the same loaded object.
    r2=st.resolve_packed(raw_token=0x87654321,decoded_pointer=decoded,
                         decoded_pointer_evidence=M.SYNTHETIC_DECODER_EVIDENCE,
                         zone_segment_bases=bases,allow_synthetic=True)
    assert r2.exact and r2.object_virtual==r.object_virtual

    # -3 allocates before inline load and back-fills only after load.
    st2=M.MaterialPointerReplay()
    st2.load_inline(pointer_slot_virtual=0x20001000,raw_token=0xfffffffd,
                    object_virtual=0x20002000,material='mc/inserted',insert_slot_virtual=0x20000080)
    assert st2.events==[
        ('insert-allocate',0x20000080),('inline-load',0x20002000),
        ('owner-slot-write',0x20001000),('insert-backfill',0x20000080)]
    assert st2.pointer_slots[0x20000080].material=='mc/inserted'

    # Raw runtime token alone is never guessed.
    unresolved=st.resolve_packed(raw_token=0xDEADBEEF,decoded_pointer=None,
        decoded_pointer_evidence=None,zone_segment_bases=bases)
    assert not unresolved.exact and unresolved.classification=='runtime-token-unresolved'

    # A decoded value with non-source-backed evidence is also rejected in production mode.
    bad_evidence=st.resolve_packed(raw_token=0x12345678,decoded_pointer=decoded,
        decoded_pointer_evidence=M.SYNTHETIC_DECODER_EVIDENCE,zone_segment_bases=bases)
    assert not bad_evidence.exact and bad_evidence.classification=='decoder-evidence-unaccepted'

    # Missing/invalid target fails closed.
    bad_target=st.resolve_packed(raw_token=0x12345678,decoded_pointer=enc(1,0,0x4444),
        decoded_pointer_evidence=M.SYNTHETIC_DECODER_EVIDENCE,zone_segment_bases=bases,allow_synthetic=True)
    assert not bad_target.exact and bad_target.classification=='alias-target-unpopulated'

    # Durable row validator replays rather than trusting its material/target labels.
    row={'surfaceIndex':0,'material':'mc/test','handleRaw':'0x12345678','loaderReplay':{
        'status':'exact','decodedPointer':hex(decoded),
        'decodedPointerEvidence':M.SYNTHETIC_DECODER_EVIDENCE,
        'zoneSegmentBases':{'1':[0x10000000,0x18000000,None,None]},
        'resolvedTargetPointerSlotVirtual':'0x10002000',
        'inlineOwner':{'material':'mc/test','pointerSlotVirtual':'0x10002000',
                       'objectVirtual':'0x10003000','rawToken':'0xffffffff'}}}
    vr=M.validate_packed_loader_replay(row,allow_synthetic=True)
    assert vr.exact and vr.material=='mc/test',vr
    row_prod=json.loads(json.dumps(row))
    row_prod['loaderReplay']['decodedPointerEvidence']='retail-Sys_DecodePointer-replay'
    vr_prod=M.validate_packed_loader_replay(row_prod)
    assert vr_prod.exact and vr_prod.material=='mc/test',vr_prod
    old={'surfaceIndex':1,'material':'mc/test','handleRaw':'0x99999999'}
    vr2=M.validate_packed_loader_replay(old,allow_synthetic=True)
    assert not vr2.exact and vr2.classification=='loader-replay-missing'

    print(json.dumps({'status':'pass','inline':True,'packed':True,'repeated':True,
                      'insertBackreference':True,'invalidRejected':True,
                      'runtimeTokenFailsClosed':True,'oldAssignmentFailsClosed':True},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
