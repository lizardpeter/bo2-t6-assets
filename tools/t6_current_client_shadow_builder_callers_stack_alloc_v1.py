#!/usr/bin/env python3
"""Freeze callers of 0x009AF970 and the exact 0x00A73040 stack-growth helper.

The source-state builder's high-stack reads sit above a 0x1564-byte dynamic
allocation. This proof closes the stack transform and all direct caller setup so
slot-16 image provenance can be mapped back to caller arguments without guessing.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadow-builder-callers-stack-alloc-v1"
TARGET=0x009AF970
ALLOC=0x00A73040
CTX=36
WINDOW=0x200

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
def secfor(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"VA {va:x} not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def decode_window(raw,s,va,size):
    ro=s["rawOffset"]+va-s["va"]; md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    return [i for i in md.disasm(raw[ro:ro+size],va) if i.id]
def callers(raw,secs,target):
    out=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
      if not s["exec"]:continue
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
        if (int(i.operands[0].imm)&0xffffffff)!=target:continue
        out.append({"call":rr(i),"section":s["name"],
          "contextBefore":[rr(x) for x in ins[max(0,n-CTX):n]],
          "contextAfter":[rr(x) for x in ins[n+1:min(len(ins),n+CTX+1)]]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw)
    target_sec=secfor(secs,TARGET); pro=decode_window(raw,target_sec,TARGET,0x30)
    req(pro[0].address==TARGET and pro[0].mnemonic=="mov" and pro[0].op_str=="eax, 0x1564","builder allocation-size prologue drift")
    req(pro[1].mnemonic=="call" and pro[1].op_str=="0xa73040","builder allocation helper call drift")
    alloc_sec=secfor(secs,ALLOC); alloc_ins=decode_window(raw,alloc_sec,ALLOC,WINDOW)
    # Keep through first RET plus a short safety tail.
    ret_i=next((i for i,x in enumerate(alloc_ins) if x.mnemonic.startswith("ret")),None);req(ret_i is not None,"alloc helper has no ret")
    alloc_ins=alloc_ins[:ret_i+1]
    cc=callers(raw,secs,TARGET)
    doc={"format":FORMAT,"authority":"SHA-classified exact builder prologue, stack helper body and direct caller denominator",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "builder":{"entryVa":f"0x{TARGET:08x}","allocationRequestBytes":0x1564,"prologue":[rr(x) for x in pro[:8]]},
      "stackHelper":{"entryVa":f"0x{ALLOC:08x}","instructionCount":len(alloc_ins),"instructions":[rr(x) for x in alloc_ins]},
      "callers":cc,
      "summary":{"directCallerCount":len(cc),"stackHelperInstructionCount":len(alloc_ins)},
      "proofBoundary":"Closes exact caller denominator and stack-allocation mechanism. Mapping a post-allocation ESP displacement to a pre-allocation argument is permitted only where the helper body proves the corresponding ESP delta; semantic resource identity still requires caller argument provenance."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
