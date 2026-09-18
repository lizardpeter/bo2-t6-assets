#!/usr/bin/env python3
"""Find exact current-client direct callers of linked-record insertion entry 0x007FD8C0."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM

CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET=0x007FD8C0

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];coff=p+4
    n=struct.unpack_from("<H",raw,coff+2)[0];os=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+os;out=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        if ch&0x20000000:out.append((name,ib+rva,ro,rs))
    return ib,out

def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=CLIENT:raise SystemExit(f"unexpected client {sha}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    allins=[]
    for name,va,ro,rs in secs:
        allins.extend(i for i in md.disasm(raw[ro:ro+rs],va) if i.id)
    hits=[]
    for idx,i in enumerate(allins):
        if i.mnemonic!="call" or not i.operands or i.operands[0].type!=X86_OP_IMM:continue
        if (i.operands[0].imm&0xffffffff)!=TARGET:continue
        hits.append({"call":row(i),"contextBefore":[row(z) for z in allins[max(0,idx-32):idx]],"contextAfter":[row(z) for z in allins[idx+1:idx+17]]})
    if not hits:raise SystemExit("no direct callers")
    out={"format":"t6-current-client-linked-record-insertion-callers-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"sha256":sha,"bytes":len(raw),"imageBaseHex":f"0x{ib:08x}"},"target":"0x007fd8c0","directCallCount":len(hits),"callers":hits,"proofBoundary":"Exact direct CALL xrefs to current-client address 0x007FD8C0 only. Stack-argument semantics are not promoted until independently projected from these bytes."}
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n";a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"directCallCount":len(hits),"sha256":hashlib.sha256(payload.encode()).hexdigest()},indent=2))
if __name__=="__main__":main()
