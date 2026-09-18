#!/usr/bin/env python3
"""Regression for source-closed T6 IPAK 0xCF skip-command handling."""
from __future__ import annotations
import struct,zlib
import t6_ipak_http_range_v1 as v1
import t6_ipak_http_range_v2 as v2

class MemSource:
    def __init__(self,data:bytes):
        self.data=data; self.url="memory://fixture"; self.requests=0; self.bytes_fetched=0
    def read_at(self,offset:int,size:int)->bytes:
        b=self.data[offset:offset+size]
        if len(b)!=size: raise ValueError("short fixture read")
        self.requests+=1; self.bytes_fetched+=size
        return b

def block(commands, payloads):
    assert len(commands)==len(payloads)
    hdr=bytearray(128)
    struct.pack_into("<I",hdr,0,(len(commands)<<24)|0)
    for i,(size,comp) in enumerate(commands):
        assert size==len(payloads[i])
        struct.pack_into("<I",hdr,4+4*i,(comp<<24)|size)
    return bytes(hdr)+b"".join(payloads)

def instance(cls,blob):
    x=object.__new__(cls)
    x.source=MemSource(blob)
    x.data_section=(v1.IPAK_DATA,0,len(blob),0)
    return x

def main():
    emitted=b"IWi\x1b"+bytes([13,16])+struct.pack("<3H",2,2,1)+b"PAYLOAD"
    skip=b"PADPAD!"
    blob=block([(len(skip),0xCF),(len(emitted),0x00)],[skip,emitted])
    data_hash=zlib.crc32(emitted)&0x1fffffff
    entry=(data_hash,0x12345678,0,len(blob))

    got=instance(v2.T6IPakRangeV2,blob).extract_entry(entry)
    assert got==emitted

    try:
        instance(v1.T6IPakRange,blob).extract_entry(entry)
    except ValueError as e:
        assert "unsupported IPAK compression command 207" in str(e)
    else:
        raise AssertionError("v1 unexpectedly accepted 0xCF")

    bad=block([(1,0xCE)],[b"X"])
    bad_hash=zlib.crc32(b"")&0x1fffffff
    try:
        instance(v2.T6IPakRangeV2,bad).extract_entry((bad_hash,1,0,len(bad)))
    except ValueError as e:
        assert "unsupported IPAK compression command 206" in str(e)
    else:
        raise AssertionError("v2 accepted unknown command")

    print("PASS t6_ipak_http_range_v2 0xCF skip regression")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
