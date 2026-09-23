#!/usr/bin/env python3
"""Census current-client accesses to source-state offset +0x1A2C (gameTime scalar T)."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
DISP=0x1A2C
FORMAT="t6-current-client-gametime-state-offset-xrefs-v1"
CTX=48
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
          if op.type==X86_OP_MEM and (int(op.mem.disp)&0xffffffff)==DISP:
            refs.append({"operandIndex":oi,
              "baseReg":i.reg_name(op.mem.base) if op.mem.base else None,
              "indexReg":i.reg_name(op.mem.index) if op.mem.index else None,
              "scale":op.mem.scale,
              "positionClass":"destination-or-rmw" if oi==0 and i.mnemonic not in ("cmp","test") else "source-or-other"})
        if not refs:continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        hits.append({"section":s["name"],"instruction":row(i),"references":refs,
          "contextBefore":[row(x) for x in ins[lo:n] if x.id],"contextAfter":[row(x) for x in ins[n+1:hi] if x.id]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded memory operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "target":{"displacementHex":"0x00001a2c","role":"exact source-state field joined to gameTime scalar T for base 0x03A36B00"},
      "summary":{"xrefInstructionCount":len(hits),
        "destinationOrRmwCount":sum(any(r["positionClass"]=="destination-or-rmw" for r in x["references"]) for x in hits),
        "sourceOrOtherCount":sum(any(r["positionClass"]=="source-or-other" for r in x["references"]) for x in hits)},
      "xrefs":hits,
      "proofBoundary":"Exact displacement-access census only. Matching displacement alone does not prove every base register denotes the same source-state type; each candidate must be dataflow-qualified before promotion."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in hits:print(x["instruction"]["address"],x["instruction"]["mnemonic"],x["instruction"]["opStr"],x["references"])
if __name__=="__main__":main()
