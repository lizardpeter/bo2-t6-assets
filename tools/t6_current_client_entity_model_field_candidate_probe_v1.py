#!/usr/bin/env python3
"""Exact current-client probe for the generic-field/model branch near 0x005c23f0."""
from __future__ import annotations
import argparse,hashlib,json,string,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-entity-model-field-candidate-probe-v1"
RANGES=[
 ("fieldSwitch",0x005c2200,0x005c2440),
 ("legacyModelNameHelper",0x0048f5c0,0x0048f680),
 ("modelSetterA",0x0040c680,0x0040c740),
 ("modelSetterB",0x00559490,0x00559570),
 ("decimalWrapper",0x00a73004,0x00a73025),
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
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"characteristics":ch})
    return ib,secs
def locate(secs,va,n=1):
    for s in secs:
      if s["va"]<=va and va+n<=s["va"]+s["rawSize"]: return s,s["rawOffset"]+va-s["va"]
    raise E(f"unbacked VA 0x{va:x}+{n}")
def cstr(raw,secs,va,limit=400):
    try:s,o=locate(secs,va)
    except E:return None
    end=min(s["rawOffset"]+s["rawSize"],o+limit);z=raw.find(b"\0",o,end)
    if z<0 or z==o:return None
    b=raw[o:z]
    if len(b)<4 or any(chr(x) not in string.printable for x in b):return None
    return {"va":f"0x{va:08x}","section":s["name"],"text":b.decode("ascii","replace"),"bytes":b.hex()}
def one(raw,secs,label,a,b):
    s,o=locate(secs,a,b-a);bb=raw[o:o+b-a];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(bb,a)); rows=[]; literals={}
    for i in ins:
      rows.append({"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str})
      for op in i.operands:
        if op.type==X86_OP_IMM:
          v=int(op.imm)&0xffffffff
          cs=cstr(raw,secs,v)
          if cs:literals[v]=cs
    return {"label":label,"startVa":f"0x{a:08x}","endVaExclusive":f"0x{b:08x}","section":s["name"],
      "bytes":len(bb),"sha256":hashlib.sha256(bb).hexdigest(),"instructions":rows,"referencedPrintableStrings":[literals[k] for k in sorted(literals)]}
def call_xrefs(raw,secs,lo,hi):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;out=[]
    for s in secs:
      if not s["characteristics"]&0x20000000:continue
      bb=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      for i in md.disasm(bb,s["va"]):
        if i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
          t=int(i.operands[0].imm)&0xffffffff
          if lo<=t<hi:out.append({"callAddress":f"0x{i.address:08x}","targetVa":f"0x{t:08x}","bytes":i.bytes.hex()})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw);ranges=[one(raw,secs,*r) for r in RANGES]
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "ranges":ranges,"directCallsIntoFieldSwitchRange":call_xrefs(raw,secs,0x005c2200,0x005c2440),
      "proofBoundary":"Exact bounded current-client disassembly, direct call operands, and raw-backed printable literals only. Investigation labels are not source symbols. The model-field branch is not yet promoted as MapEnt spawn parsing; helper names/runtime meanings and historical-retail equivalence remain unclaimed."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"ranges":{x["label"]:{"instructions":len(x["instructions"]),"strings":[s["text"] for s in x["referencedPrintableStrings"]]} for x in ranges},"callerCount":len(doc["directCallsIntoFieldSwitchRange"])},indent=2))
if __name__=="__main__":main()
