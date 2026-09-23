#!/usr/bin/env python3
"""Recover exact register/input setup for all six callers of the gameTime state-copy helper."""
from __future__ import annotations
import argparse,hashlib,json,struct,string
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET=0x0076f7e0
FORMAT="t6-current-client-gametime-state-copy-callers-v1"
CALLS=[0x00732479,0x00732c00,0x00733164,0x00733729,0x00745c41,0x00773f89]
CTX_BEFORE=72
CTX_AFTER=28
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
def cstr(raw,secs,va,limit=256):
    for s in secs:
      if s["va"]<=va<s["va"]+s["rawSize"]:
        o=s["rawOffset"]+va-s["va"];end=min(s["rawOffset"]+s["rawSize"],o+limit);z=raw.find(b"\0",o,end)
        if z<0 or z==o:return None
        b=raw[o:z]
        try:t=b.decode("ascii")
        except:return None
        if len(t)<4 or any(ch not in string.printable for ch in t):return None
        return {"va":f"0x{va:08x}","section":s["name"],"text":t,"bytes":b.hex()}
    return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[x for x in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if x.id]
      pos={i.address:n for n,i in enumerate(ins)}
      for va in CALLS:
        if va not in pos:continue
        n=pos[va];i=ins[n]
        req(i.mnemonic=="call" and i.op_str==f"0x{TARGET:x}",f"call drift 0x{va:x}: {i.mnemonic} {i.op_str}")
        lo=max(0,n-CTX_BEFORE);hi=min(len(ins),n+CTX_AFTER+1);win=ins[lo:hi]
        lits={}
        for z in win:
          for op in z.operands:
            if op.type==X86_OP_IMM:
              v=int(op.imm)&0xffffffff;cs=cstr(raw,secs,v)
              if cs:lits[v]=cs
        rows.append({"callVa":f"0x{va:08x}","section":s["name"],
          "before":[row(x) for x in ins[lo:n]],"call":row(i),"after":[row(x) for x in ins[n+1:hi]],
          "printableImmediateStrings":[lits[k] for k in sorted(lits)]})
    req(len(rows)==len(CALLS),f"caller windows {len(rows)} != {len(CALLS)}")
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact caller instruction windows",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "calleeVa":f"0x{TARGET:08x}","summary":{"callerCount":len(rows)},"callers":rows,
      "proofBoundary":"Exact caller windows only. Register setup is preserved verbatim; no caller/function/input-struct semantics or historical-retail equivalence is promoted until a dataflow projector proves them."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":doc["summary"],"callers":[{"callVa":x["callVa"],"strings":[s["text"] for s in x["printableImmediateStrings"]]} for x in rows]},indent=2,sort_keys=True))
if __name__=="__main__":main()
