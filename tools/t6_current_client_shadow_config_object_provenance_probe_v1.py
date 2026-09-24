#!/usr/bin/env python3
"""Classify the object written by current-client function 0x00497450.

Retains exact caller argument setup and global per-index object construction around
0x02FB838C + arg1*0x284E0 + 0x13A8. This is a provenance probe; no source-state
identity is inferred from coincident offsets.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadow-config-object-provenance-probe-v1"
TARGET=0x00497450
CALLS=(0x00657b1c,0x0088a59c,0x0089f3bb,0x0089f4d3,0x0092aca4)
CTX=40
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
def rr(i): return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def secfor(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise E(f"VA 0x{va:x} not backed")
def context(raw,secs,va):
    s=secfor(secs,va);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    bb=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];ins=[i for i in md.disasm(bb,s["va"]) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==va),None);req(n is not None,f"0x{va:x} not decoded")
    lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
    return {"call":rr(ins[n]),"section":s["name"],"contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);calls=[]
    for va in CALLS:
        c=context(raw,secs,va);req(c["call"]["mnemonic"]=="call" and c["call"]["opStr"]=="0x497450",f"call drift {va:x}")
        calls.append(c)
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact callsite windows",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "target":{"functionVa":"0x00497450","perIndexStride":0x284e0,"globalPointerTableBaseVa":"0x02fb838c","subobjectOffset":0x13a8,
                "derivedWriteBase":"uint32(0x02FB838C + arg1*0x284E0) + 0x13A8"},
      "callers":calls,
      "summary":{"callerCount":len(calls)},
      "proofBoundary":"Exact caller windows and object-address arithmetic only. The object is deliberately not called source state, shadow state, or any retail source symbol. Coincident code-constant offsets inside this object are not provider proof."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2))
if __name__=="__main__": main()
