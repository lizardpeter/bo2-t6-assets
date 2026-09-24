#!/usr/bin/env python3
"""Recover the exact current-client source-state sampler-state initializer around 0x00455588.

The unresolved slot scans operate at byte granularity, but this initializer writes
multiple sampler-state bytes at once with dword stores. This proof retains the
whole INT3-bounded function, exact writes covering 0x160C..0x163F, their source
register provenance, and direct callers.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-sampler-state-initializer-v1"
ANCHOR=0x00455588
SEARCH=0x5000
CTX=32
LO=0x160C
HI=0x1640

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
    raise E(f"VA 0x{va:x} not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def body(raw,s,anchor):
    ro=s["rawOffset"]+anchor-s["va"];lo=max(s["rawOffset"],ro-SEARCH);hi=min(s["rawOffset"]+s["rawSize"],ro+SEARCH)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(raw[lo:hi],s["va"]+lo-s["rawOffset"]) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==anchor),None);req(n is not None,"anchor not decoded")
    p=-1
    for k in range(n-1,-1,-1):
        if ins[k].mnemonic=="int3":
            while k+1<n and ins[k+1].mnemonic=="int3":k+=1
            p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
        if ins[k].mnemonic=="int3":q=k;break
    out=ins[p+1:q];req(out,"empty function");return out
def callers(raw,secs,target):
    out=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
        if not s["exec"]:continue
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            if (int(i.operands[0].imm)&0xffffffff)!=target:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            out.append({"call":rr(i),"section":s["name"],"contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s=secfor(secs,ANCHOR);ins=body(raw,s,ANCHOR);st=ins[0].address;en=ins[-1].address+ins[-1].size
    writes=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    # Re-disassemble exact body with details.
    ro=s["rawOffset"]+st-s["va"];blob=raw[ro:ro+(en-st)];detail=list(md.disasm(blob,st))
    for i in detail:
        if not i.operands:continue
        op=i.operands[0]
        if op.type!=X86_OP_MEM:continue
        disp=int(op.mem.disp)
        if LO<=disp<HI:
            writes.append({"offset":disp,"widthBytes":op.size,"instruction":rr(i),
              "baseReg":md.reg_name(op.mem.base) if op.mem.base else None,
              "indexReg":md.reg_name(op.mem.index) if op.mem.index else None,"scale":op.mem.scale})
    covered={}
    for w in writes:
        for off in range(w["offset"],w["offset"]+w["widthBytes"]):
            if LO<=off<HI:covered.setdefault(off,[]).append(w["instruction"]["address"])
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact INT3-bounded source-state initializer bytes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{st:08x}","endVaExclusive":f"0x{en:08x}","section":s["name"],
        "instructionCount":len(ins),"instructions":[rr(i) for i in ins]},
      "samplerStateWrites":writes,
      "byteCoverage":{f"0x{k:04x}":v for k,v in sorted(covered.items())},
      "directCallers":callers(raw,secs,st),
      "summary":{"functionStartVa":f"0x{st:08x}","samplerRangeWriteCount":len(writes),
        "coveredByteCount":len(covered),"slot6StateByteCovered":0x1612 in covered,"slot16StateByteCovered":0x161c in covered,
        "directCallerCount":len(callers(raw,secs,st))},
      "proofBoundary":"Exact initializer function/write coverage only. A covered sampler-state byte proves some wider store writes that byte, but its final byte value and lifetime require source-register/value dataflow; image ownership and historical-retail equivalence remain separate."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
