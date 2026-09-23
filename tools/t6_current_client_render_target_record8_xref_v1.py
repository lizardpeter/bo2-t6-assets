#!/usr/bin/env python3
"""Exact current-client xref census for render-target record 8 derived addresses."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-target-record8-xref-v1"
TARGETS={
  0x03A267C0:"record8+0 firstDword",
  0x03A267CC:"record8+0x0c width",
  0x03A267CE:"record8+0x0e height",
}
CTX=80
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
        for op in i.operands:
          if op.type==X86_OP_IMM:
            v=int(op.imm)&0xffffffff
            if v in TARGETS:refs.append((v,"immediate"))
          elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0:
            v=int(op.mem.disp)&0xffffffff
            if v in TARGETS:refs.append((v,"absolute-memory"))
        if not refs:continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        hits.append({"section":s["name"],"instruction":row(i),
          "references":[{"targetVa":f"0x{v:08x}","label":TARGETS[v],"kind":k} for v,k in refs],
          "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]})
    counts={f"0x{k:08x}":sum(any(r["targetVa"]==f"0x{k:08x}" for r in h["references"]) for h in hits) for k in TARGETS}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded operands + independently proven record-8 address arithmetic",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "targets":{f"0x{k:08x}":v for k,v in TARGETS.items()},
      "summary":{"xrefInstructionCount":len(hits),"xrefCountsByTarget":counts},
      "xrefs":hits,
      "proofBoundary":"Exact decoded references to independently derived record-8 addresses only. No xref function is assigned float-Z semantics, and the record first-dword field is not promoted as GfxImage* unless its dataflow independently closes that identity."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for h in hits:print(h["instruction"]["address"],h["references"])
if __name__=="__main__":main()
