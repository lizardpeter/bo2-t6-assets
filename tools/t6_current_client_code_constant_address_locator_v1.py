#!/usr/bin/env python3
"""Locate current-client T6 code-constant address computation by exact machine signature.

The signature is taken from an independently decompiled T6 PC server function
named R_GetCodeConstant and is used only as a locator:
    lea eax,[esi+0x80]
    shl eax,4
    add eax,[edi]
    ret
No server address or symbol is promoted. A client hit must match exact bytes.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-constant-address-locator-v1"
SIG=bytes.fromhex("8d8680000000c1e0040307c3")
PRE=0x90
POST=0x30

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
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def raw_callers(raw,secs,target):
    out=[]
    for s in secs:
      if not s["exec"]:continue
      b=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      for p in range(len(b)-5):
        if b[p]!=0xe8:continue
        va=s["va"]+p;disp=struct.unpack_from("<i",b,p+1)[0]
        if ((va+5+disp)&0xffffffff)==target:
          out.append({"callVa":f"0x{va:08x}","bytes":b[p:p+5].hex(),"section":s["name"]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    for s in secs:
      if not s["exec"]:continue
      b=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      pos=0
      while True:
        rel=b.find(SIG,pos)
        if rel<0:break
        va=s["va"]+rel
        lo=max(0,rel-PRE);hi=min(len(b),rel+len(SIG)+POST)
        blob=b[lo:hi];start=s["va"]+lo
        ins=list(md.disasm(blob,start))
        sig_ins=[row(i) for i in ins if va<=i.address<va+len(SIG)]
        hits.append({
          "section":s["name"],"signatureVa":f"0x{va:08x}","signatureBytes":SIG.hex(),
          "contextStartVa":f"0x{start:08x}","contextBytes":len(blob),"contextSha256":hashlib.sha256(blob).hexdigest(),
          "instructions":[row(i) for i in ins],"signatureInstructions":sig_ins,
          "rawRel32Callers":raw_callers(raw,secs,va-PRE) # diagnostic only; exact function start unknown
        })
        pos=rel+1
    doc={
      "format":FORMAT,"authority":"SHA-classified current Plutonium client exact bytes; T6 server machine sequence used as locator only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"exactSignatureHitCount":len(hits)},
      "hits":hits,
      "proofBoundary":"Exact client signature presence and bounded disassembly only. The T6 server symbol name is not assigned to a client hit. Function start/callers, GfxCmdBufSourceState field meaning, runtime values, and historical-retail equivalence require later client-only proof."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for h in hits:print(h["signatureVa"],h["contextSha256"])
if __name__=="__main__":main()
