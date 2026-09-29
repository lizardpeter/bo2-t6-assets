#!/usr/bin/env python3
"""Path-sensitive current-client proof for writer 0x009C2A88 upstream arg1.

Corrects the path-insensitive v2 interpretation. The writer path reaches
0x009B80DA through JE 0x009B8083, which skips the epilogue at
0x009B80D3..0x009B80D9. This proof establishes whether EBP therefore remains
the active frame pointer on that exact branch occurrence and retains the sole
decoded caller context for the enclosing function.

No source-level semantic type is assigned from an address or offset alone.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ANCHOR=0x009B80E9
ENTRY=0x009B7E80
BRANCH=0x009B8083
BRANCH_TARGET=0x009B80DA
DOWNSTREAM=0x009C1EF0

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
def rec(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def raw_region(raw,s,va):
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];rel=va-s["va"]
    pre=list(re.finditer(b"\xCC{8,}",data[:rel]));req(pre,"no prior int3")
    a=pre[-1].end()
    while a<len(data) and data[a]==0xcc:a+=1
    post=re.search(b"\xCC{8,}",data[rel+1:]);req(post,"no next int3")
    b=rel+1+post.start()
    return s["va"]+a,s["va"]+b,data[a:b]
def dis(blob,va,detail=True):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=detail
    return md,list(md.disasm(blob,va))
def direct_edges(raw,s,target):
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    out=[]
    for i in md.disasm(data,s["va"]):
        if i.mnemonic not in ("call","jmp","je","jne","jz","jnz","ja","jb","jbe","jae","jg","jge","jl","jle") or len(i.operands)!=1:continue
        if i.operands[0].type==X86_OP_IMM and (int(i.operands[0].imm)&0xffffffff)==target:
            out.append(rec(i))
    return out
def region_for_edge(raw,s,edge_va):
    a,b,blob=raw_region(raw,s,edge_va);md,ins=dis(blob,a,True)
    idx=next((j for j,x in enumerate(ins) if x.address==edge_va),None);req(idx is not None,"edge missing")
    lo=max(0,idx-96);hi=min(len(ins),idx+24)
    return {"diagnosticStartVa":f"0x{a:08X}","diagnosticEndVaExclusive":f"0x{b:08X}",
            "instructionCount":len(ins),"contextBefore":[rec(x) for x in ins[lo:idx]],
            "edge":rec(ins[idx]),"contextAfter":[rec(x) for x in ins[idx+1:hi]]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=parse_pe(raw);s=sec_for(secs,ANCHOR)
    rs,rex,blob=raw_region(raw,s,ANCHOR);md,ins=dis(blob,rs,True);by={x.address:x for x in ins}
    gates={
      ENTRY:("push","ebp"), ENTRY+1:("mov","ebp, esp"),
      BRANCH:("je","0x9b80da"),
      0x009B80D6:("mov","esp, ebp"),0x009B80D8:("pop","ebp"),0x009B80D9:("ret",""),
      BRANCH_TARGET:("mov","esi, dword ptr [ebp + 8]"),
      0x009B80E2:("push","esi"),ANCHOR:("call","0x9c1ef0")
    }
    for va,(mn,op) in gates.items():
        x=by.get(va);req(x is not None,f"missing {va:x}")
        req(x.mnemonic==mn and x.op_str.lower()==op.lower(),f"drift {va:x}: {x.mnemonic} {x.op_str}")

    # Direct path BRANCH_TARGET..ANCHOR contains no EBP writes.
    path=[x for x in ins if BRANCH_TARGET<=x.address<=ANCHOR]
    ebp_path_writes=[]
    for x in path:
        _r,w=x.regs_access()
        if any(md.reg_name(z)=="ebp" for z in w):ebp_path_writes.append(rec(x))
    req(not ebp_path_writes,f"EBP modified on branch-target path: {ebp_path_writes}")

    to_target=direct_edges(raw,s,BRANCH_TARGET)
    to_entry=direct_edges(raw,s,ENTRY)
    # For the observed intra-function branch occurrence, EBP is the frame pointer
    # because ENTRY establishes it and the branch jumps over the epilogue.
    observed_branch=[x for x in to_target if x["address"].lower()=="0x009b8083"]
    req(observed_branch,"missing observed branch edge")

    caller_contexts=[]
    for edge in to_entry:
        caller_contexts.append(region_for_edge(raw,s,int(edge["address"],16)))

    doc={
      "format":"t6-current-client-writer-9c2a88-path-sensitive-arg1-v3",
      "authority":"SHA-pinned current-client path-sensitive branch/prologue/epilogue proof plus decoded direct-edge census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "enclosingRegion":{"diagnosticStartVa":f"0x{rs:08X}","diagnosticEndVaExclusive":f"0x{rex:08X}",
                         "sha256":hashlib.sha256(blob).hexdigest(),"instructionCount":len(ins)},
      "path":{
        "frameSetup":[rec(by[ENTRY]),rec(by[ENTRY+1])],
        "branchToWriterContinuation":rec(by[BRANCH]),
        "skippedEpilogue":[rec(by[0x009B80D6]),rec(by[0x009B80D8]),rec(by[0x009B80D9])],
        "continuationSourceLoad":rec(by[BRANCH_TARGET]),
        "continuationArgPush":rec(by[0x009B80E2]),
        "downstreamCall":rec(by[ANCHOR]),
        "ebpWritesFromContinuationToDownstreamCall":ebp_path_writes,
        "conclusion":"On the decoded 0x009B8083 -> 0x009B80DA branch occurrence, EBP remains the active frame pointer; [EBP+8] is enclosing-function arg1 and is pushed unchanged as 0x009C1EF0 arg1."
      },
      "directEdgesToContinuation":to_target,
      "directEdgesToEnclosingEntry":to_entry,
      "enclosingCallerContexts":caller_contexts,
      "summary":{"enclosingEntry":f"0x{ENTRY:08X}","continuation":f"0x{BRANCH_TARGET:08X}",
                 "directEdgeCountToContinuation":len(to_target),"directEdgeCountToEntry":len(to_entry),
                 "observedBranchFramePointerPreserved":True,
                 "downstreamArg1Expression":"enclosing_function_arg1",
                 "writerDestinationBaseExpression":"enclosing_function_arg1 + 0xF00"},
      "proofBoundary":"Closes the observed decoded branch occurrence only: on 0x009B8083 -> 0x009B80DA, the epilogue is skipped and EBP remains the frame pointer. Therefore the downstream writer base is enclosing-function arg1+0xF00 for that occurrence. Other hypothetical indirect entries to 0x009B80DA are not excluded; caller arg1 semantic identity remains to be proven from the upstream call context."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
