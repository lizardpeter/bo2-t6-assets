#!/usr/bin/env python3
"""Focused exact current-client probe for both callers of 0x009BEA80 and its callbacks."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FMT="t6-current-client-spot-shadow-writer-call-contract-probe-v1"
RANGES=[
 ("callerA",0x009BF660,0x009BF754),
 ("callerB",0x009C0180,0x009C022C),
 ("callbackA",0x009BEA10,0x009BEA40),
 ("callbackB",0x009BEA40,0x009BEA80),
 ("writerEntry",0x009BEA80,0x009BEBE0),
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
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro})
    return ib,secs
def blob(raw,secs,a,b):
    for s in secs:
        if s["va"]<=a and b<=s["va"]+s["rawSize"]:
            o=s["rawOffset"]+(a-s["va"]);return s,raw[o:o+b-a]
    raise E(f"unbacked {a:x}..{b:x}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def one(raw,secs,label,a,b):
    s,bb=blob(raw,secs,a,b);ins=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(bb,a))
    return {"label":label,"startVa":f"0x{a:08x}","endVaExclusive":f"0x{b:08x}","section":s["name"],
      "bytes":len(bb),"sha256":hashlib.sha256(bb).hexdigest(),"instructions":[row(i) for i in ins]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);ranges=[one(raw,secs,*x) for x in RANGES]
    doc={"format":FMT,"authority":"SHA-classified current client exact bounded disassembly",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "ranges":ranges,
      "proofBoundary":"Exact bounded caller/callback/writer-entry bytes only. Range labels are investigation labels, not source symbols. Later projector must prove argument positions and EDI/ESI ownership from exact instruction dataflow; no physical shadowmap units or historical-retail equivalence are inferred."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({x["label"]:{"sha256":x["sha256"],"instructionCount":len(x["instructions"])} for x in ranges},indent=2))
if __name__=="__main__":main()
