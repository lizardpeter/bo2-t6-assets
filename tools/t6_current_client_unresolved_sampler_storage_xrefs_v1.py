#!/usr/bin/env python3
"""Exact current-client storage xrefs for unresolved retained-special code samplers.

Uses the independently proven generic source-state layout:
  codeImages[slot]            = source + 0x1530 + slot*4
  codeImageSamplerStates[slot]= source + 0x160C + slot

Targets only still-unresolved sampler enums 6,16,18. This is a storage/provider
locator; destination matches are not promoted until base provenance and source
image/state semantics are proven.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-unresolved-sampler-storage-xrefs-v1"
IMAGE_BASE=0x1530
STATE_BASE=0x160C
TARGETS={6:"shadowmapSamplerSun",16:"dlightAttenuationSampler",18:"floatZSampler"}
CTX=36
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
def fstart(ins,n):
    for k in range(n-1,max(-1,n-900),-1):
      if ins[k].mnemonic=="int3":
        while k+1<n and ins[k+1].mnemonic=="int3":k+=1
        return ins[k+1].address if k+1<n else ins[n].address
    return ins[max(0,n-900)].address
def classify(d):
    for slot,name in TARGETS.items():
      if d==IMAGE_BASE+slot*4:return {"slot":slot,"accessor":name,"kind":"codeImage","expectedOffset":d}
      if d==STATE_BASE+slot:return {"slot":slot,"accessor":name,"kind":"samplerState","expectedOffset":d}
    return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[];clusters=defaultdict(list)
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        refs=[]
        for oi,op in enumerate(i.operands):
          if op.type!=X86_OP_MEM:continue
          d=int(op.mem.disp)&0xffffffff;c=classify(d)
          if c is None:continue
          role="destination-or-rmw" if oi==0 and i.mnemonic not in ("cmp","test") else "source-or-read"
          refs.append({**c,"operandIndex":oi,"role":role,
            "baseReg":i.reg_name(op.mem.base) if op.mem.base else None,
            "indexReg":i.reg_name(op.mem.index) if op.mem.index else None,"scale":op.mem.scale})
        if not refs:continue
        fs=fstart(ins,n);lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        h={"section":s["name"],"diagnosticFunctionStartVa":f"0x{fs:08x}","instruction":rr(i),"references":refs,
           "contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]}
        hits.append(h);clusters[(s["name"],fs)].append(h)
    rows=[]
    for (sec,fs),hs in clusters.items():
      refs=[r for h in hs for r in h["references"]]
      rows.append({"section":sec,"diagnosticFunctionStartVa":f"0x{fs:08x}","hitCount":len(hs),
        "accessors":sorted(set(r["accessor"] for r in refs)),
        "destinationKinds":sorted(set((r["accessor"],r["kind"]) for r in refs if r["role"]=="destination-or-rmw")),
        "sourceKinds":sorted(set((r["accessor"],r["kind"]) for r in refs if r["role"]=="source-or-read")),
        "addresses":[h["instruction"]["address"] for h in hs]})
    rows.sort(key=lambda x:(-len(x["destinationKinds"]),-x["hitCount"],x["diagnosticFunctionStartVa"]))
    summary={}
    for slot,name in TARGETS.items():
      sub=[r for h in hits for r in h["references"] if r["slot"]==slot]
      summary[name]={
        "slot":slot,"codeImageOffset":IMAGE_BASE+slot*4,"samplerStateOffset":STATE_BASE+slot,
        "imageDestinationHits":sum(r["kind"]=="codeImage" and r["role"]=="destination-or-rmw" for r in sub),
        "stateDestinationHits":sum(r["kind"]=="samplerState" and r["role"]=="destination-or-rmw" for r in sub),
        "imageSourceHits":sum(r["kind"]=="codeImage" and r["role"]=="source-or-read" for r in sub),
        "stateSourceHits":sum(r["kind"]=="samplerState" and r["role"]=="source-or-read" for r in sub)}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded memory operands + independently proven code-pixel-sampler array layout",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "arrayContract":{"codeImagesBaseOffset":IMAGE_BASE,"codeImageSamplerStatesBaseOffset":STATE_BASE},
      "summary":summary,"diagnosticClusters":rows,"hits":hits,
      "proofBoundary":"Exact destination/source xrefs for the three unresolved code-sampler slots only. A matching displacement does not by itself prove base-register source-state identity or resource provenance; each candidate writer remains unresolved until those dataflows are independently closed."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for x in rows[:30]:print(x)
if __name__=="__main__":main()
