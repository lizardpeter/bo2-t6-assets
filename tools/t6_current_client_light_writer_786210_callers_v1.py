#!/usr/bin/env python3
"""Exact direct-call and live-in register probe for current-client 0x00786210.

Retains every direct rel32 caller plus bounded decoded context. Promotion is
deferred until register provenance is closed.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-light-writer-786210-callers-v1"
TARGET=0x00786210
CTX=90
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
      q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);calls=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        if i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM and (int(i.operands[0].imm)&0xffffffff)==TARGET:
          lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
          calls.append({"section":s["name"],"call":rr(i),
            "contextBefore":[rr(z) for z in ins[lo:n]],"contextAfter":[rr(z) for z in ins[n+1:hi]]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact direct call targets and bounded decoded contexts",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "targetVa":f"0x{TARGET:08x}","summary":{"directCallerCount":len(calls)},"callers":calls,
      "proofBoundary":"Exact caller contexts only. ESI/EDI/EAX live-in roles are not assigned unless a separate semantic projector traces their provenance at every promoted callsite."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in calls: print(c["call"]["address"])
if __name__=="__main__":main()
