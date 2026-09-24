#!/usr/bin/env python3
"""Exact direct-caller provenance for current-client sun-shadow image builder 0x009AF970.

This sits one level above the already-proven slot-6 image writer. It freezes every
rel32 caller and enough surrounding argument setup to recover the outer function's
incoming resource records without guessing names.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadowmap-sun-parent-callers-v1"
TARGET=0x009AF970
CTX_BEFORE=64
CTX_AFTER=24

class E(RuntimeError):pass
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
def rr(i):
    return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);callers=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            if (int(i.operands[0].imm)&0xffffffff)!=TARGET:continue
            lo=max(0,n-CTX_BEFORE);hi=min(len(ins),n+CTX_AFTER+1)
            callers.append({
              "call":rr(i),"section":s["name"],
              "contextBefore":[rr(x) for x in ins[lo:n]],
              "contextAfter":[rr(x) for x in ins[n+1:hi]],
            })
    req(callers,"no direct caller to 0x009AF970")
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact rel32 caller census for proven sun-shadow source-state builder",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "target":{"functionStartVa":f"0x{TARGET:08x}","source":"proof/current_client/T6_CURRENT_CLIENT_SHADOWMAP_SUN_IMAGE_CALLER_STACK_PROVENANCE_V1.json"},
      "summary":{"directCallerCount":len(callers),"callerAddresses":[c["call"]["address"] for c in callers]},
      "callers":callers,
      "proofBoundary":"Closes only exact direct caller sites and bounded caller argument setup for 0x009AF970. Per-argument semantic identity, resource naming, indirect callers, historical-retail equivalence and framebuffer effects remain separate proof gates."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
