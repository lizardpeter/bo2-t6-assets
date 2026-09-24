#!/usr/bin/env python3
"""Focused current-client proof for spot-shadow pixel-adjust live writer.

Captures the exact SHA-classified function beginning at 0x009BEA80, direct rel32
callers, and all accesses to the enum-60/61 constant lanes and version dword.
This is intentionally a byte/dataflow proof; provider semantics are projected
separately only after exact branch/formula analysis.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-spot-shadow-pixel-adjust-writer-probe-v1"
START=0x009BEA80
END=0x009BF520
TARGETS={
  "spotShadowmapPixelAdjust":[0x0BC0,0x0BC4,0x0BC8,0x0BCC,0x1858],
  "dlightSpotShadowmapPixelAdjust":[0x0BD0,0x0BD4,0x0BD8,0x0BDC,0x185A],
}

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]; req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4; n=struct.unpack_from("<H",raw,coff+2)[0]; optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20; req(struct.unpack_from("<H",raw,opt)[0]==0x10b,"not PE32")
    ib=struct.unpack_from("<I",raw,opt+28)[0]; so=opt+optsz; secs=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8); ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def va_blob(raw,secs,a,b):
    for s in secs:
        if s["va"]<=a and b<=s["va"]+s["rawSize"]:
            off=s["rawOffset"]+(a-s["va"])
            return s,raw[off:off+b-a]
    raise E(f"range 0x{a:x}..0x{b:x} not raw-backed")
def row(i):
    return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def direct_calls(raw,secs,target):
    md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True; out=[]
    for s in secs:
        if not s["exec"]: continue
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        for i in md.disasm(blob,s["va"]):
            if i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
                t=int(i.operands[0].imm)&0xffffffff
                if t==target: out.append(row(i))
    return out
def refs(ins):
    out=[]
    for i in ins:
        op=i.op_str.lower()
        for acc,disps in TARGETS.items():
            for d in disps:
                hx=f"0x{d:x}"
                if hx in op:
                    out.append({"accessor":acc,"displacement":d,"instruction":row(i)})
    return out
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path); ap.add_argument("--revision",required=True); ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    raw=a.exe.read_bytes(); digest=hashlib.sha256(raw).hexdigest(); req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw); sec,blob=va_blob(raw,secs,START,END)
    md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True; ins=list(md.disasm(blob,START))
    req(ins and ins[0].address==START,"decode start drift")
    calls=direct_calls(raw,secs,START)
    touches=refs(ins)
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":sec["name"],
        "bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),"instructions":[row(i) for i in ins]},
      "directCallers":calls,
      "storageTouches":touches,
      "summary":{"instructionCount":len(ins),"directCallerCount":len(calls),"storageTouchCount":len(touches)},
      "proofBoundary":"Exact current-client bytes/disassembly and direct rel32 callers only. The function label 'spot-shadow pixel-adjust writer' is an investigation label derived from exact enum-60/61 storage accesses. Bulk initialization/state-copy paths are not conflated with this function. Higher-level physical units, historical-retail equivalence, and framebuffer semantics remain unclaimed."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__": main()
