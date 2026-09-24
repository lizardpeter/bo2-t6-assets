#!/usr/bin/env python3
"""Find current-client data pointer holders for the constant-source table and executable xrefs."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-constant-source-table-pointer-xrefs-v1"
TABLE=0x00D2928C
CTX=36

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
      secs.append({"name":name,"va":ib+rva,"virtualSize":vs,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);needle=struct.pack("<I",TABLE);holders=[]
    for s in secs:
      blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      start=0
      while True:
        k=blob.find(needle,start)
        if k<0:break
        holders.append({"va":s["va"]+k,"section":s["name"],"offsetInSection":k,"sectionExecutable":s["exec"]})
        start=k+1
    holder_vas={h["va"] for h in holders}
    hits=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        matches=[]
        for oi,op in enumerate(i.operands):
          vals=[]
          if op.type==X86_OP_IMM: vals.append(("immediate",int(op.imm)&0xffffffff))
          elif op.type==X86_OP_MEM: vals.append(("memDisp",int(op.mem.disp)&0xffffffff))
          for kind,v in vals:
            if v in holder_vas:
              matches.append({"operandIndex":oi,"kind":kind,"holderVa":f"0x{v:08x}"})
        if matches:
          hits.append({"instruction":rr(i),"section":s["name"],"matches":matches,
            "contextBefore":[rr(x) for x in ins[max(0,n-CTX):n]],
            "contextAfter":[rr(x) for x in ins[n+1:min(len(ins),n+CTX+1)]]})
    doc={"format":FORMAT,"authority":"SHA-classified exact PE pointer-value census plus executable operand xrefs",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "table":{"baseVa":f"0x{TABLE:08x}"},
      "pointerHolders":[{**h,"va":f"0x{h['va']:08x}"} for h in holders],
      "hits":hits,
      "summary":{"pointerHolderCount":len(holders),"executableHolderCount":sum(h["sectionExecutable"] for h in holders),"holderXrefInstructionCount":len(hits)},
      "proofBoundary":"Closes literal pointer holders whose stored uint32 value equals the table base and direct executable references to those holder addresses. Register-relayed or computed pointers beyond those xrefs require follow-on dataflow."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
