#!/usr/bin/env python3
"""Regression for t6_ipak_exact_slice_collect_v1.py.

Locks four safety properties:
1. exact (nameHash,dataHash29) pair selects the intended IPAK row;
2. same nameHash with a different dataHash does not match;
3. selected bytes are copied byte-for-byte with stable SHA-256;
4. an index row whose span escapes the declared data section fails closed.
"""
from __future__ import annotations
import hashlib, importlib.util, json, struct, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('slicev1',HERE/'t6_ipak_exact_slice_collect_v1.py')
M=importlib.util.module_from_spec(SPEC); assert SPEC.loader is not None; SPEC.loader.exec_module(M)


def make_ipak(path:Path, rows, payloads, *, corrupt_bounds=False):
    # Header + two section rows. Index at 0x100; data at 0x200.
    index_off=0x100; data_off=0x200
    buf=bytearray(data_off)
    cursor=0
    irows=[]
    for i,(data_hash,name_hash) in enumerate(rows):
        blob=payloads[i]
        rel=cursor
        span=len(blob)
        if corrupt_bounds and i==0: span += 0x1000
        irows.append((data_hash,name_hash,rel,span))
        if not corrupt_bounds or i!=0:
            need=data_off+cursor+len(blob)
            if len(buf)<need:buf.extend(b'\0'*(need-len(buf)))
            buf[data_off+cursor:data_off+cursor+len(blob)]=blob
        cursor += len(blob)
    data_size=cursor
    total=max(len(buf),data_off+data_size)
    if len(buf)<total:buf.extend(b'\0'*(total-len(buf)))
    struct.pack_into('<4sIII',buf,0,b'KAPI',0x50000,len(buf),2)
    struct.pack_into('<IIII',buf,16,1,index_off,len(irows)*16,len(irows))
    struct.pack_into('<IIII',buf,32,2,data_off,data_size,0)
    for i,row in enumerate(irows):struct.pack_into('<IIII',buf,index_off+i*16,*row)
    path.write_bytes(buf)


def main()->int:
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        p=td/'tiny.ipak'
        wanted=b'EXACT-RAW-SPAN-12345'
        decoy=b'DECOY-SAME-NAME-DIFFERENT-DATAHASH'
        nh=0x1234ABCD; dh=0x01234567; other=0x07654321
        make_ipak(p,[(dh,nh),(other,nh)],[wanted,decoy])
        idx=M.IPakIndex(p)
        hits=idx.find_pairs({(nh,dh)})
        assert len(hits)==1,hits
        assert hits[0]['dataHash29']==dh
        got=idx.read_span(hits[0])
        assert got==wanted
        assert hashlib.sha256(got).hexdigest()==hashlib.sha256(wanted).hexdigest()
        assert idx.find_pairs({(nh,0x00111111)})==[]

        # End-to-end target normalization keeps exact pair identity.
        targets=M.normalize_targets([{'id':'wanted','nameHash':f'0x{nh:08X}','dataHash29':f'0x{dh:08X}','dimensions':[8,8,1]}])
        assert targets[0]['nameHash']==nh and targets[0]['dataHash29']==dh

        bad=td/'bad.ipak'
        make_ipak(bad,[(dh,nh)],[wanted],corrupt_bounds=True)
        try:
            M.IPakIndex(bad).find_pairs({(nh,dh)})
        except ValueError as exc:
            assert 'outside data section' in str(exc)
        else:
            raise AssertionError('out-of-bounds target span was accepted')

    print(json.dumps({'status':'pass','exactPairHit':True,'sameNameWrongDataHashRejected':True,'sliceByteExact':True,'outOfBoundsRejected':True},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
