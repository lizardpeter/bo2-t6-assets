#!/usr/bin/env python3
"""Synthetic end-to-end regression for t6_ipak_iwi_materialize_v1.py."""
from __future__ import annotations
import json, struct, subprocess, sys, tempfile, zlib
from pathlib import Path
from PIL import Image

HERE=Path(__file__).resolve().parent
TOOL=HERE/'t6_ipak_iwi_materialize_v1.py'

def rhash(s:str)->int:
    h=0
    for c in s.encode('latin1'):h=((33*h)^(c|0x20))&0xffffffff
    return h

def make_iwi_bc1()->bytes:
    block=struct.pack('<HHI',0xF800,0x0000,0)  # opaque red 4x4 BC1
    b=bytearray(64+len(block));b[:4]=b'IWi'+bytes([27]);b[4]=0x0B;b[5]=0
    struct.pack_into('<3H',b,6,4,4,1);struct.pack_into('<f',b,12,1.0)
    struct.pack_into('<8I',b,32,len(b),0,0,0,0,0,0,0);b[64:]=block
    return bytes(b)

def make_ipak(path:Path,name:str,iwi:bytes):
    dh=zlib.crc32(iwi)&0x1fffffff;nh=rhash(name);idx_off=64;data_off=128;entry_span=128+len(iwi);total=data_off+entry_span
    out=bytearray(total);out[:16]=struct.pack('<4sIII',b'KAPI',0x50000,total,2)
    out[16:32]=struct.pack('<IIII',1,idx_off,16,1);out[32:48]=struct.pack('<IIII',2,data_off,entry_span,1)
    out[idx_off:idx_off+16]=struct.pack('<IIII',dh,nh,0,entry_span)
    hdr=bytearray(128);struct.pack_into('<I',hdr,0,1<<24);struct.pack_into('<I',hdr,4,len(iwi))
    out[data_off:data_off+128]=hdr;out[data_off+128:]=iwi;path.write_bytes(out);return nh,dh

def main()->int:
    with tempfile.TemporaryDirectory() as td:
        r=Path(td);name='unit_test_texture';iwi=make_iwi_bc1();nh,dh=make_ipak(r/'base.ipak',name,iwi)
        targets={'exactBaseIpakKeys':[{'image':name,'nameHashHex':f'0x{nh:08x}','dataHashHex':f'0x{dh:08x}','repository':'base.ipak'}]}
        meta={'exactBaseIpakKeys':[{'image':name,'nameHashHex':f'0x{nh:08x}','dataHashHex':f'0x{dh:08x}','width':4,'height':4,'depth':1,'uses':['mat:0:colorMap']}]}
        (r/'targets.json').write_text(json.dumps(targets));(r/'meta.json').write_text(json.dumps(meta))
        p=subprocess.run([sys.executable,str(TOOL),'--ipak',str(r/'base.ipak'),'--targets',str(r/'targets.json'),'--metadata',str(r/'meta.json'),'--outdir',str(r/'out')],capture_output=True,text=True)
        assert p.returncode==0,(p.stdout,p.stderr)
        m=json.loads((r/'out'/'manifest.json').read_text());assert m['summary']=={'requested':1,'materialized':1,'unresolved':0,'iwiFiles':1,'pngFiles':1}
        row=m['textures'][0];assert (r/'out'/row['iwiFile']).read_bytes()==iwi
        im=Image.open(r/'out'/row['pngFile']);assert im.size==(4,4);assert im.convert('RGBA').getpixel((0,0))==(255,0,0,255)
        # Same dataHash with a wrong nameHash must not be accepted.
        bad={'exactBaseIpakKeys':[{'image':name,'nameHashHex':'0x12345678','dataHashHex':f'0x{dh:08x}'}]};(r/'bad.json').write_text(json.dumps(bad))
        p=subprocess.run([sys.executable,str(TOOL),'--ipak',str(r/'base.ipak'),'--targets',str(r/'bad.json'),'--outdir',str(r/'badout')],capture_output=True,text=True)
        assert p.returncode==2,(p.stdout,p.stderr);mm=json.loads((r/'badout'/'manifest.json').read_text());assert mm['unresolved'][0]['reason']=='exact-key-not-found'
    print('t6_ipak_iwi_materialize_v1: PASS');return 0
if __name__=='__main__':raise SystemExit(main())
