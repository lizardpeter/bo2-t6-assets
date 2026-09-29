#!/usr/bin/env python3
"""Locate exact pointer/xref occurrences for current-client function 0x009B59F0.

Scans every PE section for little-endian absolute VA and RVA dwords, records the
containing section/VA, and preserves neighboring dwords/bytes for dispatch-table
or registration-structure analysis. Also enumerates decoded immediate operands
equal to the target VA in executable sections.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET=0x009B59F0

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        ss.append(dict(name=name,rva=rva,va=base+rva,virtualSize=vs,rawSize=rs,rawOffset=ro,
                       executable=bool(ch&0x20000000),writable=bool(ch&0x80000000),readable=bool(ch&0x40000000)))
    return base,ss
def rec(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha {dg}")
    base,ss=pe(raw);rva=TARGET-base
    patterns=[("absolute_va",struct.pack("<I",TARGET)),("rva",struct.pack("<I",rva))]
    hits=[]
    for s in ss:
        data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        for kind,pat in patterns:
            pos=0
            while True:
                j=data.find(pat,pos)
                if j<0:break
                va=s["va"]+j
                lo=max(0,j-64);hi=min(len(data),j+68)
                win=data[lo:hi]
                dwords=[]
                dlo=max(0,j-32);dhi=min(len(data),j+36)
                start=dlo-(dlo%4)
                for k in range(start,dhi-3,4):
                    dwords.append({"va":f"0x{s['va']+k:08X}","value":f"0x{struct.unpack_from('<I',data,k)[0]:08X}"})
                hits.append({"kind":kind,"section":s["name"],"locationVa":f"0x{va:08X}","sectionOffset":j,
                             "windowStartVa":f"0x{s['va']+lo:08X}","windowHex":win.hex(),"neighborDwords":dwords})
                pos=j+1
    imms=[]
    for s in ss:
        if not s["executable"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        for i in md.disasm(data,s["va"]):
            if not i.id:continue
            for op in i.operands:
                if op.type==X86_OP_IMM and (int(op.imm)&0xffffffff)==TARGET:
                    imms.append({"section":s["name"],"instruction":rec(i)})
                    break
    doc={
      "format":"t6-current-client-9b59f0-pointer-xrefs-v1",
      "authority":"SHA-pinned exact PE raw-pointer and decoded immediate census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "target":{"va":f"0x{TARGET:08X}","rva":f"0x{rva:08X}"},
      "rawPointerHits":hits,
      "decodedImmediateHits":imms,
      "summary":{"rawPointerHitCount":len(hits),"absoluteVaHitCount":sum(h["kind"]=="absolute_va" for h in hits),
                 "rvaHitCount":sum(h["kind"]=="rva" for h in hits),"decodedImmediateHitCount":len(imms),
                 "sections":sorted(set(h["section"] for h in hits))},
      "proofBoundary":"Exact byte/immediate census only. A pointer hit suggests a table/registration/reference location but does not assign semantic identity until surrounding structure and use are independently analyzed."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
