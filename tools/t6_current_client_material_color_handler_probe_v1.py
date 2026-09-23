#!/usr/bin/env python3
"""Focused exact current-client probe for render-command handler table index 2."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-material-color-handler-probe-v1"
START=0x00745bc0
END=0x00745c20
TABLE=0x00d27e70
INDEX=2
EXPECTED_PTR=START

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
def raw_for(secs,va,n):
    for s in secs:
      if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:
        return s["rawOffset"]+va-s["va"],s
    raise E(f"unbacked 0x{va:x}+{n}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw)
    toff,_=raw_for(secs,TABLE+INDEX*4,4);ptr=struct.unpack_from("<I",raw,toff)[0]
    req(ptr==EXPECTED_PTR,f"table index2 drift 0x{ptr:08x}")
    off,sec=raw_for(secs,START,END-START);blob=raw[off:off+END-START]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,START))
    doc={"format":FORMAT,"authority":"SHA-classified current client exact bytes plus exact render-command table index 2",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "table":{"va":f"0x{TABLE:08x}","index":INDEX,"handlerVa":f"0x{ptr:08x}"},
      "handler":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":sec["name"],
                 "bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),"instructions":[row(i) for i in ins]},
      "proofBoundary":"Exact table pointer and bounded current-client handler bytes/disassembly only. The handler is not yet promoted as materialColor semantics until a separate projector proves its command-pointer reads, three color-component transfers, code-constant destination, dirty/version behavior, and command-stream advance."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"handlerSha256":doc["handler"]["sha256"],"instructionCount":len(ins)},indent=2))
    for i in ins:print(i.address, i.mnemonic, i.op_str)
if __name__=="__main__":main()
