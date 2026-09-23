#!/usr/bin/env python3
"""Census exact current-client callers of the gameTime source-object copy function at 0x76F7E0."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET=0x0076f7e0
FORMAT="t6-current-client-gametime-source-object-callers-v1"
CTX=40
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
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
        if not s["exec"]:continue
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[x for x in md.disasm(blob,s["va"]) if x.id]
        by={x.address:n for n,x in enumerate(ins)}
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.bytes)!=5 or i.bytes[0]!=0xe8:continue
            disp=struct.unpack("<i",i.bytes[1:5])[0];target=(i.address+5+disp)&0xffffffff
            if target!=TARGET:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            hits.append({"section":s["name"],"call":row(i),
              "contextBefore":[row(x) for x in ins[lo:n]],"contextAfter":[row(x) for x in ins[n+1:hi]]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact rel32 call targets + decoded context",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "target":{"functionVa":f"0x{TARGET:08x}","exactSemantics":"copies source [EAX+0..0x10] to render state [EDX+0x1A28..0x1A38]; source +4 becomes gameTime.T at state +0x1A2C"},
      "summary":{"callerCount":len(hits)},"callers":hits,
      "proofBoundary":"Exact current-client callsite evidence only. Caller-local EAX/EDX setup is retained for qualification; source-object field meaning, time units/cadence, and historical-retail equivalence remain unpromoted until a separate dataflow proof closes them."}
    if not hits:raise SystemExit("no direct callers found")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":doc["summary"],"calls":[x["call"] for x in hits]},indent=2,sort_keys=True))
if __name__=="__main__":main()
