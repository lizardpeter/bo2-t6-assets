#!/usr/bin/env python3
"""Locate current-client render-command allocator by unique machine invariants.

Pinned T6 lineage is locator-only. The allocator uniquely combines:
- 0x1E00 critical command threshold
- 0x2000 reserved noncritical tail
- command-byte alignment/size handling
- returned record/header initialization

This probe groups decoded immediate uses of 0x1E00 and 0x2000 by INT3-bounded
function and persists exact function disassembly for candidates containing both.
No source symbol is assigned by this locator.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-command-allocator-immediate-locator-v1"
TARGETS={0x1e00:"criticalThreshold",0x2000:"noncriticalReserve"}

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
def bounds(raw,s,va):
    o=s["rawOffset"]+va-s["va"];lo=o;base=s["rawOffset"];end=s["rawOffset"]+s["rawSize"]
    while lo>base+4 and raw[lo-4:lo]!=b"\xcc"*4:lo-=1
    start=lo if lo>base and raw[lo-4:lo]==b"\xcc"*4 else max(base,o-2048)
    hi=o
    while hi<end-4 and raw[hi:hi+4]!=b"\xcc"*4:hi+=1
    stop=hi if hi<end-4 and raw[hi:hi+4]==b"\xcc"*4 else min(end,o+4096)
    return s["va"]+start-base,s["va"]+stop-base,start,stop
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);groups={}
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        ins=[i for i in md.disasm(blob,s["va"]) if i.id]
        for i in ins:
            vals=[]
            for op in i.operands:
                if op.type==X86_OP_IMM:
                    v=int(op.imm)&0xffffffff
                    if v in TARGETS:vals.append(v)
            if not vals:continue
            fs,fe,rs,re=bounds(raw,s,i.address)
            k=(fs,fe,s["name"],rs,re)
            g=groups.setdefault(k,{"values":set(),"hits":[]})
            g["values"].update(vals);g["hits"].append(row(i))
    candidates=[]
    for (fs,fe,sec,rs,re),g in groups.items():
        if set(TARGETS)-g["values"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        body=[i for i in md.disasm(raw[rs:re],fs) if i.id]
        # Diagnostics for argument/header-like behavior, not promotion criteria.
        stackRefs=[row(i) for i in body if any("[esp +" in op.op_str for op in [i])][:80]
        candidates.append({
          "section":sec,"functionStartVa":f"0x{fs:08x}","functionEndVaExclusive":f"0x{fe:08x}",
          "bytes":re-rs,"sha256":hashlib.sha256(raw[rs:re]).hexdigest(),
          "immediateHits":g["hits"],"instructionCount":len(body),
          "instructions":[row(i) for i in body],
        })
    candidates.sort(key=lambda x:x["functionStartVa"])
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded immediate/control-flow locator",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "locator":{"criticalThreshold":0x1e00,"noncriticalReserve":0x2000},
      "summary":{"candidateFunctionCount":len(candidates)},
      "candidates":candidates,
      "proofBoundary":"Locator only. Candidates are exact current-client functions containing both 0x1E00 and 0x2000 immediates. Pinned T6 lineage motivates those invariants. No candidate is named R_GetCommandBuffer and no command-header/allocation semantics are promoted until a dedicated structural projector validates stack arguments, size accounting, returned command pointer, and header stores."
    }
    if not candidates:raise SystemExit("no function contains both allocator immediates")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in candidates:print(c["functionStartVa"],c["functionEndVaExclusive"],c["sha256"],[(x["address"],x["mnemonic"],x["opStr"]) for x in c["immediateHits"]])
if __name__=="__main__":main()
