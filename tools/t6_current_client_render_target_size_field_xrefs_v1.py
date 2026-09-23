#!/usr/bin/env python3
"""Exact current-client xref census for proven render-target source-state size fields."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-target-size-field-xrefs-v1"
TARGETS={0x03A38568:"renderTargetWidthDword",0x03A3856C:"renderTargetHeightDword"}
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
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      for n,i in enumerate(ins):
        refs=[]
        for oi,op in enumerate(i.operands):
          if op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0:
            v=int(op.mem.disp)&0xffffffff
            if v in TARGETS:refs.append({"targetVa":f"0x{v:08x}","label":TARGETS[v],"operandIndex":oi,"access":"write" if oi==0 and i.mnemonic not in ("cmp","test") else "read-or-rmw"})
          elif op.type==X86_OP_IMM:
            v=int(op.imm)&0xffffffff
            if v in TARGETS:refs.append({"targetVa":f"0x{v:08x}","label":TARGETS[v],"operandIndex":oi,"access":"immediate-address"})
        if refs:
          lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
          hits.append({"section":s["name"],"instruction":row(i),"references":refs,
            "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]})
    counts={name:{"total":0,"writes":0} for name in TARGETS.values()}
    for h in hits:
      for r in h["references"]:
        x=counts[r["label"]];x["total"]+=1;x["writes"]+=r["access"]=="write"
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded operands + independently proven RC_RESOLVE_COMPOSITE source-state size destinations",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "targets":{f"0x{k:08x}":v for k,v in TARGETS.items()},
      "summary":{"xrefInstructionCount":len(hits),"counts":counts},"xrefs":hits,
      "proofBoundary":"Exact decoded references to the two proven current-client render-target size source-state destinations. Read/write labels are operand-position diagnostics; no reader is promoted as CONST_SRC_CODE_RENDER_TARGET_SIZE until its destination/dataflow closes enum 17."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for h in hits:print(h["instruction"]["address"],h["instruction"]["opStr"])
if __name__=="__main__":main()
