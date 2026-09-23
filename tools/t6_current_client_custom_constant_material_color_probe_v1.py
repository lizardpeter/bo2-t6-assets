#!/usr/bin/env python3
"""Probe current-client RC_SET_CUSTOM_CONSTANT and RC_SET_MATERIAL_COLOR handlers.

This is exact-byte evidence only. The semantic projector separately proves that the
material-color handler's fixed destinations are const index 46 by deriving the
generic const/value/version array bases from RC_SET_CUSTOM_CONSTANT.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-custom-constant-and-material-color-handlers-v1"
RANGES=[
 ("customConstant",0x00745b70,0x00745bc0),
 ("materialColor",0x00745bc0,0x00745c20),
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
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro})
    return ib,secs
def get(raw,secs,a,b):
    for s in secs:
      if s["va"]<=a and b<=s["va"]+s["rawSize"]:
        o=s["rawOffset"]+(a-s["va"]);return s,raw[o:o+b-a]
    raise E(f"unbacked range 0x{a:x}..0x{b:x}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);ranges=[]
    for label,start,end in RANGES:
      s,b=get(raw,secs,start,end);ins=list(md.disasm(b,start))
      req(ins and ins[0].address==start,f"{label}: bad decode start")
      ranges.append({"label":label,"startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}","section":s["name"],
        "bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"instructions":[row(i) for i in ins]})
    doc={"format":FORMAT,"authority":"SHA-classified current client exact bytes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "ranges":ranges,
      "proofBoundary":"Exact bounded handler bytes/disassembly only. Labels come from the independently proven render-command table, but this probe alone does not assign constant indices or source-state semantics."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({x["label"]:{"sha256":x["sha256"],"instructionCount":len(x["instructions"])} for x in ranges},indent=2))
if __name__=="__main__":main()
