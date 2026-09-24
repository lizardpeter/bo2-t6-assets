#!/usr/bin/env python3
"""Absolute destination writer census for all unresolved retained-special code constants.

Unlike older relative-offset probes, this accepts only memory destinations with
no base/index register whose address is exactly one of:
  value lane = 0x03A37300 + enum*16 + lane*4
  version    = 0x03A382E0 + enum*2
This prevents unrelated structure fields with coincident offsets from entering
the provider denominator.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-unresolved-constant-absolute-writers-v1"
VALUE_BASE=0x03A37300
VERSION_BASE=0x03A382E0
TARGETS={
 37:"shadowmapSwitchPartition",
 38:"sunShadowmapPixelSize",
 60:"spotShadowmapPixelAdjust",
 61:"dlightSpotShadowmapPixelAdjust",
 107:"postFxControl0",
 108:"postFxControl1",
 109:"postFxControl2",
 110:"postFxControl3",
 111:"postFxControl4",
 112:"postFxControl5",
}
READ_ONLY={"cmp","test","comiss","ucomiss","comisd","ucomisd","bt"}
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
def target_for(v):
    for e,a in TARGETS.items():
        b=VALUE_BASE+e*16
        for lane in range(4):
            if v==b+lane*4:return a,e,f"value[{lane}]"
        if v==VERSION_BASE+e*2:return a,e,"version"
    return None
def extent(ins,n):
    p=-1
    for k in range(n-1,-1,-1):
        if ins[k].mnemonic=="int3":
            while k+1<n and ins[k+1].mnemonic=="int3":k+=1
            p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
        if ins[k].mnemonic=="int3":q=k;break
    body=ins[p+1:q]
    return (body[0].address,body[-1].address+body[-1].size) if body else None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);writes=[];funcs=defaultdict(list)
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic in READ_ONLY or not i.operands:continue
            op=i.operands[0]
            if op.type!=X86_OP_MEM or op.mem.base!=0 or op.mem.index!=0:continue
            v=int(op.mem.disp)&0xffffffff;t=target_for(v)
            if t is None:continue
            ex=extent(ins,n);req(ex is not None,f"writer 0x{i.address:x} has no local extent")
            acc,e,field=t;lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            row={"accessor":acc,"enumValue":e,"field":field,"targetVa":f"0x{v:08x}",
                 "functionStartVa":f"0x{ex[0]:08x}","functionEndVaExclusive":f"0x{ex[1]:08x}",
                 "instruction":rr(i),"section":s["name"],
                 "contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]}
            writes.append(row);funcs[ex].append(row)
    summary={}
    for e,acc in TARGETS.items():
        rs=[x for x in writes if x["enumValue"]==e]
        summary[acc]={
          "enumValue":e,
          "absoluteDestinationWriteCount":len(rs),
          "fields":sorted({x["field"] for x in rs}),
          "writerFunctions":sorted({x["functionStartVa"] for x in rs}),
          "writerFunctionCount":len({x["functionStartVa"] for x in rs}),
          "hasAllFourValueLanes":all(f"value[{k}]" in {x["field"] for x in rs} for k in range(4)),
          "hasVersionWrite":"version" in {x["field"] for x in rs},
        }
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact absolute destination/RMW operand census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "arrayContract":{"valueBaseVa":f"0x{VALUE_BASE:08x}","versionBaseVa":f"0x{VERSION_BASE:08x}"},
      "summary":summary,
      "functions":[{"startVa":f"0x{st:08x}","endVaExclusive":f"0x{en:08x}","writes":rs} for (st,en),rs in sorted(funcs.items())],
      "writes":writes,
      "proofBoundary":"Exact absolute writer denominator only. Because every accepted destination has no base/index register, unrelated structure-offset aliases are excluded. This does not by itself close source value formulas, branch reachability, update cadence, historical-retail equivalence or framebuffer effects."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
