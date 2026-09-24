#!/usr/bin/env python3
"""Locate exact current-client references to the spot-shadow live writer VA 0x009BEA80.

Admits:
- decoded executable immediates / absolute memory displacements equal to the VA;
- raw 32-bit pointer occurrences in non-executable/raw-backed sections;
- executable raw byte occurrences only as diagnostics, never xrefs.

No provider semantic is promoted here.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import deque
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET=0x009BEA80
PRE=20
POST=36
FMT="t6-current-client-spot-shadow-writer-entry-xrefs-v1"

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
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000),"chars":ch})
    return ib,secs
def md():
    d=Cs(CS_ARCH_X86,CS_MODE_32);d.detail=True;d.skipdata=True;return d
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def following(raw,sec,va,n=POST):
    off=sec["rawOffset"]+(va-sec["va"]);end=min(sec["rawOffset"]+sec["rawSize"],off+512)
    out=[]
    for i in md().disasm(raw[off:end],va):
        if i.id==0:continue
        out.append(row(i))
        if len(out)>=n:break
    return out
def decoded(raw,secs):
    out=[]
    for s in secs:
        if not s["exec"]:continue
        prev=deque(maxlen=PRE)
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        for i in md().disasm(blob,s["va"]):
            if i.id==0:
                prev.clear();continue
            hits=[]
            for oi,op in enumerate(i.operands):
                if op.type==X86_OP_IMM and (int(op.imm)&0xffffffff)==TARGET:
                    hits.append({"operandIndex":oi,"kind":"immediate"})
                elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and (int(op.mem.disp)&0xffffffff)==TARGET:
                    hits.append({"operandIndex":oi,"kind":"absolute-memory-displacement"})
            if hits:
                out.append({"instruction":row(i),"section":s["name"],"operands":hits,"before":list(prev),"after":following(raw,s,i.address)})
            prev.append(row(i))
    return out
def rawptr(raw,secs):
    needle=struct.pack("<I",TARGET);out=[]
    for s in secs:
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];pos=0
        while True:
            i=blob.find(needle,pos)
            if i<0:break
            out.append({"section":s["name"],"sectionExecutable":s["exec"],"fileOffset":s["rawOffset"]+i,"va":f"0x{s['va']+i:08x}"})
            pos=i+1
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);dx=decoded(raw,secs);rp=rawptr(raw,secs)
    doc={"format":FMT,"authority":"SHA-classified current client exact decoded operands and raw-backed data only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "targetVa":f"0x{TARGET:08x}","decodedOperandXrefs":dx,"rawPointerOccurrences":rp,
      "summary":{"decodedOperandXrefCount":len(dx),"rawPointerOccurrenceCount":len(rp),
                 "nonExecutableRawPointerCount":sum(not x["sectionExecutable"] for x in rp),
                 "executableRawPointerCount":sum(x["sectionExecutable"] for x in rp)},
      "proofBoundary":"Decoded executable operands and raw-backed dword occurrences only. Raw executable byte occurrences are diagnostic and are not promoted as xrefs. A non-executable table pointer still does not by itself identify the table or caller semantics; later projector must close table ownership and invocation dataflow."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
