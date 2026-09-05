#!/usr/bin/env python3
from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from t6_ipak_core import IpakEntry, T6Ipak, T6IpakError


def crc29(payload:bytes)->int:
    return zlib.crc32(payload)&0x1fffffff


def block(payload:bytes,*,skip:bytes=b'')->bytes:
    commands=[]
    body=bytearray()
    if skip:
        commands.append((len(skip),0xCF)); body.extend(skip)
    commands.append((len(payload),0)); body.extend(payload)
    header=bytearray(128)
    struct.pack_into('<I',header,0,(len(commands)<<24)|0)
    for i,(size,kind) in enumerate(commands):
        struct.pack_into('<I',header,4+4*i,(kind<<24)|size)
    return bytes(header)+bytes(body)


def make_ipak(path:Path)->tuple[IpakEntry,IpakEntry,bytes,bytes]:
    p1=b'T6 shared IPAK exact-pair fixture A'
    p2=b'T6 shared IPAK exact-pair fixture B'
    name_hash=0x12345678
    b1=block(p1)
    b2=block(p2,skip=b'\xCF\xCF\xCF')
    index_off=0x100
    data_off=0x200
    rel1=0
    rel2=0x100
    e1=IpakEntry(crc29(p1),name_hash,rel1,len(b1))
    e2=IpakEntry(crc29(p2),name_hash,rel2,len(b2))
    total=0x500
    out=bytearray(total)
    struct.pack_into('<4sIII',out,0,b'KAPI',0x50000,total,2)
    struct.pack_into('<IIII',out,16,1,index_off,32,2)
    struct.pack_into('<IIII',out,32,2,data_off,total-data_off,0)
    struct.pack_into('<IIII',out,index_off,*e1.as_tuple())
    struct.pack_into('<IIII',out,index_off+16,*e2.as_tuple())
    out[data_off+rel1:data_off+rel1+len(b1)]=b1
    out[data_off+rel2:data_off+rel2+len(b2)]=b2
    path.write_bytes(out)
    return e1,e2,p1,p2


class TestT6IpakCore(unittest.TestCase):
    def test_exact_pair_and_cf_skip(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'fixture.ipak'
            e1,e2,p1,p2=make_ipak(path)
            ipak=T6Ipak.open_file(path)
            self.assertEqual(ipak.total_size,0x500)
            self.assertEqual(len(ipak.entries),2)
            self.assertEqual(ipak.exact(e1.name_hash,e1.data_hash),e1)
            self.assertEqual(ipak.exact(e2.name_hash,e2.data_hash),e2)
            self.assertEqual(ipak.extract(e1),p1)
            self.assertEqual(ipak.extract(e2),p2)
            self.assertEqual(ipak.extract_exact(e1.name_hash,e1.data_hash),p1)
            self.assertEqual(len(ipak.name_candidates(e1.name_hash)),2)
            self.assertEqual(ipak.unique_data(e1.data_hash),e1)
            self.assertEqual(ipak.unique_data(e2.data_hash),e2)

    def test_same_name_wrong_data_never_falls_back(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'fixture.ipak'
            e1,e2,_,_=make_ipak(path)
            ipak=T6Ipak.open_file(path)
            wrong=(e1.data_hash^0x12345)&0x1fffffff
            self.assertIsNone(ipak.exact(e1.name_hash,wrong))
            with self.assertRaises(T6IpakError) as ctx:
                ipak.extract_exact(e1.name_hash,wrong)
            text=str(ctx.exception)
            self.assertIn('exact pair missing',text)
            self.assertIn(f'{e1.data_hash:08x}',text)
            self.assertIn(f'{e2.data_hash:08x}',text)

    def test_crc29_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'fixture.ipak'
            e1,_,_,_=make_ipak(path)
            data=bytearray(path.read_bytes())
            data[0x200+128]^=1
            path.write_bytes(data)
            ipak=T6Ipak.open_file(path)
            with self.assertRaises(T6IpakError) as ctx:
                ipak.extract(e1)
            self.assertIn('CRC29',str(ctx.exception))


if __name__=='__main__':
    unittest.main()
