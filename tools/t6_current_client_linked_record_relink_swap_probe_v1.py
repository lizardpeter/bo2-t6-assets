#!/usr/bin/env python3
"""Persist exact disassembly for the current-client linked-record relink/swap closure."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
RANGES=[
 ("directLookup",0x00479c40,0x00479cdc),
 ("swapHelper",0x007fd4b0,0x007fd5b0),
 ("insertionPath",0x007fd8c0,0x007fdd30),
]

def sections(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];coff=p+4
    n=struct.unpack_from("<H",raw,coff+2)[0];os=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+os;out=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        out.append((name,ib+rva,vs,ro,rs))
    return ib,out

def raw_slice(raw,secs,lo,hi):
    for name,va,vs,ro,rs in secs:
        span=max(vs,rs)
        if lo>=va and hi<=va+span:
            off=ro+(lo-va)
            return name,raw[off:off+(hi-lo)]
    raise SystemExit(f"range 0x{lo:x}..0x{hi:x} not in one section")

def row(i):
    return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=CLIENT: raise SystemExit(f"unexpected client {sha}")
    ib,secs=sections(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.skipdata=True
    out={"format":"t6-current-client-linked-record-relink-swap-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"sha256":sha,"bytes":len(raw),"imageBaseHex":f"0x{ib:08x}"},"ranges":[]}
    for name,lo,hi in RANGES:
        sec,b=raw_slice(raw,secs,lo,hi)
        ins=[row(i) for i in md.disasm(b,lo) if i.id]
        if not ins: raise SystemExit(f"empty {name}")
        out["ranges"].append({"name":name,"start":f"0x{lo:08x}","endExclusive":f"0x{hi:08x}","section":sec,"instructions":ins})
    out["proofBoundary"]="Exact current-client bytes for bounded functions/ranges only. Semantic names in range labels are organizational and do not promote historical-retail source symbols."
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n";a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"ranges":len(out["ranges"]),"instructionCounts":{r["name"]:len(r["instructions"]) for r in out["ranges"]},"sha256":hashlib.sha256(payload.encode()).hexdigest()},indent=2,sort_keys=True))
if __name__=="__main__": main()
