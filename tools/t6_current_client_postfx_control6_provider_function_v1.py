#!/usr/bin/env python3
"""Exact current-client function/caller probe for the postFxControl6 writer at 0x7685D6."""
from __future__ import annotations
import argparse,hashlib,json,string,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-postfx-control6-provider-function-v1"
TARGET=0x007685d6
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
def secva(secs,va):
    for s in secs:
      if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked VA 0x{va:08x}")
def cstr(raw,secs,va,limit=240):
    try:s=secva(secs,va)
    except:return None
    o=s["rawOffset"]+va-s["va"];end=min(o+limit,s["rawOffset"]+s["rawSize"]);z=raw.find(b"\0",o,end)
    if z<=o:return None
    b=raw[o:z]
    try:t=b.decode("ascii")
    except:return None
    if len(t)<4 or any(ch not in string.printable for ch in t):return None
    return {"va":f"0x{va:08x}","section":s["name"],"text":t,"bytes":b.hex()}
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s=secva(secs,TARGET);to=s["rawOffset"]+TARGET-s["va"]
    # Find >=4-byte INT3 fences. Function starts immediately after prior fence and ends before next.
    lo=to
    while lo>s["rawOffset"]+4 and raw[lo-4:lo]!=b"\xcc"*4:lo-=1
    req(raw[lo-4:lo]==b"\xcc"*4,"prior INT3 fence not found")
    hi=to;lim=s["rawOffset"]+s["rawSize"]-4
    while hi<lim and raw[hi:hi+4]!=b"\xcc"*4:hi+=1
    req(raw[hi:hi+4]==b"\xcc"*4,"following INT3 fence not found")
    sva=s["va"]+lo-s["rawOffset"];eva=s["va"]+hi-s["rawOffset"];blob=raw[lo:hi]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=list(md.disasm(blob,sva))
    req(ins and ins[0].address==sva,"decode start drift");req(any(i.address==TARGET for i in ins),"target not decoded")
    lits={}
    for i in ins:
      for op in i.operands:
        if op.type==X86_OP_IMM:
          v=int(op.imm)&0xffffffff;cs=cstr(raw,secs,v)
          if cs:lits[v]=cs
    callers=[]
    for ss in secs:
      if not ss["exec"]:continue
      b=raw[ss["rawOffset"]:ss["rawOffset"]+ss["rawSize"]]
      md2=Cs(CS_ARCH_X86,CS_MODE_32);md2.detail=True;md2.skipdata=True
      seq=[i for i in md2.disasm(b,ss["va"]) if i.id]
      for n,i in enumerate(seq):
        if i.mnemonic!="call" or len(i.bytes)!=5 or i.bytes[0]!=0xe8:continue
        disp=struct.unpack("<i",i.bytes[1:])[0]
        if ((i.address+5+disp)&0xffffffff)!=sva:continue
        callers.append({"call":row(i),"section":ss["name"],
          "contextBefore":[row(x) for x in seq[max(0,n-40):n]],"contextAfter":[row(x) for x in seq[n+1:min(len(seq),n+41)]]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact INT3-bounded function bytes + exact rel32 caller contexts",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{sva:08x}","endVaExclusive":f"0x{eva:08x}","bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),
        "instructions":[row(i) for i in ins],"printableImmediateStrings":[lits[k] for k in sorted(lits)]},
      "callers":callers,
      "summary":{"functionStartVa":f"0x{sva:08x}","functionEndVaExclusive":f"0x{eva:08x}","instructionCount":len(ins),
        "callerCount":len(callers),"printableStringCount":len(lits)},
      "proofBoundary":"Exact function and direct-caller locator evidence only. postFxControl6 A/B/C/D source semantics, stack ownership, physical meaning and historical-retail equivalence remain unpromoted until a dataflow projector closes them."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":doc["summary"],"callers":[x["call"] for x in callers],"strings":doc["function"]["printableImmediateStrings"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
