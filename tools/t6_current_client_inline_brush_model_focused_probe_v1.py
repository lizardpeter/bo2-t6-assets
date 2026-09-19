#!/usr/bin/env python3
"""Focused exact-byte probe for current-client inline brush-model parse candidates.

The broad ASCII-star census identified two candidate paths with the engine-lineage
shape '*': advance string -> call common parser -> 16-bit entity-field store.
This probe retains complete bounded disassembly for those paths and the common
callee. It is intentionally a locator: semantics are promoted only by a later
projector that checks exact control/data flow.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-inline-brush-model-focused-probe-v1"
RANGES=[
 ("candidateA",0x007c3460,0x007c3540),
 ("candidateB",0x007c8a60,0x007c8b10),
 ("suffixParser",0x00a72fc0,0x00a73080),
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
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        secs.append((name,ib+rva,rs,ro))
    return ib,secs
def get(raw,secs,a,b):
    for name,va,rs,ro in secs:
        if va<=a and b<=va+rs:
            off=ro+(a-va);return name,off,raw[off:off+b-a]
    raise E(f"range 0x{a:x}..0x{b:x} not raw-backed")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32)
    ranges=[]
    for label,start,end in RANGES:
        sec,off,blob=get(raw,secs,start,end)
        ins=list(md.disasm(blob,start))
        req(ins and ins[0].address==start,f"{label}: decode did not start at range start")
        ranges.append({"label":label,"startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}",
          "section":sec,"rawOffset":off,"bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),
          "instructions":[row(i) for i in ins]})
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "ranges":ranges,
      "proofBoundary":"Exact bounded current-client bytes/disassembly only. Range labels are investigation labels, not source symbols. No atoi identity, F_MODEL identity, brushmodel field semantics, MapEnt *N meaning, or historical-retail equivalence is promoted by this probe alone."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({x["label"]:{"sha256":x["sha256"],"instructionCount":len(x["instructions"])} for x in ranges},indent=2))
if __name__=="__main__":main()
