#!/usr/bin/env python3
"""Locate current-client floatZSampler provider candidates from exact T6 lineage shape.

Locator shape (lineage only):
  argument 11 -> direct call -> returned program image stored to one source-relative
  dword slot -> sampler-state byte 97 stored exactly +0xA6 bytes later.
0xA6 is the T6 GfxCmdBufInput layout delta from codeImages[18] to
codeImageSamplerStates[18] (55 pointer slots between array bases).

No function/provider semantic is promoted by this locator.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM,X86_OP_REG
from capstone.x86_const import X86_REG_EAX

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-floatz-provider-locator-v1"
STATE_DELTA=0xA6
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
def push11(i):
    if i.id==0:return False
    return i.mnemonic=="push" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM and int(i.operands[0].imm)==11
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);candidates=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
        for n,i in enumerate(ins):
            if i.id==0:continue
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            if not any(push11(z) for z in ins[max(0,n-5):n]):continue
            # Track EAX aliases created immediately after return.
            aliases={X86_REG_EAX}
            stores=[];states=[]
            for z in ins[n+1:min(len(ins),n+1+CTX)]:
                if z.mnemonic=="mov" and len(z.operands)==2:
                    d,sop=z.operands
                    if d.type==X86_OP_REG and sop.type==X86_OP_REG and sop.reg in aliases:
                        aliases.add(d.reg)
                    if d.type==X86_OP_MEM and d.mem.base!=0 and d.mem.index==0:
                        if d.size==4 and sop.type==X86_OP_REG and sop.reg in aliases:
                            stores.append({"baseRegId":d.mem.base,"disp":int(d.mem.disp),"instruction":row(z),"sourceRegId":sop.reg})
                        if d.size==1 and sop.type==X86_OP_IMM and (int(sop.imm)&0xff)==0x61:
                            states.append({"baseRegId":d.mem.base,"disp":int(d.mem.disp),"instruction":row(z)})
            pairs=[]
            for st in stores:
                for ss in states:
                    if st["baseRegId"]==ss["baseRegId"] and ss["disp"]-st["disp"]==STATE_DELTA:
                        pairs.append({"imageStore":st,"samplerStateStore":ss,"delta":STATE_DELTA})
            if not pairs:continue
            lo=max(0,n-20);hi=min(len(ins),n+1+CTX)
            candidates.append({
              "section":s["name"],"call":row(i),"callTargetVa":f"0x{int(i.operands[0].imm)&0xffffffff:08x}",
              "argument11Instructions":[row(z) for z in ins[max(0,n-5):n] if push11(z)],
              "matchedPairs":pairs,
              "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]
            })
    doc={"format":FORMAT,"authority":"SHA-classified current client exact decoded instructions; OpenBO2 sequence/layout used as locator only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"candidateCount":len(candidates),"matchedImageStatePairCount":sum(len(x["matchedPairs"]) for x in candidates)},
      "locatorShape":{"programArgument":11,"samplerStateByte":97,"codeImageToSamplerStateDelta":STATE_DELTA},
      "candidates":candidates,
      "proofBoundary":"Exact current-client instruction matches only. Argument 11, sampler-state 97 and +0xA6 layout are T6 lineage locators. No call target is named Image_GetProg, no destination is promoted as codeImages[18], and no candidate is assigned floatZSampler until independent current-client/static-table evidence closes those semantics."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in candidates:print(x["call"]["address"],x["callTargetVa"],[(p["imageStore"]["disp"],p["samplerStateStore"]["disp"]) for p in x["matchedPairs"]])
if __name__=="__main__":main()
