#!/usr/bin/env python3
"""Freeze exact current-client gameTime arithmetic and embedded constants.

The write-cluster proof already establishes exact enum-25 value/version
destinations. This probe captures the bounded arithmetic feeding those stores
and decodes every absolute scalar constant it depends on. It intentionally
stops short of naming the arithmetic until a projector verifies the formula.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-gametime-arithmetic-probe-v1"
START=0x00733c90
END=0x00733d78
CONST_VAS=[0x00c59da4,0x00bd1200,0x00d2b3c8,0x00c63b24]
SOURCE_VA=0x03a3852c
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
def read(raw,secs,va,n):
    for s in secs:
      if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:
        o=s["rawOffset"]+va-s["va"];return s,raw[o:o+n]
    raise E(f"VA 0x{va:08x}+{n} not raw-backed")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def scalar(raw,secs,va):
    s,b=read(raw,secs,va,4)
    u=struct.unpack("<I",b)[0];f=struct.unpack("<f",b)[0]
    return {"va":f"0x{va:08x}","section":s["name"],"bytes":b.hex(),"u32":u,"u32Hex":f"0x{u:08x}","float32":f}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);sec,bb=read(raw,secs,START,END-START)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(bb,START));req(ins and ins[0].address==START,"decode start drift")
    refs=[]
    for i in ins:
      for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and op.mem.disp:
          v=int(op.mem.disp)&0xffffffff
          if v in CONST_VAS or v==SOURCE_VA:refs.append({"instruction":row(i),"targetVa":f"0x{v:08x}"})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact bytes/data",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "range":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":sec["name"],"bytes":len(bb),"sha256":hashlib.sha256(bb).hexdigest(),"instructions":[row(i) for i in ins]},
      "sourceScalar":{"va":f"0x{SOURCE_VA:08x}","references":[x for x in refs if x["targetVa"]==f"0x{SOURCE_VA:08x}"]},
      "embeddedConstants":[scalar(raw,secs,v) for v in CONST_VAS],
      "selectedAbsoluteReferences":refs,
      "summary":{"instructionCount":len(ins),"embeddedConstantCount":len(CONST_VAS),
                 "hasFsincos":any(i.mnemonic=="fsincos" for i in ins),
                 "sourceScalarReferenceCount":sum(x["targetVa"]==f"0x{SOURCE_VA:08x}" for x in refs)},
      "proofBoundary":"Exact bounded arithmetic bytes and raw-backed scalar constants only. The source scalar and function are not named here; no floor/fract/trigonometric formula, update timing, scene-time producer, or historical-retail equivalence is promoted until a dedicated semantic projector closes the instruction dataflow."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":doc["summary"],"constants":doc["embeddedConstants"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
