#!/usr/bin/env python3
"""Exact current-client xrefs for spot-shadow pixel-adjust constants 60/61.

Uses independently proven code-constant storage:
  values[enum] at source + 0x800 + enum*16
  versions[enum] uint16 at source + 0x17E0 + enum*2

Retains every decoded memory operand that addresses either enum's exact value
lanes or version slot, classified by destination/source operand role. This is a
locator/copy-vs-provider discriminator; no provider is promoted here.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-spot-shadow-pixel-adjust-storage-xrefs-v1"
VALUE_BASE=0x800
VERSION_BASE=0x17e0
ENUMS={60:"spotShadowmapPixelAdjust",61:"dlightSpotShadowmapPixelAdjust"}
CTX=18

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
def bounds(ins,n):
    lo=max(0,n-700)
    for k in range(n-1,lo-1,-1):
      if ins[k].mnemonic=="int3":
        while k+1<n and ins[k+1].mnemonic=="int3":k+=1
        return k+1
    return lo
def classify_disp(d):
    for e,name in ENUMS.items():
      vb=VALUE_BASE+e*16
      if vb<=d<vb+16 and (d-vb)%4==0:return {"enumValue":e,"accessor":name,"kind":"valueLane","lane":(d-vb)//4,"expectedBase":vb}
      vo=VERSION_BASE+e*2
      if d==vo:return {"enumValue":e,"accessor":name,"kind":"version","lane":None,"expectedBase":vo}
    return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[];clusters=defaultdict(lambda:{"hits":[],"keys":set()})
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        refs=[]
        for oi,op in enumerate(i.operands):
          if op.type!=X86_OP_MEM:continue
          d=int(op.mem.disp)&0xffffffff;c=classify_disp(d)
          if c is None:continue
          c={**c,"operandIndex":oi,"role":"destination-or-rmw" if oi==0 and i.mnemonic not in ("cmp","test") else "source-or-read",
             "baseReg":i.reg_name(op.mem.base) if op.mem.base else None,"indexReg":i.reg_name(op.mem.index) if op.mem.index else None,
             "scale":op.mem.scale,"displacement":d}
          refs.append(c)
        if not refs:continue
        fi=bounds(ins,n);fs=ins[fi].address if fi<len(ins) else i.address
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        h={"section":s["name"],"instruction":rr(i),"diagnosticFunctionStartVa":f"0x{fs:08x}","references":refs,
           "contextBefore":[rr(z) for z in ins[lo:n]],"contextAfter":[rr(z) for z in ins[n+1:hi]]}
        hits.append(h)
        cl=clusters[(s["name"],fs)];cl["hits"].append(h)
        for r in refs:cl["keys"].add((r["accessor"],r["kind"],r["lane"],r["role"]))
    rows=[]
    for (sec,fs),cl in clusters.items():
      rows.append({"section":sec,"diagnosticFunctionStartVa":f"0x{fs:08x}","hitCount":len(cl["hits"]),
        "referenceKeys":[{"accessor":a,"kind":k,"lane":l,"role":r} for a,k,l,r in sorted(cl["keys"],key=str)],
        "addresses":[x["instruction"]["address"] for x in cl["hits"]]})
    rows.sort(key=lambda x:(-len(x["referenceKeys"]),-x["hitCount"],x["diagnosticFunctionStartVa"]))
    summary={}
    for e,name in ENUMS.items():
      sub=[r for h in hits for r in h["references"] if r["accessor"]==name]
      summary[name]={
        "valueLaneDestinationHits":sum(r["kind"]=="valueLane" and r["role"]=="destination-or-rmw" for r in sub),
        "valueLaneSourceHits":sum(r["kind"]=="valueLane" and r["role"]=="source-or-read" for r in sub),
        "versionDestinationHits":sum(r["kind"]=="version" and r["role"]=="destination-or-rmw" for r in sub),
        "versionSourceHits":sum(r["kind"]=="version" and r["role"]=="source-or-read" for r in sub)}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded memory operands + independently proven constant-cache layouts",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "targets":[{"enumValue":e,"accessor":n,"valueBaseOffset":VALUE_BASE+e*16,"versionOffset":VERSION_BASE+e*2} for e,n in ENUMS.items()],
      "summary":summary,"diagnosticClusters":rows,"hits":hits,
      "proofBoundary":"Exact storage xrefs only. Destination writes are not automatically provider writes: state copies and bulk synchronization remain distinct until caller/source dataflow and version-update semantics are proven. INT3-based function starts are diagnostic grouping only."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for x in rows[:25]:print(x["diagnosticFunctionStartVa"],x["hitCount"],x["referenceKeys"])
if __name__=="__main__":main()
