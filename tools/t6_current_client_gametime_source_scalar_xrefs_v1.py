#!/usr/bin/env python3
"""Exact current-client xref census for the scalar feeding gameTime enum 25."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET=0x03A3852C
FORMAT="t6-current-client-gametime-source-scalar-xrefs-v1"
CTX=64
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
          vals=[]
          if op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0:
            vals.append((int(op.mem.disp)&0xffffffff,"absolute-memory",oi))
          elif op.type==X86_OP_IMM:
            vals.append((int(op.imm)&0xffffffff,"immediate",oi))
          for v,k,oi2 in vals:
            if v==TARGET:
              refs.append({"kind":k,"operandIndex":oi2,
                "positionClass":"destination-or-rmw" if oi2==0 and i.mnemonic not in ("cmp","test") else "source-or-other"})
        if not refs:continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        hits.append({"section":s["name"],"instruction":row(i),"references":refs,
          "contextBefore":[row(x) for x in ins[lo:n] if x.id],"contextAfter":[row(x) for x in ins[n+1:hi] if x.id]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "target":{"va":f"0x{TARGET:08x}","role":"exact scalar read by proven gameTime arithmetic cluster"},
      "summary":{"xrefInstructionCount":len(hits),
        "destinationOrRmwCount":sum(any(r["positionClass"]=="destination-or-rmw" for r in x["references"]) for x in hits),
        "sourceOrOtherCount":sum(any(r["positionClass"]=="source-or-other" for r in x["references"]) for x in hits)},
      "xrefs":hits,
      "proofBoundary":"Exact xrefs only. This file does not name the scalar, containing functions, update cadence, source clock, units, or historical-retail equivalence."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in hits:print(x["instruction"]["address"],x["instruction"]["mnemonic"],x["instruction"]["opStr"],x["references"])
if __name__=="__main__":main()
