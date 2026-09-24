#!/usr/bin/env python3
"""Locate executable references into the exact current-client 220-row constant-source table.

Table geometry comes from the already-closed static join:
  base = 0x00D2928C
  row size = 20 bytes
  row count = 220
Rows 88/89 are postFxControl4/5. This probe keeps any immediate or memory
 displacement that lands inside the table and projects it to row index/offset.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-constant-source-table-executable-xrefs-v1"
BASE=0x00D2928C
ROW_SIZE=20
ROW_COUNT=220
END=BASE+ROW_SIZE*ROW_COUNT
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
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def classify(v):
    if BASE<=v<END:
        d=v-BASE
        return d//ROW_SIZE,d%ROW_SIZE
    return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            matched=[]
            for oi,op in enumerate(i.operands):
                vals=[]
                if op.type==X86_OP_IMM:
                    vals=[("immediate",int(op.imm)&0xffffffff,None,None,1)]
                elif op.type==X86_OP_MEM:
                    vals=[("memDisp",int(op.mem.disp)&0xffffffff,
                           md.reg_name(op.mem.base) if op.mem.base else None,
                           md.reg_name(op.mem.index) if op.mem.index else None,op.mem.scale)]
                for kind,v,base,index,scale in vals:
                    c=classify(v)
                    if c:
                        row,off=c;matched.append({"operandIndex":oi,"kind":kind,"value":f"0x{v:08x}","rowIndex":row,"rowOffset":off,"baseReg":base,"indexReg":index,"scale":scale})
            if matched:
                lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
                hits.append({"instruction":rr(i),"section":s["name"],"matches":matched,
                             "contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
    row_counts={}
    for h in hits:
        for m in h["matches"]:
            row_counts[str(m["rowIndex"])]=row_counts.get(str(m["rowIndex"]),0)+1
    target=[h for h in hits if any(m["rowIndex"] in (88,89) for m in h["matches"])]
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact executable operand references into independently closed static constant-source table geometry",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "table":{"baseVa":f"0x{BASE:08x}","rowSize":ROW_SIZE,"rowCount":ROW_COUNT,"endVaExclusive":f"0x{END:08x}",
               "postFxControl4RowIndex":88,"postFxControl5RowIndex":89},
      "summary":{"executableInstructionCount":len(hits),"targetRowInstructionCount":len(target),"rowReferenceCounts":row_counts},
      "targetRows":target,"hits":hits,
      "proofBoundary":"Exact executable operand census only. Direct row/table references are proven where present; absence of a direct row-88/89 operand does not exclude indexed access through the table base. Runtime-record construction and per-enum reachability require dataflow joins from the retained contexts."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
