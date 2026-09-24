#!/usr/bin/env python3
"""Census every executable literal reference to generic code-constant storage bases."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-generic-constant-base-reference-census-v1"
BASES={0x03A37300:"valueBase",0x03A382E0:"versionBase"}
CTX=28
READ_ONLY={"cmp","test","comiss","ucomiss","comisd","ucomisd","fld","movzx"}

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
        refs=[]
        for oi,op in enumerate(i.operands):
          if op.type==X86_OP_IMM:
            v=int(op.imm)&0xffffffff
            if v in BASES:refs.append({"storage":BASES[v],"kind":"immediate","operandIndex":oi,"value":f"0x{v:08x}"})
          elif op.type==X86_OP_MEM:
            v=int(op.mem.disp)&0xffffffff
            if v in BASES:
              refs.append({"storage":BASES[v],"kind":"memDisp","operandIndex":oi,"value":f"0x{v:08x}",
                           "baseReg":md.reg_name(op.mem.base) if op.mem.base else None,
                           "indexReg":md.reg_name(op.mem.index) if op.mem.index else None,"scale":op.mem.scale})
        if not refs:continue
        # Direct destination/rmw only if operand0 is the matching memory operand.
        writer_like=any(r["kind"]=="memDisp" and r["operandIndex"]==0 and i.mnemonic not in READ_ONLY for r in refs)
        pointer_formation=any(r["kind"]=="immediate" for r in refs)
        hits.append({"instruction":rr(i),"section":s["name"],"references":refs,
          "writerLikeDirectMemory":writer_like,"pointerFormationImmediate":pointer_formation,
          "contextBefore":[rr(x) for x in ins[max(0,n-CTX):n]],
          "contextAfter":[rr(x) for x in ins[n+1:min(len(ins),n+CTX+1)]]})
    doc={"format":FORMAT,"authority":"SHA-classified exact executable literal reference census for generic constant storage bases",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "storage":{"valueBase":"0x03a37300","versionBase":"0x03a382e0"},
      "summary":{"instructionCount":len(hits),
        "valueBaseReferenceCount":sum(any(r["storage"]=="valueBase" for r in h["references"]) for h in hits),
        "versionBaseReferenceCount":sum(any(r["storage"]=="versionBase" for r in h["references"]) for h in hits),
        "pointerFormationInstructionCount":sum(h["pointerFormationImmediate"] for h in hits),
        "directWriterLikeInstructionCount":sum(h["writerLikeDirectMemory"] for h in hits)},
      "hits":hits,
      "proofBoundary":"Closes literal-base references only. A pointer formed from valueBase can feed later writes through a register; those dataflow consequences are retained in context and require explicit classification. Computed bases with no literal reference remain outside this proof."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
