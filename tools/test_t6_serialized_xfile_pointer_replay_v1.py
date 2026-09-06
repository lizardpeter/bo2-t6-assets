#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location('serialized_replay_tested',HERE/'t6_serialized_xfile_pointer_replay_v1.py')
M=importlib.util.module_from_spec(S);sys.modules[S.name]=M;assert S.loader is not None;S.loader.exec_module(M)


def proof(raw, offset, material='mc/test', revision=None):
    return {
        'handleRaw':raw,
        'material':material,
        'serializedReplay':{
            'status':'exact','evidence':M.EXACT_EVIDENCE,
            'sourceRevision': M.OAT_SOURCE_REVISION if revision is None else revision,
            'pointerBits':32,'blockBits':3,'decodedBlockIndex':5,
            'decodedBlockOffset':offset,
            'owner':{'model':'c_test','slotIndex':0,'pointerSlotVirtual':offset,
                     'material':material,'materialRawStart':123,'evidence':'exact-xmodel-materialHandles-field-alias'}
        }
    }


def main():
    reps={
      '0xA0336C39':0x00336C38,
      '0xA00F8EBD':0x000F8EBC,
      '0xA040A719':0x0040A718,
      '0xA0543C69':0x00543C68,
    }
    for raw,off in reps.items():
        d=M.decode_serialized_pointer(raw)
        assert d.block_index==5 and d.block_offset==off,(raw,d)
        assert M.validate_serialized_material_replay(proof(raw,off)).exact

    for raw in (0,0xffffffff,0xfffffffe,0xfffffffd):
        try:M.decode_serialized_pointer(raw)
        except ValueError:pass
        else:raise AssertionError(f'{raw:#x} accepted as packed archive pointer')

    r=M.validate_serialized_material_replay(proof('0xA0336C39',0x00336C38,revision='deadbeef'))
    assert not r.exact and r.classification=='serialized-source-revision-unaccepted'
    r=M.validate_serialized_material_replay(proof('0xA0336C39',0x00336C34))
    assert not r.exact and r.classification=='serialized-owner-slot-mismatch'
    r=M.validate_serialized_material_replay(proof('0x80336C39',0x00336C38))
    assert not r.exact and r.classification=='serialized-block-not-virtual'
    row=proof('0xA0336C39',0x00336C38);row['material']='other'
    r=M.validate_serialized_material_replay(row)
    assert not r.exact and r.classification=='serialized-material-mismatch'
    print(json.dumps({'status':'pass','representativeTokens':len(reps),'virtualBlock':5,'sourceRevisionPinned':True,'invalidCasesRejected':7},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
