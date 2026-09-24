#!/usr/bin/env python3
"""Recover actual direct control-flow entrypoints around sampler-state writes at 0x00455588.

The earlier INT3-bounded diagnostic region contains an early RET, so padding alone
is not a valid function boundary. This probe enumerates all direct CALL/JMP edges
into a tight window around the sampler-state initializer and preserves exact
local disassembly so the true entrypoint(s) can be established fail-closed.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-sampler-initializer-entrypoints-v1"
LO=0x00455000
HI=0x00455700
ANCHOR=0x00455588
CTX=20
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
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def secfor(secs,va):
    for s in secs:
      if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"VA 0x{va:x} not backed")
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);edges=[];targets=defaultdict(list)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
      if not s["exec"]:continue
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        if i.mnemonic not in {"call","jmp"} or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
        tgt=int(i.operands[0].imm)&0xffffffff
        if not (LO<=tgt<HI):continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        row={"source":rr(i),"targetVa":f"0x{tgt:08x}","section":s["name"],
             "contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]}
        edges.append(row);targets[tgt].append(row["source"]["address"])
    s=secfor(secs,LO);start=s["rawOffset"]+LO-s["va"];end=s["rawOffset"]+HI-s["va"]
    local=[rr(i) for i in md.disasm(raw[start:end],LO) if i.id]
    # Split local stream at every RET/RETF/INT3 and at every proven incoming target.
    target_set=set(targets)
    marker_rows=[]
    for i,x in enumerate(local):
      va=int(x["address"],16)
      if va in target_set or x["mnemonic"] in {"ret","retf","int3"}:
        marker_rows.append(x)
    below=[t for t in sorted(targets) if t<=ANCHOR]
    candidate=max(below) if below else None
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact direct control-flow edges + local decoded bytes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "window":{"loVa":f"0x{LO:08x}","hiVaExclusive":f"0x{HI:08x}","anchorVa":f"0x{ANCHOR:08x}"},
      "incomingTargets":[{"targetVa":f"0x{k:08x}","edgeCount":len(v),"sources":v} for k,v in sorted(targets.items())],
      "edges":edges,"localInstructions":local,"markers":marker_rows,
      "summary":{"incomingTargetCount":len(targets),"incomingEdgeCount":len(edges),
                 "nearestIncomingTargetAtOrBelowAnchor":f"0x{candidate:08x}" if candidate is not None else None,
                 "anchorHasDirectIncomingEdge":ANCHOR in targets},
      "proofBoundary":"Direct CALL/JMP entrypoint census and local bytes only. The nearest incoming target is a control-flow candidate, not automatically a semantic function start; indirect entries and fallthrough remain separate until explicitly proven."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    print(json.dumps(doc["incomingTargets"],indent=2,sort_keys=True))
if __name__=="__main__":main()
