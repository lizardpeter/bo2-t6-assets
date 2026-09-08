#!/usr/bin/env python3
"""Parse a T6 SABS/SABL bank into a compact exact ID/metadata manifest.

The structural grammar mirrors the retained August 2026 BO2 audio cataloger:
72-byte header, 64-byte dependency slots, 20-byte audio-entry records and
16-byte checksum records. No external Names.xml mapping is required here.

The output is designed as the durable physical side of the SndAlias.assetId
join: every entry retains its exact 32-bit identifier plus source-bank
provenance and playback/container metadata, while audio payload bytes are not
copied into the artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

MAGIC = 0x23585532
VERSION = 0x0E
AUDIO_ENTRY_SIZE = 0x14
CHECKSUM_ENTRY_SIZE = 0x10
DEPENDENCY_ENTRY_SIZE = 0x40
SAMPLE_RATES = [8000,12000,16000,24000,32000,44100,48000,96000,192000]
FORMATS = {0x00:"PCMS16",0x04:"XMA4",0x05:"MP3",0x08:"FLAC"}


class BankError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_bank(data: bytes, source: str = "") -> dict:
    if len(data) < 72:
        raise BankError(f"bank shorter than 72-byte header: {len(data)}")
    magic = struct.unpack_from('<I',data,0)[0]
    version,aesz,cesz,desz,count,dep_count,padding = struct.unpack_from('<7I',data,4)
    declared,entries_off,checksums_off = struct.unpack_from('<3Q',data,32)
    asset_link=data[56:72].hex().upper()
    if magic!=MAGIC: raise BankError(f"magic 0x{magic:08x} != 0x{MAGIC:08x}")
    if version!=VERSION: raise BankError(f"version 0x{version:x} != 0x{VERSION:x}")
    if aesz!=AUDIO_ENTRY_SIZE: raise BankError(f"audio entry size {aesz} != {AUDIO_ENTRY_SIZE}")
    if cesz!=CHECKSUM_ENTRY_SIZE: raise BankError(f"checksum entry size {cesz} != {CHECKSUM_ENTRY_SIZE}")
    if desz!=DEPENDENCY_ENTRY_SIZE: raise BankError(f"dependency entry size {desz} != {DEPENDENCY_ENTRY_SIZE}")
    if declared>len(data): raise BankError(f"declared length {declared} > physical bytes {len(data)}")
    dep_end=72+dep_count*desz
    if dep_end>len(data): raise BankError("dependency table extends outside file")
    if entries_off+count*aesz>len(data): raise BankError("entry table extends outside file")
    if checksums_off+count*cesz>len(data): raise BankError("checksum table extends outside file")

    deps=[]; raw_deps=[]
    for i in range(dep_count):
        raw=data[72+i*desz:72+(i+1)*desz]
        text=raw.split(b'\0',1)[0].decode('ascii',errors='strict')
        raw_deps.append(text)
        if text: deps.append(text)

    entries=[]
    for i in range(count):
        off=entries_off+i*aesz
        ident,size,payload_off,samples=struct.unpack_from('<4I',data,off)
        rate_flag,channels,loop_raw,format_code=struct.unpack_from('<4B',data,off+16)
        rate=SAMPLE_RATES[rate_flag] if rate_flag<len(SAMPLE_RATES) else None
        end=payload_off+size
        checksum=data[checksums_off+i*cesz:checksums_off+(i+1)*cesz].hex().upper()
        entries.append({
            'entryIndex':i,
            'identifierHex':f'{ident:08X}',
            'identifierU32':ident,
            'dataOffset':payload_off,
            'dataBytes':size,
            'dataEndOffset':end,
            'dataInsideFile':0<=payload_off<=end<=len(data),
            'sampleCount':samples,
            'sampleRateFlag':rate_flag,
            'sampleRateHz':rate,
            'channels':channels,
            'loopRaw':loop_raw,
            'loop':bool(loop_raw),
            'formatCode':format_code,
            'formatName':FORMATS.get(format_code,f'UNKNOWN_0x{format_code:02X}'),
            'checksum128Hex':checksum,
        })

    invalid=sum(not e['dataInsideFile'] for e in entries)
    formats={}
    for e in entries: formats[e['formatName']]=formats.get(e['formatName'],0)+1
    return {
        'format':'t6-audio-bank-id-manifest-v1',
        'source':source,
        'bank':{
            'bytes':len(data),
            'sha256':sha256(data),
            'magicHex':f'{magic:08X}',
            'version':version,
            'audioEntrySize':aesz,
            'checksumEntrySize':cesz,
            'dependencyEntrySize':desz,
            'entryCount':count,
            'dependencySlotCount':dep_count,
            'paddingU32':padding,
            'declaredLength':declared,
            'entriesOffset':entries_off,
            'checksumsOffset':checksums_off,
            'assetLinkIdentifierHex':asset_link,
            'dependencies':deps,
            'rawDependencySlots':raw_deps,
        },
        'summary':{
            'entryCount':count,
            'invalidDataEntryCount':invalid,
            'formatCounts':dict(sorted(formats.items())),
            'uniqueIdentifierCount':len({e['identifierU32'] for e in entries}),
        },
        'entries':entries,
        'proofBoundary':'Exact structural manifest of one physical T6 SABS/SABL file. The bank bytes are SHA-256 identified; entry IDs/offsets/sizes/sample metadata/checksum records are read directly from the validated T6 tables. No external filename mapping, SndAlias linkage, or runtime sound-selection semantics are inferred.',
    }


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('bank',type=Path)
    p.add_argument('--source',default='')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=parse_bank(a.bank.read_bytes(),a.source)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(result['summary'],indent=2,sort_keys=True))
    return 1 if result['summary']['invalidDataEntryCount'] else 0


if __name__=='__main__':
    raise SystemExit(main())
