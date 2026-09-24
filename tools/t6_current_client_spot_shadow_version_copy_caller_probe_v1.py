#!/usr/bin/env python3
"""Trace the sole exact caller of the enum60 state-copy routine at 0x009D44D0."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-spot-shadow-version-copy-caller-probe-v1"
CALL_VA=0x009d4928
CALLEE=0x009d44d0
SEARCH_PAD=0x3000
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
def getsec(secs,va):
    for s in secs:
      if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"VA 0x{va:x} not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def function_around(raw,s,va):
    ro=s["rawOffset"]+(va-s["va"]);lo=max(s["rawOffset"],ro-SEARCH_PAD);hi=min(s["rawOffset"]+s["rawSize"],ro+SEARCH_PAD)
    bb=raw[lo:hi];base=s["va"]+(lo-s["rawOffset"])
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(bb,base) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==va),None);req(n is not None,"call VA not decoded exactly")
    p=-1
    for k in range(n-1,-1,-1):
      if ins[k].mnemonic=="int3":
        while k+1<n and ins[k+1].mnemonic=="int3":k+=1
        p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
      if ins[k].mnemonic=="int3":q=k;break
    body=ins[p+1:q];req(body,"empty derived caller body")
    return body
def direct_callers(raw,secs,target):
    out=[]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
      if not s["exec"]:continue
      bb=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      for i in md.disasm(bb,s["va"]):
        if i.id and i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM and (int(i.operands[0].imm)&0xffffffff)==target:
          out.append(rr(i))
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s=getsec(secs,CALL_VA);body=function_around(raw,s,CALL_VA)
    call=[i for i in body if i.address==CALL_VA];req(len(call)==1,"call instruction missing")
    ci=call[0];req(ci.mnemonic=="call" and ci.op_str==f"0x{CALLEE:x}","callee drift")
    start=body[0].address;end=body[-1].address+body[-1].size
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact caller function derived from local INT3 padding + exact rel32 callee",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "callerFunction":{"startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}","section":s["name"],
        "sha256":hashlib.sha256(raw[s["rawOffset"]+start-s["va"]:s["rawOffset"]+end-s["va"]]).hexdigest(),
        "callVa":f"0x{CALL_VA:08x}","calleeVa":f"0x{CALLEE:08x}","instructions":[rr(i) for i in body]},
      "directCallersToCallerEntry":direct_callers(raw,secs,start),
      "summary":{"callerFunctionStartVa":f"0x{start:08x}","instructionCount":len(body),"upstreamDirectCallerCount":len(direct_callers(raw,secs,start))},
      "proofBoundary":"Exact current-client caller extent, bytes and call operands only. The callee is already proven as a large state-copy routine containing enum60 version offset 0x1858. This probe does not yet identify the caller arguments as specific source-state generations or promote enum60 physical provider semantics."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
