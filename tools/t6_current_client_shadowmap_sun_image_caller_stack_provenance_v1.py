#!/usr/bin/env python3
"""Exact caller-window and stack-reference census for shadowmapSamplerSun image writer."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM
SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FMT="t6-current-client-shadowmap-sun-image-caller-stack-provenance-v1"
START=0x009AF970
END=0x009AFC00
CALL=0x009AF9D8
class E(RuntimeError):pass
def req(v,m):
    if not v:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0]
    o=c+20;ib=struct.unpack_from("<I",raw,o+28)[0];sh=o+os;ss=[]
    for i in range(n):
        q=sh+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        ss.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,ss
def locate(ss,va,n):
    for s in ss:
        if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:return s,s["rawOffset"]+va-s["va"]
    raise E("window not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,ss=pe(raw);sec,off=locate(ss,START,END-START)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(raw[off:off+END-START],START));by={i.address:i for i in ins}
    c=by.get(CALL);req(c and c.mnemonic=="call" and c.op_str=="0x9a7a30","call drift")
    stack=[]
    for i in ins:
        refs=[]
        for oi,op in enumerate(i.operands):
            if op.type==X86_OP_MEM and op.mem.base and md.reg_name(op.mem.base) in {"esp","ebp"}:
                refs.append({"operandIndex":oi,"baseReg":md.reg_name(op.mem.base),"indexReg":md.reg_name(op.mem.index) if op.mem.index else None,
                             "scale":op.mem.scale,"disp":int(op.mem.disp),"size":int(op.size)})
        if refs:stack.append({"instruction":rr(i),"stackRefs":refs})
    call_idx=next(i for i,x in enumerate(ins) if x.address==CALL)
    doc={"format":FMT,"authority":"SHA-classified exact current-client caller window and stack-memory operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "window":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":sec["name"]},
      "instructions":[rr(i) for i in ins],
      "stackReferences":stack,
      "writerCall":{"call":rr(c),"contextBefore":[rr(x) for x in ins[max(0,call_idx-90):call_idx]],
                    "contextAfter":[rr(x) for x in ins[call_idx+1:min(len(ins),call_idx+40)]]},
      "summary":{"instructionCount":len(ins),"stackReferenceInstructionCount":len(stack),"writerCallClosed":True},
      "proofBoundary":"Exact caller-window and stack-reference locator only. Stack-slot lifetime, argument meaning and resource identity require a subsequent dataflow reduction."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
