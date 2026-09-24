#!/usr/bin/env python3
"""Focused current-client probe for the all-lane enum38 sunShadowmapPixelSize writer."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-sun-shadowmap-pixel-size-writer-probe-v1"
ANCHOR=0x00497450
SEARCH=0x1800
class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
      q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def secfor(secs,va):
    for s in secs:
      if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E("unbacked anchor")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def body(raw,s,anchor):
    ro=s["rawOffset"]+anchor-s["va"];lo=max(s["rawOffset"],ro-SEARCH);hi=min(s["rawOffset"]+s["rawSize"],ro+SEARCH)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(raw[lo:hi],s["va"]+lo-s["rawOffset"]) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==anchor),None);req(n is not None,"anchor not decoded")
    p=-1
    for k in range(n-1,-1,-1):
      if ins[k].mnemonic=="int3":
        while k+1<n and ins[k+1].mnemonic=="int3":k+=1
        p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
      if ins[k].mnemonic=="int3":q=k;break
    return ins[p+1:q]
def callers(raw,secs,target):
    out=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
      if not s["exec"]:continue
      for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]):
        if i.id and i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM and (int(i.operands[0].imm)&0xffffffff)==target:
          out.append(rr(i))
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s=secfor(secs,ANCHOR);ins=body(raw,s,ANCHOR);start=ins[0].address;end=ins[-1].address+ins[-1].size
    lanes={0:0xa60,1:0xa64,2:0xa68,3:0xa6c};hits=[]
    for i in ins:
      op=i.op_str.lower()
      for lane,off in lanes.items():
        if f"0x{off:x}" in op:hits.append({"lane":lane,"instruction":rr(i)})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact bounded writer function",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}","anchorVa":f"0x{ANCHOR:08x}","section":s["name"],"instructions":[rr(i) for i in ins]},
      "enum38LaneHits":hits,"directCallersToFunctionEntry":callers(raw,secs,start),
      "summary":{"functionStartVa":f"0x{start:08x}","instructionCount":len(ins),"laneHitCount":len(hits),"lanes":sorted({h["lane"] for h in hits}),"directCallerCount":len(callers(raw,secs,start))},
      "proofBoundary":"Exact current-client function bytes and callers only. Selection is based on the independent enum38 xref census. Base-register source-state identity, input units, version/update behavior, physical shadow semantics, and historical-retail equivalence remain unpromoted until proven from this dataflow."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
