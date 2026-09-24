#!/usr/bin/env python3
"""Freeze exact caller argument setup for enum38 sunShadowmapPixelSize writer 0x00497450."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-sun-shadowmap-pixel-size-caller-arguments-v1"
TARGET=0x00497450
EXPECTED={0x00657B1C,0x0088A59C,0x0089F3BB,0x0089F4D3,0x0092ACA4}
PRE=56
POST=18
class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def rr(i): return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            if (int(i.operands[0].imm)&0xffffffff)!=TARGET:continue
            lo=max(0,n-PRE);hi=min(len(ins),n+POST+1)
            rows.append({"call":rr(i),"section":s["name"],"contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
    got={int(x["call"]["address"],16) for x in rows}
    req(got==EXPECTED,f"caller denominator drift {sorted(hex(x) for x in got)}")
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact rel32 caller denominator and argument-setup windows",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "target":{"functionStartVa":f"0x{TARGET:08x}","laneFormula":"second function argument +{0x28,0x2C,0x30,0x34} -> enum38 lanes 0..3"},
      "summary":{"directCallerCount":len(rows),"callerAddresses":[x["call"]["address"] for x in rows]},
      "callers":rows,
      "proofBoundary":"Exact caller windows only. This freezes every callsite needed to recover first-argument context index and second-argument source-record provenance; it does not yet name those records, prove update cadence, historical-retail equivalence or framebuffer behavior."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
