#!/usr/bin/env python3
"""Current-client census joining owner+0x5DAC references to generic code-sampler callers.

Exact SHA-pinned executable evidence only. Enumerates:
  * decoded executable memory operands with displacement +0x5DAC;
  * decoded direct CALL/JMP edges to generic code-sampler consumer functions
    0x0077D710 and 0x0077DBE0;
  * bounded local instruction context around each occurrence.

This is a census/provenance proof. It does not assign source-level names solely
from displacement coincidence.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
DISP=0x5DAC
TARGETS={0x0077D710:"generic-code-sampler-consumer-a",0x0077DBE0:"generic-code-sampler-consumer-b"}
CTX=96

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        x=so+i*40;name=raw[x:x+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,x+8);ch=struct.unpack_from("<I",raw,x+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def row(i):
    return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def dis(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    return md,[i for i in md.disasm(data,s["va"]) if i.id]
def nearest_int3_boundary(ins,idx):
    # Diagnostic grouping only: find nearest preceding/following >=8 INT3 run.
    start=max(0,idx-1000); end=min(len(ins),idx+1000)
    prev=None;run=0
    for j in range(start,idx):
        if ins[j].mnemonic=="int3":
            run+=1
            if run>=8: prev=j+1
        else: run=0
    nxt=None;run=0
    for j in range(idx+1,end):
        if ins[j].mnemonic=="int3":
            run+=1
            if run>=8:
                nxt=j-run+1;break
        else: run=0
    return (
      row(ins[prev])["address"] if prev is not None and prev<len(ins) else None,
      row(ins[nxt])["address"] if nxt is not None and nxt<len(ins) else None,
    )
def ctx(ins,idx):
    lo=max(0,idx-CTX);hi=min(len(ins),idx+CTX+1)
    return {"before":[row(x) for x in ins[lo:idx]],"instruction":row(ins[idx]),"after":[row(x) for x in ins[idx+1:hi]]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=pe(raw);refs=[];edges=[]
    for s in secs:
        if not s["executable"]:continue
        md,ins=dis(raw,s)
        for idx,i in enumerate(ins):
            memhits=[]
            for oi,op in enumerate(i.operands):
                if op.type==X86_OP_MEM and op.mem.disp==DISP:
                    memhits.append({"operandIndex":oi,"base":md.reg_name(op.mem.base) if op.mem.base else None,
                                    "index":md.reg_name(op.mem.index) if op.mem.index else None,
                                    "scale":op.mem.scale,"disp":op.mem.disp})
            if memhits:
                ps,ns=nearest_int3_boundary(ins,idx)
                refs.append({"section":s["name"],"memoryOperands":memhits,"diagnosticInt3Start":ps,
                             "diagnosticInt3End":ns,**ctx(ins,idx)})
            if i.mnemonic in ("call","jmp") and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
                t=int(i.operands[0].imm)&0xffffffff
                if t in TARGETS:
                    ps,ns=nearest_int3_boundary(ins,idx)
                    edges.append({"section":s["name"],"targetVa":f"0x{t:08X}","targetRole":TARGETS[t],
                                  "diagnosticInt3Start":ps,"diagnosticInt3End":ns,**ctx(ins,idx)})
    doc={
      "format":"t6-current-client-owner-5dac-code-sampler-join-census-v1",
      "authority":"SHA-pinned current-client decoded executable memory-reference and direct-control-transfer census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "targetDisplacement":{"decimal":DISP,"hex":f"0x{DISP:X}"},
      "genericConsumers":[{"va":f"0x{k:08X}","role":v} for k,v in TARGETS.items()],
      "memoryReferences":refs,
      "consumerIncomingEdges":edges,
      "summary":{"memoryReferenceInstructionCount":len(refs),"consumerIncomingEdgeCount":len(edges),
                 "incomingByTarget":{f"0x{k:08X}":sum(1 for e in edges if e["targetVa"]==f"0x{k:08X}") for k in TARGETS}},
      "proofBoundary":"Exact decoded current-client census. INT3 boundaries are diagnostic grouping only. A +0x5DAC reference is not assigned a semantic field identity from displacement alone; context dataflow must establish any join to the generic sampler source object."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
