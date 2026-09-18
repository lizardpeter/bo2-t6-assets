#!/usr/bin/env python3
"""Persist exact current-client disassembly for helper 0x00A72BF0 used by relink swap."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x00A72BF0
MAXEND=0x00A72D80

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];coff=p+4
    n=struct.unpack_from("<H",raw,coff+2)[0];os=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+os;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        secs.append((name,ib+rva,max(vs,rs),ro,rs))
    return ib,secs

def rawoff(secs,va):
    for name,base,span,ro,rs in secs:
        if base<=va<base+span:return name,ro+(va-base)
    raise SystemExit(f"VA outside sections: 0x{va:x}")

def row(i): return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=CLIENT:raise SystemExit(f"unexpected client {sha}")
    ib,secs=pe(raw);sec,off=rawoff(secs,START)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.skipdata=True
    ins=[]
    end=None
    for i in md.disasm(raw[off:off+(MAXEND-START)],START):
        if not i.id: continue
        ins.append(row(i))
        if i.mnemonic.startswith("ret"):
            end=i.address+len(i.bytes);break
    if end is None:raise SystemExit("no return before bound")
    out={"format":"t6-current-client-relink-payload-helper-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"sha256":sha,"bytes":len(raw),"imageBaseHex":f"0x{ib:08x}"},"helper":{"entry":"0x00a72bf0","section":sec,"endExclusive":f"0x{end:08x}","bytes":end-START,"instructions":ins},"proofBoundary":"Exact bounded current-client helper bytes only. No source-symbol name or semantic role is promoted beyond the fact that relink helper 0x007fd520 calls this address with payload-related arguments."}
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n";a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"entry":out["helper"]["entry"],"bytes":out["helper"]["bytes"],"instructionCount":len(ins),"sha256":hashlib.sha256(payload.encode()).hexdigest()},indent=2))
if __name__=="__main__":main()
