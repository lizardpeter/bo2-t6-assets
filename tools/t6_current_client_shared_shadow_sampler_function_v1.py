#!/usr/bin/env python3
"""Recover the full current-client function containing the shared slot-7/slot-16 sampler cluster.

Purpose: prove the provenance of EBX around writes to the derived code-image/state
arrays. This is an exact function/caller probe only; provider promotion remains a
separate projector.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shared-shadow-sampler-function-v1"
ANCHOR=0x0072D600
SEARCH=0x5000

class E(RuntimeError): pass
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
def secfor(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise E(f"VA 0x{va:x} not backed")
def rr(i): return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def full_function(raw,s,anchor):
    ro=s["rawOffset"]+anchor-s["va"];lo=max(s["rawOffset"],ro-SEARCH);hi=min(s["rawOffset"]+s["rawSize"],ro+SEARCH)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(raw[lo:hi],s["va"]+lo-s["rawOffset"]) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==anchor),None);req(n is not None,"anchor not decoded")
    p=-1
    for k in range(n-1,-1,-1):
        if ins[k].mnemonic=="int3":
            while k+1<n and ins[k+1].mnemonic=="int3": k+=1
            p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
        if ins[k].mnemonic=="int3":
            q=k;break
    body=ins[p+1:q];req(body,"empty function")
    return body
def callers(raw,secs,target):
    out=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
        if not s["exec"]:continue
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            if (int(i.operands[0].imm)&0xffffffff)!=target:continue
            lo=max(0,n-36);hi=min(len(ins),n+37)
            out.append({"call":rr(i),"section":s["name"],"contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s=secfor(secs,ANCHOR);ins=full_function(raw,s,ANCHOR);start=ins[0].address;end=ins[-1].address+ins[-1].size
    calls=callers(raw,secs,start)
    # Preserve all instructions touching the derived slot-7/slot-16 image/state offsets.
    wanted={0xd4c,0xd70,0xe13,0xe1c}
    touches=[]
    for i in ins:
        op=i.op_str.lower()
        for d in wanted:
            if f"0x{d:x}" in op:
                touches.append({"displacement":d,"instruction":rr(i)})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact INT3-bounded function bytes + direct rel32 callers",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}","anchorVa":f"0x{ANCHOR:08x}",
                  "section":s["name"],"instructions":[rr(i) for i in ins]},
      "slotTouches":touches,"directCallers":calls,
      "summary":{"functionStartVa":f"0x{start:08x}","instructionCount":len(ins),"slotTouchCount":len(touches),"directCallerCount":len(calls)},
      "proofBoundary":"Exact current-client function and direct-call windows only. EBX/source-state identity, code-image slot semantics, sampler-state byte meanings, resource provenance, historical-retail equivalence and framebuffer effects remain unpromoted until a separate exact dataflow projector proves them."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__": main()
