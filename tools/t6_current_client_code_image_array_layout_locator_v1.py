#!/usr/bin/env python3
"""Locate current-client indexed code-image-array candidates around source offset +0x1578.

The exact record-8 proof already shows writes to object/source +0x1578. This
locator searches executable instructions for 32-bit memory operands using a
base register plus an index register scaled by 4 with displacement near the
candidate base 0x1530, and for fixed accesses throughout 0x1530..0x15C0.

No array identity is promoted here.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-image-array-layout-locator-v1"
LO=0x1500
HI=0x1600
CANDIDATE_BASE=0x1530
CTX=30
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
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      for n,i in enumerate(ins):
        if i.id==0:continue
        refs=[]
        for oi,op in enumerate(i.operands):
          if op.type!=X86_OP_MEM:continue
          disp=int(op.mem.disp)
          if LO<=disp<HI:
            refs.append({"operandIndex":oi,"displacement":disp,"displacementHex":f"0x{disp:04x}",
              "baseReg":i.reg_name(op.mem.base) if op.mem.base else None,
              "indexReg":i.reg_name(op.mem.index) if op.mem.index else None,
              "scale":op.mem.scale,
              "indexedScale4":bool(op.mem.index and op.mem.scale==4),
              "candidateCodeImageIndex":(disp-CANDIDATE_BASE)//4 if (disp-CANDIDATE_BASE)%4==0 else None,
              "positionClass":"destination-or-rmw" if oi==0 and i.mnemonic not in ("cmp","test") else "source-or-other"})
        if refs:
          lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
          hits.append({"section":s["name"],"instruction":row(i),"references":refs,
            "contextBefore":[row(x) for x in ins[lo:n] if x.id],"contextAfter":[row(x) for x in ins[n+1:hi] if x.id]})
    indexed=[h for h in hits if any(r["indexedScale4"] for r in h["references"])]
    exactBase=[h for h in hits if any(r["displacement"]==CANDIDATE_BASE and r["indexedScale4"] for r in h["references"])]
    exact18=[h for h in hits if any(r["displacement"]==0x1578 for r in h["references"])]
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded memory operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "candidate":{"baseOffsetHex":"0x1530","floatZEnum":18,"floatZCandidateOffsetHex":"0x1578"},
      "summary":{"nearbyMemoryInstructionCount":len(hits),"indexedScale4InstructionCount":len(indexed),
        "exactCandidateBaseIndexedInstructionCount":len(exactBase),"fixed1578InstructionCount":len(exact18)},
      "indexedScale4":indexed,"fixed1578":exact18,
      "proofBoundary":"Locator only. Candidate index arithmetic is diagnostic. No source-state type, codeImages array, sampler enum binding, floatZ provider, or historical-retail semantics are promoted until a dedicated dataflow projector closes both generic indexed access and exact enum identity."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for h in indexed:print("INDEXED",h["instruction"]["address"],h["instruction"]["mnemonic"],h["instruction"]["opStr"],h["references"])
    for h in exact18:print("1578",h["instruction"]["address"],h["instruction"]["mnemonic"],h["instruction"]["opStr"],h["references"])
if __name__=="__main__":main()
