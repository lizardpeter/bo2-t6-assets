#!/usr/bin/env python3
"""Locate current-client HDR control update paths from exact enum 123/124 uses.

This is a semantic locator, not a value promoter. It scans executable code for
instructions carrying immediate 123 or 124, then records bounded control/dataflow
contexts and nearby direct calls. Pairing is based only on exact current-client
bytes; open-engine lineage is not used as authority.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-hdrcontrol-enum-pair-probe-v1"
TARGETS={123:"hdrControl0",124:"hdrControl1"}
CTX=28
NEAR_CALLS=10

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
    ib,secs=pe(raw);hits=[];call_targets=collections.defaultdict(lambda:collections.Counter())
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
        ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
        for n,i in enumerate(ins):
            vals=[]
            for op in i.operands:
                if op.type==X86_OP_IMM:
                    vals.append(int(op.imm)&0xffffffff)
            matched=sorted(set(vals)&set(TARGETS))
            if not matched:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            nearby=[]
            for z in ins[n+1:min(len(ins),n+1+NEAR_CALLS)]:
                if z.mnemonic=="call" and len(z.operands)==1 and z.operands[0].type==X86_OP_IMM:
                    t=int(z.operands[0].imm)&0xffffffff
                    nearby.append({"call":row(z),"targetVa":f"0x{t:08x}"})
                    for v in matched:call_targets[v][t]+=1
            hits.append({
              "section":s["name"],"instruction":row(i),
              "enumValues":matched,"enumNames":[TARGETS[v] for v in matched],
              "nearbyDirectCalls":nearby,
              "contextBefore":[row(z) for z in ins[lo:n]],
              "contextAfter":[row(z) for z in ins[n+1:hi]],
            })
    paired=[]
    common=set(call_targets[123])&set(call_targets[124])
    for t in sorted(common):
        paired.append({"targetVa":f"0x{t:08x}",
          "hdrControl0NearbyHitCount":call_targets[123][t],
          "hdrControl1NearbyHitCount":call_targets[124][t]})
    doc={
      "format":FORMAT,"authority":"SHA-classified current Plutonium client exact decoded instructions only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{
        "enum123InstructionHitCount":sum(123 in h["enumValues"] for h in hits),
        "enum124InstructionHitCount":sum(124 in h["enumValues"] for h in hits),
        "commonNearbyDirectCallTargetCount":len(paired),
      },
      "commonNearbyDirectCallTargets":paired,"hits":hits,
      "proofBoundary":"Immediate 123/124 uses and nearby calls are exact current-client locator evidence only. The numeric values are independently pinned T6 code-constant enums, but no hit is promoted as R_DirtyCodeConstant, no preceding store is assigned to GfxCmdBufSourceState, and no HDR value formula or historical-retail equivalence is inferred here."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    print(json.dumps(paired,indent=2,sort_keys=True))
if __name__=="__main__":main()
