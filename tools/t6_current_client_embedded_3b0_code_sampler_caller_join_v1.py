#!/usr/bin/env python3
"""Join current-client +0x3B0 address formation to generic code-sampler caller functions.

The owner constructor proves its +0x5DAC field resolves to owner+0x3B0.
This probe asks whether the same +0x3B0 embedded object is materialized in
functions that directly call the generic code-sampler consumers.

Exact SHA-pinned executable evidence only. INT3-bounded groups are diagnostic
containers, not automatically semantic function identities.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
DISP=0x3B0
TARGETS={0x0077D710:"consumer-a",0x0077DBE0:"consumer-b"}
CTX=80

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        x=so+i*40;name=raw[x:x+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,x+8);ch=struct.unpack_from("<I",raw,x+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def row(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def dis(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    return md,[i for i in md.disasm(data,s["va"]) if i.id]
def group_bounds(ins,idx):
    # nearest >=6 INT3 run on both sides; diagnostic grouping only
    start=ins[0].address;run=0
    for j in range(idx-1,-1,-1):
        if ins[j].mnemonic=="int3":
            run+=1
            if run>=6:
                k=j
                while k>0 and ins[k-1].mnemonic=="int3":k-=1
                # start at first non-int3 after whole run
                t=j+run
                while t<len(ins) and ins[t].mnemonic=="int3":t+=1
                if t<len(ins): start=ins[t].address
                break
        else:run=0
    end=None;run=0;run_start=None
    for j in range(idx+1,len(ins)):
        if ins[j].mnemonic=="int3":
            if run==0:run_start=j
            run+=1
            if run>=6:
                end=ins[run_start].address
                break
        else:run=0;run_start=None
    return start,end
def ctx(ins,idx,n=CTX):
    return {"before":[row(x) for x in ins[max(0,idx-n):idx]],"instruction":row(ins[idx]),"after":[row(x) for x in ins[idx+1:min(len(ins),idx+n+1)]]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=pe(raw);forms=[];calls=[]
    for s in secs:
        if not s["executable"]:continue
        md,ins=dis(raw,s)
        for idx,i in enumerate(ins):
            mh=[]
            for oi,op in enumerate(i.operands):
                if op.type==X86_OP_MEM and op.mem.disp==DISP:
                    mh.append({"operandIndex":oi,"base":md.reg_name(op.mem.base) if op.mem.base else None,
                               "index":md.reg_name(op.mem.index) if op.mem.index else None,"scale":op.mem.scale})
            if mh:
                gs,ge=group_bounds(ins,idx)
                forms.append({"section":s["name"],"groupStartVa":f"0x{gs:08X}","groupEndVa":f"0x{ge:08X}" if ge else None,
                              "memoryOperands":mh,**ctx(ins,idx,36)})
            if i.mnemonic in ("call","jmp") and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
                t=int(i.operands[0].imm)&0xffffffff
                if t in TARGETS:
                    gs,ge=group_bounds(ins,idx)
                    calls.append({"section":s["name"],"groupStartVa":f"0x{gs:08X}","groupEndVa":f"0x{ge:08X}" if ge else None,
                                  "targetVa":f"0x{t:08X}","targetRole":TARGETS[t],**ctx(ins,idx,52)})
    call_groups={x["groupStartVa"] for x in calls}
    matched_forms=[x for x in forms if x["groupStartVa"] in call_groups]
    matched_groups=sorted({x["groupStartVa"] for x in matched_forms})
    matched_calls=[x for x in calls if x["groupStartVa"] in set(matched_groups)]
    doc={
      "format":"t6-current-client-embedded-3b0-code-sampler-caller-join-v1",
      "authority":"SHA-pinned current-client decoded +0x3B0 memory/address operands intersected with exact direct generic code-sampler caller groups",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "embeddedOffset":{"decimal":DISP,"hex":f"0x{DISP:X}","upstreamIdentity":"owner+0x5DAC resolves to owner+0x3B0 in exact constructor proof"},
      "summary":{"all3B0InstructionCount":len(forms),"consumerIncomingEdgeCount":len(calls),
                 "matchedGroupCount":len(matched_groups),"matched3B0InstructionCount":len(matched_forms),
                 "matchedConsumerEdgeCount":len(matched_calls)},
      "matchedGroups":matched_groups,
      "matched3B0Occurrences":matched_forms,
      "matchedConsumerEdges":matched_calls,
      "all3B0OccurrenceIndex":[{"address":x["instruction"]["address"],"mnemonic":x["instruction"]["mnemonic"],"opStr":x["instruction"]["opStr"],"groupStartVa":x["groupStartVa"]} for x in forms],
      "proofBoundary":"Exact decoded intersection census. A same-function/group +0x3B0 occurrence is a high-value dataflow candidate, not by itself proof that the formed address reaches context.source. Promotion requires local register/stack dataflow from that occurrence into the first dword of the context passed to a consumer."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    print("matchedGroups",matched_groups)
if __name__=="__main__":main()
