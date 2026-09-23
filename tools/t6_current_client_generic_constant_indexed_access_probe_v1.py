#!/usr/bin/env python3
"""Locate indexed current-client accesses to generic T6 code-constant storage.

Exact generic storage already proven independently:
  values  = 0x03A37300 + enum*16 + lane*4
  version = 0x03A382E0 + enum*2

This probe retains every decoded memory operand whose displacement is exactly one
of those bases, including base/index/scale and bounded context. It is locator
evidence only; no accessor/provider semantics are inferred.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-generic-constant-indexed-access-probe-v1"
TARGETS={0x03A37300:"valueBase",0x03A382E0:"versionBase"}
CTX=28

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
def reg(md,r):return md.reg_name(r) if r else None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        refs=[]
        for oi,op in enumerate(i.operands):
          if op.type!=X86_OP_MEM:continue
          disp=int(op.mem.disp)&0xffffffff
          if disp not in TARGETS:continue
          refs.append({"storage":TARGETS[disp],"displacementVa":f"0x{disp:08x}","operandIndex":oi,
            "baseRegister":reg(md,op.mem.base),"indexRegister":reg(md,op.mem.index),"scale":int(op.mem.scale),
            "positionClass":"destination-or-rmw" if oi==0 and i.mnemonic not in ("cmp","test") else "source-or-other"})
        if refs:
          hits.append({"section":s["name"],"instruction":row(i),"references":refs,
            "contextBefore":[row(x) for x in ins[max(0,n-CTX):n]],
            "contextAfter":[row(x) for x in ins[n+1:min(len(ins),n+CTX+1)]]})
    summary={"indexedAccessInstructionCount":len(hits),
      "valueBaseInstructionCount":sum(any(r["storage"]=="valueBase" for r in h["references"]) for h in hits),
      "versionBaseInstructionCount":sum(any(r["storage"]=="versionBase" for r in h["references"]) for h in hits),
      "destinationOrRmwInstructionCount":sum(any(r["positionClass"]=="destination-or-rmw" for r in h["references"]) for h in hits)}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded indexed memory operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "storage":{"valueBaseVa":"0x03a37300","versionBaseVa":"0x03a382e0","valueStridePerEnum":16,"versionStridePerEnum":2},
      "summary":summary,"hits":hits,
      "proofBoundary":"Exact indexed-storage locator only. Register arithmetic and surrounding bytes are retained verbatim. No enum identity, lane identity, source-value ownership, update timing, helper/function name, or historical-retail equivalence is promoted by this probe alone."}
    if not hits:raise SystemExit("no indexed generic constant storage accesses")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for h in hits:print(h["instruction"]["address"],h["instruction"]["mnemonic"],h["instruction"]["opStr"],h["references"])
if __name__=="__main__":main()
