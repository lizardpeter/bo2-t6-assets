#!/usr/bin/env python3
"""Trace the caller-arg provenance feeding current-client writer 0x009C2A88.

The prior proof closes:
  0x009B80E9 -> 0x009C1EF0
  0x009B80DA ESI=[EBP+8]
  callee destination base = that value + 0xF00.

This probe recovers the exact diagnostic region containing 0x009B80E9,
checks the local frame setup, and enumerates all decoded direct CALL/JMP
edges to the region start with bounded caller argument context.

INT3-derived region boundaries are diagnostic until direct control-flow
and prologue evidence support function-boundary promotion.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ANCHOR=0x009B80E9
TARGET=0x009C1EF0
CTX=128

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)

def parse_pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]; req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;secs=[]
    for i in range(n):
        x=so+i*40; name=raw[x:x+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,x+8);ch=struct.unpack_from("<I",raw,x+36)[0]
        secs.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,secs

def rec(i): return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def disasm_section(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    return md,[i for i in md.disasm(data,s["va"]) if i.id]

def find_region(ins,idx):
    # nearest preceding/following run of >=8 INT3 instructions
    start_idx=0; run=0; last_after=None
    for j in range(0,idx):
        if ins[j].mnemonic=="int3":
            run+=1
            if run>=8: last_after=j+1
        else:
            run=0
    if last_after is not None:
        start_idx=last_after
        while start_idx<len(ins) and ins[start_idx].mnemonic=="int3": start_idx+=1
    end_idx=len(ins);run=0
    for j in range(idx+1,len(ins)):
        if ins[j].mnemonic=="int3":
            run+=1
            if run>=8:
                end_idx=j-run+1
                break
        else: run=0
    return start_idx,end_idx

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    base,secs=parse_pe(raw)
    textsec=next(s for s in secs if s["name"]==".text")
    md,ins=disasm_section(raw,textsec)
    index={i.address:j for j,i in enumerate(ins)}
    req(ANCHOR in index,f"missing anchor {ANCHOR:x}")
    ai=index[ANCHOR]; anchor=ins[ai]
    req(anchor.mnemonic=="call" and anchor.op_str.lower()=="0x9c1ef0",f"anchor drift {anchor.mnemonic} {anchor.op_str}")
    si,ei=find_region(ins,ai)
    region=ins[si:ei]
    req(region,"empty region")
    start=region[0].address; end=(region[-1].address+region[-1].size)
    rindex={i.address:k for k,i in enumerate(region)}
    req(0x009B80DA in rindex,"missing arg load")
    argload=region[rindex[0x009B80DA]]
    req(argload.mnemonic=="mov" and argload.op_str=="esi, dword ptr [ebp + 8]",f"arg load drift {argload.op_str}")

    # Frame setup evidence before anchor.
    pre=region[:rindex[ANCHOR]]
    frame_setup=[rec(i) for i in pre if (i.mnemonic=="push" and i.op_str=="ebp") or (i.mnemonic=="mov" and i.op_str=="ebp, esp")]
    ebp_writes=[]
    for i in pre:
        _r,w=i.regs_access()
        if any(md.reg_name(x)=="ebp" for x in w):
            ebp_writes.append(rec(i))

    incoming=[]
    for s in secs:
        if not s["executable"]: continue
        smd,sins=disasm_section(raw,s)
        for j,i in enumerate(sins):
            if i.mnemonic not in ("call","jmp") or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM: continue
            t=int(i.operands[0].imm)&0xffffffff
            if t!=start: continue
            lo=max(0,j-CTX);hi=min(len(sins),j+32)
            incoming.append({
                "section":s["name"],"edge":rec(i),
                "contextBefore":[rec(x) for x in sins[lo:j]],
                "contextAfter":[rec(x) for x in sins[j+1:hi]],
            })

    doc={
      "format":"t6-current-client-writer-9c2a88-caller-arg1-provenance-v1",
      "authority":"SHA-pinned current-client exact diagnostic region, frame dataflow, and decoded direct incoming-edge census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "anchor":{"call":rec(anchor),"arg1Load":rec(argload),"downstreamDestinationBase":"loaded [EBP+8] + 0xF00"},
      "region":{"startVa":f"0x{start:08X}","endVaExclusive":f"0x{end:08X}","instructionCount":len(region),
                "frameSetupCandidates":frame_setup,"ebpWritesBeforeAnchor":ebp_writes,
                "instructions":[rec(i) for i in region]},
      "directIncomingEdges":incoming,
      "summary":{"diagnosticRegionStart":f"0x{start:08X}","diagnosticRegionEndExclusive":f"0x{end:08X}",
                 "directIncomingEdgeCount":len(incoming),"frameSetupCandidateCount":len(frame_setup),
                 "ebpWriteCountBeforeAnchor":len(ebp_writes)},
      "proofBoundary":"Exact current-client local/caller census. INT3 boundaries remain diagnostic unless the recovered prologue and incoming edges establish a true entry. [EBP+8] is promoted as function arg1 only if frame setup is unambiguous; caller source-level semantics remain unassigned."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__": main()
