#!/usr/bin/env python3
"""Locate exact current-client light code-constant version writers.

Upstream current-client proof closes:
  constVersionsBaseOffset = 0x17E0
  constVersions[enum] is uint16 at source + 0x17E0 + enum*2

This probe scans decoded executable memory operands for the exact derived
displacements of the retained light enums, retaining only destination/RMW
instructions plus compact context. Function boundaries are diagnostic only.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-light-const-version-writer-xrefs-v1"
BASE=0x17e0
ENUMS={0:"lightPosition",1:"lightDiffuse",2:"lightSpotDir",3:"lightSpotFactors",
5:"lightFallOffA",6:"lightFallOffB",7:"lightSpotMatrix0",8:"lightSpotMatrix1",
9:"lightSpotMatrix2",11:"lightSpotAABB",12:"lightConeControl1",
14:"lightSpotCookieSlideControl",60:"spotShadowmapPixelAdjust"}
OFFSETS={BASE+e*2:(e,n) for e,n in ENUMS.items()}
CTX=16

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
def func_bounds(ins,n):
    lo=max(0,n-700)
    for k in range(n-1,lo-1,-1):
      if ins[k].mnemonic=="int3":
        while k+1<n and ins[k+1].mnemonic=="int3":k+=1
        return k+1
    return lo
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[];clusters=defaultdict(lambda:{"accessors":set(),"hits":[]})
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        refs=[]
        for oi,op in enumerate(i.operands):
          if op.type!=X86_OP_MEM:continue
          disp=int(op.mem.disp)&0xffffffff
          if disp not in OFFSETS:continue
          # Only destination/RMW memory operand zero; cmp/test are reads.
          if oi!=0 or i.mnemonic in ("cmp","test"):continue
          e,name=OFFSETS[disp]
          refs.append({"enumValue":e,"accessor":name,"displacement":disp,
            "baseReg":i.reg_name(op.mem.base) if op.mem.base else None,
            "indexReg":i.reg_name(op.mem.index) if op.mem.index else None,"scale":op.mem.scale})
        if not refs:continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        fi=func_bounds(ins,n);fs=ins[fi].address if fi<len(ins) else i.address
        h={"section":s["name"],"instruction":row(i),"references":refs,
           "diagnosticFunctionStartVa":f"0x{fs:08x}",
           "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]}
        hits.append(h)
        c=clusters[(s["name"],fs)];c["hits"].append(h)
        c["accessors"].update(r["accessor"] for r in refs)
    cr=[]
    for (sec,fs),c in clusters.items():
      cr.append({"section":sec,"diagnosticFunctionStartVa":f"0x{fs:08x}",
        "distinctAccessors":sorted(c["accessors"]),"distinctAccessorCount":len(c["accessors"]),
        "writerInstructionCount":len(c["hits"]),
        "writerAddresses":[x["instruction"]["address"] for x in c["hits"]]})
    cr.sort(key=lambda x:(-x["distinctAccessorCount"],-x["writerInstructionCount"],x["diagnosticFunctionStartVa"]))
    counts={n:0 for n in ENUMS.values()}
    for h in hits:
      for r in h["references"]:counts[r["accessor"]]+=1
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded destination/RMW memory operands + proven constVersions base layout",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "upstream":{"constVersionsBaseOffset":BASE,"formula":"source + 0x17E0 + enum*2",
        "targets":[{"enumValue":e,"accessor":n,"offset":BASE+e*2} for e,n in sorted(ENUMS.items())]},
      "summary":{"writerInstructionCount":len(hits),"accessorWriterCounts":counts,
        "diagnosticClusterCount":len(cr),"maxAccessorsPerDiagnosticCluster":max((x["distinctAccessorCount"] for x in cr),default=0)},
      "diagnosticClusters":cr,"hits":hits,
      "proofBoundary":"Exact version-slot destination/RMW xrefs are authoritative current-client evidence because each displacement derives from the independently proven constVersions layout. diagnosticFunctionStartVa uses nearby INT3 only as a grouping locator and is not promoted as a true function boundary. A semantics projector must prove source-state base identity and corresponding value formulas before provider closure."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in cr[:25]:print(x["diagnosticFunctionStartVa"],x["distinctAccessorCount"],x["distinctAccessors"],x["writerAddresses"])
if __name__=="__main__":main()
