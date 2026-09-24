#!/usr/bin/env python3
"""Freeze the strongest enum-60 +4 constructor containing 0x00736C7C."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-enum60-constructor-function-v1"
ANCHOR=0x00736C7C
CTX=48
SEARCH=0x10000

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
    raise E("VA not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def bounded(raw,s,anchor):
    ro=s["rawOffset"]+anchor-s["va"];lo=max(s["rawOffset"],ro-SEARCH);hi=min(s["rawOffset"]+s["rawSize"],ro+SEARCH)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(raw[lo:hi],s["va"]+lo-s["rawOffset"]) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==anchor),None);req(n is not None,"anchor missing")
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
        out.append({"call":rr(i),"section":s["name"],
          "contextBefore":[rr(x) for x in ins[max(0,n-CTX):n]],
          "contextAfter":[rr(x) for x in ins[n+1:min(len(ins),n+CTX+1)]]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s=secfor(secs,ANCHOR);ins=bounded(raw,s,ANCHOR)
    start=ins[0].address;cc=callers(raw,secs,start)
    n=next(i for i,x in enumerate(ins) if x.address==ANCHOR)
    # Retain all writes through the apparent record base EBX for compact ABI inspection.
    record=[rr(x) for x in ins if "[ebx" in x.op_str]
    calls=[rr(x) for x in ins if x.mnemonic=="call"]
    doc={"format":FORMAT,"authority":"SHA-classified exact bounded enum60 +4 constructor and callers",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{start:08x}","endVaExclusive":f"0x{ins[-1].address+ins[-1].size:08x}",
                  "instructionCount":len(ins),"anchor":rr(ins[n]),"instructions":[rr(x) for x in ins]},
      "recordBaseReferences":record,"calls":calls,"callers":cc,
      "summary":{"instructionCount":len(ins),"callerCount":len(cc),"recordBaseReferenceCount":len(record),"callCount":len(calls)},
      "proofBoundary":"Closes the strongest enum60 +4 constructor body and direct caller denominator. Type-1 ABI membership and downstream runtime-record reachability remain separate gates until the +0/+2/+8.. lane layout and consumer path are matched exactly."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
