#!/usr/bin/env python3
"""Exact current-client storage xrefs for three unresolved retained-special code constants."""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadow-debug-constant-storage-xrefs-v1"
VALUE_BASE=0x800
VERSION_BASE=0x17e0
TARGETS={37:"shadowmapSwitchPartition",38:"sunShadowmapPixelSize",45:"debugPerformance"}
CTX=28
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
    for k in range(n-1,max(-1,n-700),-1):
      if ins[k].mnemonic=="int3":
        while k+1<n and ins[k+1].mnemonic=="int3":k+=1
        return ins[k+1].address if k+1<n else ins[n].address
    return ins[max(0,n-700)].address
def classify(d):
    for e,name in TARGETS.items():
      vb=VALUE_BASE+e*16
      if vb<=d<vb+16 and (d-vb)%4==0:return {"enumValue":e,"accessor":name,"kind":"valueLane","lane":(d-vb)//4}
      vo=VERSION_BASE+e*2
      if d==vo:return {"enumValue":e,"accessor":name,"kind":"version","lane":None}
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
          refs.append({**c,"displacement":d,"operandIndex":oi,
            "role":"destination-or-rmw" if oi==0 and i.mnemonic not in ("cmp","test") else "source-or-read",
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
        "referenceKeys":sorted({(r["accessor"],r["kind"],r["lane"],r["role"]) for r in refs},key=str),
        "addresses":[h["instruction"]["address"] for h in hs]})
    rows.sort(key=lambda x:(-len(x["referenceKeys"]),-x["hitCount"],x["diagnosticFunctionStartVa"]))
    summary={}
    for e,name in TARGETS.items():
      rs=[r for h in hits for r in h["references"] if r["enumValue"]==e]
      summary[name]={"enumValue":e,
        "valueDestinationHits":sum(r["kind"]=="valueLane" and r["role"]=="destination-or-rmw" for r in rs),
        "valueSourceHits":sum(r["kind"]=="valueLane" and r["role"]=="source-or-read" for r in rs),
        "versionDestinationHits":sum(r["kind"]=="version" and r["role"]=="destination-or-rmw" for r in rs),
        "versionSourceHits":sum(r["kind"]=="version" and r["role"]=="source-or-read" for r in rs)}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded memory operands + independently proven generic code-constant cache layout",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"diagnosticClusters":rows,"hits":hits,
      "proofBoundary":"Exact displacement-access census only. Matching offsets are locators until base-register source-state identity and value/version dataflow are independently closed; diagnostic INT3 boundaries are grouping evidence only."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
