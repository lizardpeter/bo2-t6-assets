#!/usr/bin/env python3
"""Locate exact indexed writers to current-client generic code image/sampler-state arrays.

The generic consumer contract is already proven:
  codeImages[index]             = source + 0x1530 + index*4
  codeImageSamplerStates[index] = source + 0x160C + index
This probe retains only executable instructions whose destination operand has
those exact displacements, including indexed forms.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-generic-code-sampler-indexed-writers-v1"
DISPS={0x1530:"codeImages",0x160c:"codeImageSamplerStates"}
CTX=32
READ_ONLY={"cmp","test","comiss","ucomiss","comisd","ucomisd"}

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
    ib,secs=pe(raw);hits=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic in READ_ONLY or not i.operands:continue
            op=i.operands[0]
            if op.type!=X86_OP_MEM:continue
            disp=int(op.mem.disp)&0xffffffff
            if disp not in DISPS:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            hits.append({"array":DISPS[disp],"instruction":rr(i),"section":s["name"],
              "memory":{"baseReg":md.reg_name(op.mem.base) if op.mem.base else None,
                        "indexReg":md.reg_name(op.mem.index) if op.mem.index else None,
                        "scale":op.mem.scale,"disp":disp},
              "contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
    summary={
      "indexedOrDirectWriterInstructionCount":len(hits),
      "codeImagesWriterInstructionCount":sum(h["array"]=="codeImages" for h in hits),
      "samplerStatesWriterInstructionCount":sum(h["array"]=="codeImageSamplerStates" for h in hits),
      "indexedCodeImagesWriterCount":sum(h["array"]=="codeImages" and h["memory"]["indexReg"] is not None for h in hits),
      "indexedSamplerStatesWriterCount":sum(h["array"]=="codeImageSamplerStates" and h["memory"]["indexReg"] is not None for h in hits),
    }
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded destination operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"hits":hits,
      "proofBoundary":"Exact destination-operand locator only. Displacement identity is joined to the independently proven generic array geometry, but base-register source-state ownership, index provenance, image/resource semantics, state-byte meanings, historical-retail equivalence and framebuffer behavior require dedicated dataflow proofs."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
