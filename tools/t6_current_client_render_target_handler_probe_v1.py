#!/usr/bin/env python3
"""Focused exact-byte probe for current-client render-target command handlers.

The handler VAs are independently proven by the exact render-command table:
  0x00743e70 RC_BLEND_SAVED_SCREEN_{BLURRED,FLASHED}
  0x00745d30 RC_RESOLVE_COMPOSITE

This probe retains bounded disassembly plus all absolute memory operands and direct
call targets. It does not assign render-target table fields by source-lineage names.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-target-handler-probe-v1"
RANGES=[
 ("blendSavedScreen",0x00743e70,0x00744320),
 ("resolveComposite",0x00745d30,0x00745dc0),
]
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
def get(raw,secs,a,b):
    for s in secs:
      if s["va"]<=a and b<=s["va"]+s["rawSize"]:
        o=s["rawOffset"]+(a-s["va"]);return s,raw[o:o+b-a]
    raise E(f"unbacked 0x{a:x}..0x{b:x}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ranges=[]
    for label,start,end in RANGES:
      s,b=get(raw,secs,start,end);ins=list(md.disasm(b,start));req(ins and ins[0].address==start,f"{label}: decode start")
      absops=[];calls=[]
      for i in ins:
        for op in i.operands:
          if op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and op.mem.disp:
            absops.append({"instruction":row(i),"targetVa":f"0x{int(op.mem.disp)&0xffffffff:08x}","operandSize":op.size})
        if i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
          calls.append({"instruction":row(i),"targetVa":f"0x{int(i.operands[0].imm)&0xffffffff:08x}"})
      ranges.append({"label":label,"startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}",
        "section":s["name"],"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),
        "instructions":[row(i) for i in ins],"absoluteMemoryOperands":absops,"directCalls":calls})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact bytes + independently proven render-command handler VAs",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "ranges":ranges,
      "summary":{x["label"]:{"instructionCount":len(x["instructions"]),"absoluteMemoryOperandCount":len(x["absoluteMemoryOperands"]),"directCallCount":len(x["directCalls"])} for x in ranges},
      "proofBoundary":"Exact bounded current-client handler bytes/disassembly only. Render-command identities come from the independently proven handler table. No absolute operand is assigned gfxRenderTargets/image/width/height semantics until a separate dataflow projector closes it."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
