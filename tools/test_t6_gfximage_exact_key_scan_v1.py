#!/usr/bin/env python3
"""Regression for exact T6 GfxImage key scanning."""
from __future__ import annotations
import importlib.util, json, struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location('imgscan',HERE/'t6_gfximage_exact_key_scan_v1.py')
M=importlib.util.module_from_spec(S);assert S.loader is not None;S.loader.exec_module(M)


def strong_record(name:str,data_hash:int=0x01234567,w:int=512,h:int=256,d:int=1):
    fixed=bytearray(80)
    struct.pack_into('<3H',fixed,20,w,h,d)
    struct.pack_into('<I',fixed,40,data_hash)
    struct.pack_into('<I',fixed,72,M.FOLLOWING)
    nh=M.r_hash_string(name);struct.pack_into('<I',fixed,76,nh)
    return bytes(fixed)+name.encode('latin1')+b'\0',nh

def shell_record(name:str):
    fixed=bytearray(80);struct.pack_into('<I',fixed,72,M.FOLLOWING)
    return bytes(fixed)+name.encode('latin1')+b'\0'

def main()->int:
    # Explicitly require a nonzero byte immediately before the name. That byte is
    # GfxImage.hash[3], proving the scanner must not use a preceding-NUL rule.
    name='retail_like_character_diffuse_c'
    rec,nh=strong_record(name)
    assert (nh>>24)&0xff != 0, f'test name hash high byte unexpectedly zero: 0x{nh:08X}'
    data=b'prefix-noise'+rec+b'suffix'
    row=M.scan_one(data,name)
    assert row['summary']['resolved'] and row['summary']['strongHits']==1,row
    assert row['exactStreamedKey']['nameHash']==nh
    assert row['exactStreamedKey']['dataHash29']==0x01234567
    assert row['exactStreamedKey']['dimensions']==[512,256,1]

    shell='retail_alias_shell_n'
    row2=M.scan_one(shell_record(shell),shell)
    assert not row2['summary']['resolved'] and row2['summary']['aliasShells']==1,row2

    # Same exact serialized identity with conflicting strict streamed keys is an
    # ambiguity and must fail closed.
    a,_=strong_record(name,0x00111111);b,_=strong_record(name,0x00222222)
    try:M.scan_one(a+b,name)
    except RuntimeError as exc:assert 'conflicting exact streamed GfxImage keys' in str(exc)
    else:raise AssertionError('conflicting GfxImage keys were accepted')

    print(json.dumps({'status':'pass','nonzeroPrecedingHashByteAccepted':True,'aliasShellSeparated':True,'conflictRejected':True},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
