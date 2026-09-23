#!/usr/bin/env python3
"""Focused current-client probe for the function called immediately before gameTime T is read."""
from __future__ import annotations
import argparse,hashlib,json,string,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-gametime-source-update-function-probe-v1"
START=0x0076f6c0
END=0x0076f880
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
def read(raw,secs,va,n):
    for s in secs:
      if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:
        o=s["rawOffset"]+va-s["va"];return s,raw[o:o+n]
    raise E(f"unbacked VA 0x{va:08x}+{n}")
def cstr(raw,secs,va,limit=300):
    try:s,b=read(raw,secs,va,1)
    except E:return None
    o=s["rawOffset"]+va-s["va"];end=min(s["rawOffset"]+s["rawSize"],o+limit);z=raw.find(b"\0",o,end)
    if z<0 or z==o:return None
    bb=raw[o:z]
    if len(bb)<4:return None
    try:t=bb.decode("ascii")
    except:return None
    if any(ch not in string.printable for ch in t):return None
    return {"va":f"0x{va:08x}","section":s["name"],"text":t,"bytes":bb.hex()}
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);sec,bb=read(raw,secs,START,END-START)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(bb,START));req(ins and ins[0].address==START,"decode start drift")
    lits={}
    for i in ins:
      for op in i.operands:
        if op.type==X86_OP_IMM:
          v=int(op.imm)&0xffffffff;cs=cstr(raw,secs,v)
          if cs:lits[v]=cs
    callers=[]
    for s in secs:
      if not s["exec"]:continue
      blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      for p in range(0,max(0,len(blob)-5)):
        if blob[p]!=0xe8:continue
        disp=struct.unpack_from("<i",blob,p+1)[0];va=s["va"]+p;t=(va+5+disp)&0xffffffff
        if t==START:callers.append({"callVa":f"0x{va:08x}","bytes":blob[p:p+5].hex(),"section":s["name"]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact bounded bytes/disassembly",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":sec["name"],"bytes":len(bb),
                  "sha256":hashlib.sha256(bb).hexdigest(),"instructions":[row(i) for i in ins]},
      "printableImmediateStrings":[lits[k] for k in sorted(lits)],"directCallers":callers,
      "summary":{"instructionCount":len(ins),"printableStringCount":len(lits),"directCallerCount":len(callers)},
      "proofBoundary":"Exact locator evidence only. The function is not named and no relation to clocks, scene time, gameTime scalar production, update cadence, or historical-retail semantics is promoted solely from this probe."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":doc["summary"],"strings":doc["printableImmediateStrings"],"callers":callers},indent=2,sort_keys=True))
if __name__=="__main__":main()
