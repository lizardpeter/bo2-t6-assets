#!/usr/bin/env python3
"""Exact focused current-client probe for the 0x00786210 light constant writer."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-light-writer-786210-probe-v1"
START=0x00786210
END=0x00786960

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
def read(raw,secs,a,b):
    for s in secs:
      if s["va"]<=a and b<=s["va"]+s["rawSize"]:
        o=s["rawOffset"]+a-s["va"];return s,raw[o:o+b-a]
    raise E("range not raw-backed")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s,blob=read(raw,secs,START,END)
    md=Cs(CS_ARCH_X86,CS_MODE_32);ins=list(md.disasm(blob,START))
    req(ins and ins[0].address==START,"decode start drift")
    req(ins[-1].address==0x0078695f and ins[-1].mnemonic=="ret","function end drift")
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact bounded function bytes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":s["name"],
        "bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),"instructionCount":len(ins),
        "instructions":[row(i) for i in ins]},
      "proofBoundary":"Exact current-client function bytes/disassembly only. The fixed range ends at the observed ret immediately before the next decoded function. Argument roles and light semantics are not assigned by this probe alone."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"sha256":doc["function"]["sha256"],"bytes":len(blob),"instructionCount":len(ins)},indent=2))
    for i in ins[:80]:print(f"0x{i.address:08x}",i.mnemonic,i.op_str)
if __name__=="__main__":main()
