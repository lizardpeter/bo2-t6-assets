#!/usr/bin/env python3
"""Focused current-client probe for spotShadowmapPixelAdjust enum 60 version writer."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-spot-shadow-pixel-adjust-version-writer-probe-v1"
START=0x009d44d0
END=0x009d4750
TARGET=START
class E(RuntimeError):pass
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
def region(raw,secs,a,b):
    for s in secs:
      if s["va"]<=a and b<=s["va"]+s["rawSize"]:
        o=s["rawOffset"]+a-s["va"];return s,raw[o:o+b-a]
    raise E("range not raw-backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def callers(raw,secs,target):
    out=[]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
      if not s["exec"]:continue
      bb=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      for i in md.disasm(bb,s["va"]):
        if i.id and i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM and (int(i.operands[0].imm)&0xffffffff)==target:
          out.append(rr(i))
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);sec,bb=region(raw,secs,START,END)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=[rr(i) for i in md.disasm(bb,START)]
    # Freeze expected exact enum60 value/version storage occurrences in this bounded body.
    valueAddrs=[];versionAddrs=[]
    for x in ins:
      op=x["opStr"].lower()
      if any(f"+ 0x{0xbc0+j*4:x}" in op for j in range(4)) or any(f"[{r} + 0xbc" in op for r in ("eax","ebx","ecx","edx","esi","edi")):
        valueAddrs.append(x["address"])
      if "0x1858" in op:versionAddrs.append(x["address"])
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact bounded disassembly",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":sec["name"],"sha256":hashlib.sha256(bb).hexdigest(),"instructions":ins},
      "summary":{"instructionCount":len(ins),"directCallerCount":len(callers(raw,secs,TARGET)),"enum60VersionOffsetInstructionCount":len(versionAddrs)},
      "directCallers":callers(raw,secs,TARGET),"enum60VersionOffsetInstructions":versionAddrs,
      "proofBoundary":"Exact current-client bounded bytes/disassembly and direct-call operands only. The function is selected because an independent exact storage census observed enum60 version offset 0x1858 here. No provider semantic, physical unit, callsite role, or historical-retail equivalence is promoted by this probe alone."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
