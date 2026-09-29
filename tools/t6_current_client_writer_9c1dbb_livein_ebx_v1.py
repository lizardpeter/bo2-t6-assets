#!/usr/bin/env python3
"""Resolve live-in EBX for the current-client lightmap writer block at 0x009C1D50.

Exact upstream evidence establishes:
  0x009C1D58: EBP = EBX + 0xF00
  helper 0x009D9120 preserves EBP
  0x009C1DBB: [EBP+0x1610] = 1

This probe enumerates every decoded direct control-flow edge to 0x009C1D50
and records the reaching EBX definitions in each bounded caller region.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ENTRY=0x009C1D50

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def parse_pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,secs
def sec_for(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked {va:x}")
def raw_region(raw,s,va):
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];rel=va-s["va"]
    pre=list(re.finditer(b"\xCC{4,}",data[:rel]));req(pre,"no prior int3")
    a=pre[-1].end()
    while a<len(data) and data[a]==0xcc:a+=1
    post=re.search(b"\xCC{4,}",data[rel+1:]);req(post,"no next int3")
    b=rel+1+post.start()
    return s["va"]+a,s["va"]+b,data[a:b]
def rec(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def all_edges(raw,s,target):
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    out=[]
    for i in md.disasm(data,s["va"]):
        if len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
        if i.mnemonic not in ("call","jmp","je","jne","jz","jnz","ja","jb","jbe","jae","jg","jge","jl","jle"):continue
        if (int(i.operands[0].imm)&0xffffffff)==target:out.append(rec(i))
    return out
def context_for(raw,s,edge_va):
    start,end,blob=raw_region(raw,s,edge_va)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,start));idx=next((j for j,x in enumerate(ins) if x.address==edge_va),None);req(idx is not None,"edge missing")
    ebx=[]
    for x in ins[:idx]:
        _r,w=x.regs_access()
        if any(md.reg_name(z)=="ebx" for z in w):ebx.append(rec(x))
    lo=max(0,idx-120)
    return {"diagnosticStartVa":f"0x{start:08X}","diagnosticEndVaExclusive":f"0x{end:08X}",
            "edge":rec(ins[idx]),"ebxDefinitionsBeforeEdge":ebx,
            "lastEbxDefinitionBeforeEdge":ebx[-1] if ebx else None,
            "contextBefore":[rec(x) for x in ins[lo:idx]],
            "contextAfter":[rec(x) for x in ins[idx+1:min(len(ins),idx+30)]]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=parse_pe(raw);s=sec_for(secs,ENTRY)
    edges=all_edges(raw,s,ENTRY);contexts=[context_for(raw,s,int(e["address"],16)) for e in edges]
    doc={
      "format":"t6-current-client-writer-9c1dbb-livein-ebx-v1",
      "authority":"SHA-pinned current-client direct-control-flow and reaching-register census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "entry":{"va":f"0x{ENTRY:08X}","writerBaseExpression":"live_in_EBX + 0xF00","writerVa":"0x009C1DBB"},
      "incomingEdges":contexts,
      "summary":{"entryVa":f"0x{ENTRY:08X}","directIncomingEdgeCount":len(contexts),
                 "lastEbxDefinitions":[c["lastEbxDefinitionBeforeEdge"] for c in contexts]},
      "proofBoundary":"Exact decoded direct-edge census into 0x009C1D50. It closes live-in EBX only for decoded direct incoming occurrences whose reaching definition is explicit; indirect entries are not excluded."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
