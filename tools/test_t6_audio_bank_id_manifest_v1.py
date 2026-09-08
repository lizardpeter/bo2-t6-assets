#!/usr/bin/env python3
from __future__ import annotations

import struct

import t6_audio_bank_id_manifest_v1 as mod


def fixture() -> bytes:
    size=400
    b=bytearray(size)
    struct.pack_into('<I',b,0,mod.MAGIC)
    struct.pack_into(
        '<7I',b,4,
        mod.VERSION,mod.AUDIO_ENTRY_SIZE,mod.CHECKSUM_ENTRY_SIZE,
        mod.DEPENDENCY_ENTRY_SIZE,2,1,0,
    )
    struct.pack_into('<3Q',b,32,size,256,296)
    b[56:72]=bytes.fromhex('00112233445566778899AABBCCDDEEFF')
    dep=b'fixture_common.all.sabs\x00'
    b[72:72+len(dep)]=dep

    # Physical payload ranges live before the metadata tables in this fixture.
    b[160:170]=b'A'*10
    b[180:200]=b'B'*20
    struct.pack_into('<4I4B',b,256,0x11223344,10,160,48000,6,1,0,8)
    struct.pack_into('<4I4B',b,276,0x55667788,20,180,22050,5,2,1,0)
    b[296:312]=bytes.fromhex('00112233445566778899AABBCCDDEEFF')
    b[312:328]=bytes.fromhex('FFEEDDCCBBAA99887766554433221100')
    return bytes(b)


def main() -> int:
    d=mod.parse_bank(fixture(),'fixture.sabs')
    assert d['summary']['entryCount']==2
    assert d['summary']['uniqueIdentifierCount']==2
    assert d['summary']['invalidDataEntryCount']==0
    assert d['summary']['formatCounts']=={'FLAC':1,'PCMS16':1}
    assert d['bank']['dependencies']==['fixture_common.all.sabs']
    assert d['bank']['assetLinkIdentifierHex']=='00112233445566778899AABBCCDDEEFF'
    assert d['entries'][0]['identifierHex']=='11223344'
    assert d['entries'][0]['sampleRateHz']==48000
    assert d['entries'][0]['checksum128Hex']=='00112233445566778899AABBCCDDEEFF'
    assert d['entries'][1]['identifierHex']=='55667788'
    assert d['entries'][1]['sampleRateHz']==44100
    assert d['entries'][1]['loop'] is True

    bad=bytearray(fixture()); struct.pack_into('<I',bad,0,0)
    try: mod.parse_bank(bytes(bad),'bad.sabs')
    except mod.BankError: pass
    else: raise AssertionError('bad magic must fail')

    bad=bytearray(fixture()); struct.pack_into('<Q',bad,32+8,390)
    try: mod.parse_bank(bytes(bad),'bad-table.sabs')
    except mod.BankError: pass
    else: raise AssertionError('entry table outside file must fail')

    print('PASS: T6 audio bank parser preserves exact table metadata and rejects malformed banks')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
