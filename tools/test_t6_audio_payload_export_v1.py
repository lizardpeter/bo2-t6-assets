#!/usr/bin/env python3
from __future__ import annotations

import struct

import t6_audio_payload_export_v1 as exp
from t6_audio_bank_id_manifest_v1 import AUDIO_ENTRY_SIZE,CHECKSUM_ENTRY_SIZE,DEPENDENCY_ENTRY_SIZE,MAGIC,VERSION


def fixture() -> bytes:
    b=bytearray(512)
    struct.pack_into('<I',b,0,MAGIC)
    struct.pack_into('<7I',b,4,VERSION,AUDIO_ENTRY_SIZE,CHECKSUM_ENTRY_SIZE,DEPENDENCY_ENTRY_SIZE,2,0,0)
    struct.pack_into('<3Q',b,32,len(b),256,296)
    b[56:72]=bytes(16)

    # Four stereo PCM frames -> 4 * 2 * 2 = 16 exact PCM bytes.
    pcm=struct.pack('<8h',-32768,-1,0,1,2,3,32766,32767)
    b[128:144]=pcm
    struct.pack_into('<4I4B',b,256,0x11111111,len(pcm),128,4,6,2,0,0)  # 48 kHz, 2 ch, PCMS16

    flac=b'fLaC'+bytes.fromhex('0000002210001000000000000000')
    b[160:160+len(flac)]=flac
    struct.pack_into('<4I4B',b,276,0x22222222,len(flac),160,1234,6,1,0,8)
    b[296:328]=bytes(32)
    return bytes(b)


def main() -> int:
    bank=fixture()
    wav,ext,p=exp.export_entry(bank,source='fixture.sabs',entry_index=0)
    assert ext=='.wav'
    assert wav[:4]==b'RIFF' and wav[8:12]==b'WAVE'
    assert wav[12:16]==b'fmt ' and wav[36:40]==b'data'
    fmt_size,audio_fmt,channels,rate,byte_rate,align,bits=struct.unpack_from('<IHHIIHH',wav,16)
    assert (fmt_size,audio_fmt,channels,rate,byte_rate,align,bits)==(16,1,2,48000,192000,4,16)
    assert struct.unpack_from('<I',wav,40)[0]==16
    assert wav[44:]==bank[128:144]
    assert p['authority']['physicalFormatName']=='SND_ASSET_FORMAT_PCMS16'

    flac,ext,p=exp.export_entry(bank,source='fixture.sabs',identifier=0x22222222)
    assert ext=='.flac'
    assert flac==bank[160:160+len(flac)]
    assert flac[:4]==b'fLaC'
    assert p['authority']['physicalFormatName']=='SND_ASSET_FORMAT_FLAC'

    bad=bytearray(bank); bad[160:164]=b'NOPE'
    try: exp.export_entry(bytes(bad),entry_index=1)
    except exp.ExportError: pass
    else: raise AssertionError('format-8 non-FLAC payload must fail')

    bad=bytearray(bank); struct.pack_into('<I',bad,256+4,14)
    try: exp.export_entry(bytes(bad),entry_index=0)
    except exp.ExportError: pass
    else: raise AssertionError('PCMS16 byte-count mismatch must fail')

    try: exp.export_entry(bank,identifier=0xDEADBEEF)
    except exp.ExportError: pass
    else: raise AssertionError('missing identifier must fail')

    print('PASS: T6 PC payload exporter wraps exact PCMS16 as WAV, passes exact FLAC through, and fails closed')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
