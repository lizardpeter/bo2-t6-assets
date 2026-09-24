#!/usr/bin/env python3
"""Exact current-client xrefs for the 0x02FB838C per-index pointer table.

The shadow-config writer derives:
  entry_address = 0x02FB838C + index*0x284E0
  subobject     = uint32(entry_address) + 0x13A8
This probe enumerates every decoded executable memory operand whose displacement
is the exact table base so initialization/ownership can be recovered without
inferring structure names from offset coincidence.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadow-config-pointer-table-xrefs-v1"
BASE=0x02FB838C
CTX=40
READ_ONLY={"cmp","test","comiss","ucomiss","comisd","ucomisd"}

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
            for oi,op in enumerate(i.operands):
                if op.type!=X86_OP_MEM:continue
                if (int(op.mem.disp)&0xffffffff)!=BASE:continue
                lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
                hits.append({
                  "instruction":rr(i),"operandIndex":oi,
                  "memory":{
                    "baseReg":md.reg_name(op.mem.base) if op.mem.base else None,
                    "indexReg":md.reg_name(op.mem.index) if op.mem.index else None,
                    "scale":op.mem.scale,"disp":BASE,
                  },
                  "accessClass":"destination-or-rmw" if oi==0 and i.mnemonic not in READ_ONLY else "source-or-test",
                  "section":s["name"],
                  "contextBefore":[rr(x) for x in ins[lo:n]],
                  "contextAfter":[rr(x) for x in ins[n+1:hi]],
                })
    req(hits,"no exact xrefs to pointer-table base")
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact decoded memory operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "target":{"baseVa":f"0x{BASE:08x}","perIndexStride":0x284e0,"consumerSubobjectOffset":0x13a8},
      "summary":{
        "xrefCount":len(hits),
        "destinationOrRmwCount":sum(h["accessClass"]=="destination-or-rmw" for h in hits),
        "sourceOrTestCount":sum(h["accessClass"]=="source-or-test" for h in hits),
        "addresses":[h["instruction"]["address"] for h in hits],
      },
      "hits":hits,
      "proofBoundary":"Exact operand/xref census only. It proves who references the pointer-table base, not the semantic type of the pointed objects. Writer/source provenance must be joined from the retained contexts before the 0x13A8 subobject can be identified as a code-constant source state."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
