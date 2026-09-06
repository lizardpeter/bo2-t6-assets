#!/usr/bin/env python3
"""Synthetic end-to-end regression for t6_ipak_iwi_materialize_v1.py."""
from __future__ import annotations
import json, struct, subprocess, sys, tempfile, zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;TOOL=HERE/'t6_ipak_iwi_materialize_v1.py'

def rhash(s:str)->int:
 h=0
 for c in s.encode('latin1'):h=((33*h)^(c|0x20))&0xffffffff
 return h

def make_iwi_bc1()->bytes:
 block=struct.pack('<HHI',0xF800,0x0000,0)
 b=bytearray(64+len(block));b[:4]=b'IWi'+bytes([27]);b[4]=0x0B;b[5]=0;struct.pack_into('<3H',b,6,4,4,1);struct.pack_into('<f',b,12,1.0);struct.pack_into('<8I',b,32,len(b),0,0,0,0,0,0,0);b[64:]=block
 return bytes(b)

def make_ipak(path:Path,name:str,iwi:bytes):
 dh=zlib.crc32(iwi)&0x1fffffff;nh=rhash(name);idx_off=64;data_off=128;entry_span=128+len(iwi);total=data_off+entry_span;out=bytearray(total);out[:16]=struct.pack('<4sIII',b'KAPI',0x50000,total,2);out[16:32]=struct.pack('<IIII',1,idx_off,16,1);out[32:48]=struct.pack('<IIII',2,data_off,entry_span,1);out[idx_off:idx_off+16]=struct.pack('<IIII',dh,nh,0,entry_span);hdr=bytearray(128);struct.pack_into('<I',hdr,0,1<<24);struct.pack_into('<I',hdr,4,len(iwi));out[data_off:data_off+128]=hdr;out[data_off+128:]=iwi;path.write_bytes(out);return nh,dh

def main():
 with tempfile.TemporaryDirectory() as td:
  r=Path(td);name='unit_test_texture';iwi=make_iwi_bc1();nh,dh=make_ipak(r/'base.ipak',name,iwi)
  targets={'exactBaseIpakKeys':[{'image':name,'nameHashHex':f'0x{nh:08x}','dataHashHex':f'0x{dh:08x}','repository':'base.ipak'}]};meta={'exactBaseIpakKeys':[{'image':name,'nameHashHex':f'0x{nh:08x}','dataHashHex':f'0x{dh:08x}','width':4,'height':4,'depth':1,'uses':['mat:0:colorMap']}]};(r/'targets.json').write_text(json.dumps(targets));(r/'meta.json').write_text(json.dumps(meta))
  p=subprocess.run([sys.executable,str(TOOL),'--ipak',str(r/'base.ipak'),'--targets',str(r/'targets.json'),'--metadata',str(r/'meta.json'),'--outdir',str(r/'out')],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr);m=json.loads((r/'out'/'manifest.json').read_text());assert m['summary']=={'requested':1,'materialized':1,'unresolved':0,'iwiFiles':1,'pngFiles':1};row=m['textures'][0];assert (r/'out'/row['iwiFile']).read_bytes()==iwi;png=(r/'out'/row['pngFile']).read_bytes();assert png[:8]==b'\x89PNG\r\n\x1a\n';assert struct.unpack_from('>II',png,16)==(4,4);pos=8;raw=b''
  while pos<len(png):
   n=struct.unpack_from('>I',png,pos)[0];kind=png[pos+4:pos+8];payload=png[pos+8:pos+8+n];pos+=12+n
   if kind==b'IDAT':raw+=payload
  scan=zlib.decompress(raw);assert scan[0]==0 and scan[1:5]==bytes((255,0,0,255))
  bad={'exactBaseIpakKeys':[{'image':name,'nameHashHex':'0x12345678','dataHashHex':f'0x{dh:08x}'}]};(r/'bad.json').write_text(json.dumps(bad));p=subprocess.run([sys.executable,str(TOOL),'--ipak',str(r/'base.ipak'),'--targets',str(r/'bad.json'),'--outdir',str(r/'badout')],capture_output=True,text=True);assert p.returncode==2;mm=json.loads((r/'badout'/'manifest.json').read_text());assert mm['unresolved'][0]['reason']=='exact-key-not-found'
 print('t6_ipak_iwi_materialize_v1: PASS')
 return 0
if __name__=='__main__':raise SystemExit(main())
