#!/usr/bin/env python3
"""Freeze complete current-client functions containing the four generic runtime-record dispatcher calls."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-generic-runtime-record-caller-functions-v1"
ANCHORS=(0x00732CDE,0x0073A031,0x0074A67D,0x00780356)
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
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def body(raw,s,anchor):
    ro=s["rawOffset"]+anchor-s["va"];lo=max(s["rawOffset"],ro-SEARCH);hi=min(s["rawOffset"]+s["rawSize"],ro+SEARCH)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(raw[lo:hi],s["va"]+lo-s["rawOffset"]) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==anchor),None);req(n is not None,f"anchor {anchor:x} not decoded")
    p=-1
    for k in range(n-1,-1,-1):
        if ins[k].mnemonic=="int3":
            while k+1<n and ins[k+1].mnemonic=="int3":k+=1
            p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
        if ins[k].mnemonic=="int3":q=k;break
    out=ins[p+1:q];req(out,f"empty body {anchor:x}");return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows=[]
    for anchor in ANCHORS:
        s=next(x for x in secs if x["exec"] and x["va"]<=anchor<x["va"]+x["rawSize"])
        ins=body(raw,s,anchor);start=ins[0].address;end=ins[-1].address+ins[-1].size
        n=next(i for i,x in enumerate(ins) if x.address==anchor)
        # Retain full function plus a compact memory/control view for easier projector work.
        interesting=[rr(x) for x in ins if "[" in x.op_str or x.mnemonic in {"call","jmp","je","jne","jz","jnz","push","pop","lea"}]
        rows.append({"anchorVa":f"0x{anchor:08x}","startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}",
          "instructionCount":len(ins),"callInstructionIndex":n,"section":s["name"],
          "sha256":hashlib.sha256(b"".join(x.bytes for x in ins)).hexdigest(),
          "interestingInstructions":interesting,"instructions":[rr(x) for x in ins]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact INT3-bounded functions containing all direct dispatcher calls",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"functionCount":len(rows),"functions":[{"anchorVa":x["anchorVa"],"startVa":x["startVa"],"endVaExclusive":x["endVaExclusive"],"instructionCount":x["instructionCount"]} for x in rows]},
      "functions":rows,
      "proofBoundary":"Exact caller-function bytes only. Record-stream field ownership and per-enum type-1 reachability remain to be derived from these functions; no semantic names are inferred from field offsets."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
