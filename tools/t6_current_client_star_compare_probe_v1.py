#!/usr/bin/env python3
"""Enumerate SHA-classified current-client x86 comparisons against ASCII '*'.

Current-client discovery only. Candidate proximity does not source-name a parser.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM

CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];coff=p+4
    n=struct.unpack_from("<H",raw,coff+2)[0];os=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+os;out=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        if ch&0x20000000:out.append((name,ib+rva,ro,rs))
    return ib,out

def row(i):
    return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=CLIENT:raise SystemExit(f"unexpected client {sha}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[]
    for name,va,ro,rs in secs:
        ins.extend(i for i in md.disasm(raw[ro:ro+rs],va) if i.id)
    hits=[]
    for k,i in enumerate(ins):
        if i.mnemonic not in ("cmp","test"):continue
        if not any(op.type==X86_OP_IMM and (int(op.imm)&0xffffffff)==0x2a for op in i.operands):continue
        hits.append({"instruction":row(i),"contextBefore":[row(x) for x in ins[max(0,k-20):k]],"contextAfter":[row(x) for x in ins[k+1:k+31]]})
    out={"format":"t6-current-client-star-compare-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"sha256":sha,"bytes":len(raw),"imageBaseHex":f"0x{ib:08x}"},"summary":{"starCompareCandidateCount":len(hits)},"candidates":hits,"proofBoundary":"Exact executable cmp/test instructions with immediate ASCII '*' and bounded decoded context only. Candidates are not source-named and no *N inline-model semantic is promoted from this census alone."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
