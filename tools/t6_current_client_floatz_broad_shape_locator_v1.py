#!/usr/bin/env python3
"""Locate current-client floatZ provider by broad exact function shape.

Anchor: a direct call with exact integer argument 11. For each hit, retain a bounded
function-like window and rank only exact instruction immediates:
- MSAA case constants 1,2,4,8,16
- sampler-state byte 97
- integer 18 uses
No semantic name is promoted here.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-floatz-broad-shape-locator-v1"
WIN=180
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
def imm_values(i):
    vals=[]
    for op in getattr(i,"operands",[]):
      if op.type==X86_OP_IMM:vals.append(int(op.imm)&0xffffffff)
    return vals
def push11(i):
    return i.mnemonic=="push" and 11 in imm_values(i)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      for n,i in enumerate(ins):
        if i.mnemonic!="call":continue
        anchors=[z for z in ins[max(0,n-8):n] if push11(z)]
        if not anchors:continue
        lo=max(0,n-WIN);hi=min(len(ins),n+WIN)
        window=ins[lo:hi]
        allim=[v for z in window for v in imm_values(z)]
        msaa={v for v in allim if v in {1,2,4,8,16}}
        state97=sum(v==97 for v in allim)
        imm18=sum(v==18 for v in allim)
        directcalls=[z for z in window if z.mnemonic=="call"]
        score=len(msaa)*10+state97*5+imm18
        hits.append({
          "section":s["name"],"call":row(i),"argument11":[row(z) for z in anchors],
          "score":score,"msaaImmediateSet":sorted(msaa),"immediate97Count":state97,"immediate18Count":imm18,
          "directCallCount":len(directcalls),"windowStartVa":f"0x{window[0].address:08x}","windowEndVa":f"0x{window[-1].address+window[-1].size:08x}",
          "context":[row(z) for z in window]
        })
    hits.sort(key=lambda x:(-x["score"],x["call"]["address"]))
    doc={"format":FORMAT,"authority":"SHA-classified current client exact decoded instructions",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"argument11DirectCallCandidateCount":len(hits),"topScore":hits[0]["score"] if hits else None,
                 "candidatesWithFullMsaaSet":sum(x["msaaImmediateSet"]==[1,2,4,8,16] for x in hits),
                 "candidatesWithImmediate97":sum(x["immediate97Count"]>0 for x in hits)},
      "candidates":hits,
      "proofBoundary":"Locator only. Exact push-immediate 11/direct-call anchors and exact bounded immediate diagnostics are retained. No call target is named Image_GetProg, no candidate is named R_ResolveFloatZ, and no codeImages/codeImageSamplerStates destination is promoted until exact current-client dataflow closes it."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in hits[:20]:print(x["call"]["address"],x["score"],x["msaaImmediateSet"],x["immediate97Count"],x["immediate18Count"])
if __name__=="__main__":main()
