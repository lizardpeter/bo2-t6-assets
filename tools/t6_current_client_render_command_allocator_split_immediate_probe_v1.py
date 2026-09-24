#!/usr/bin/env python3
"""Fail-closed split-function probe for render-command allocator immediates.

The prior locator assumed 0x1E00 and 0x2000 occur in one INT3-bounded function;
the exact current client disproved that. This probe persists the separate hit
functions and exact rel32 call graph between/to them. It does not require a
connection to exist.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-command-allocator-split-immediate-probe-v1"
TARGETS={0x1e00:"criticalThreshold",0x2000:"noncriticalReserve"}

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
def bounds(raw,s,va):
    o=s["rawOffset"]+va-s["va"];base=s["rawOffset"];end=s["rawOffset"]+s["rawSize"]
    lo=o
    while lo>base+4 and raw[lo-4:lo]!=b"\xcc"*4:lo-=1
    start=lo if lo>base and raw[lo-4:lo]==b"\xcc"*4 else max(base,o-2048)
    hi=o
    while hi<end-4 and raw[hi:hi+4]!=b"\xcc"*4:hi+=1
    stop=hi if hi<end-4 and raw[hi:hi+4]==b"\xcc"*4 else min(end,o+4096)
    return s["va"]+start-base,s["va"]+stop-base,start,stop
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);fun={}
    allIns=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      allIns.extend((s,i) for i in ins)
      for i in ins:
        vals=[]
        for op in i.operands:
          if op.type==X86_OP_IMM:
            v=int(op.imm)&0xffffffff
            if v in TARGETS:vals.append(v)
        if not vals:continue
        fs,fe,rs,re=bounds(raw,s,i.address);k=(fs,fe,s["name"],rs,re)
        f=fun.setdefault(k,{"values":set(),"hits":[]});f["values"].update(vals);f["hits"].append(row(i))
    rows=[]
    starts=set()
    for (fs,fe,sec,rs,re),f in fun.items():
      starts.add(fs)
      rows.append({"section":sec,"functionStartVa":f"0x{fs:08x}","functionEndVaExclusive":f"0x{fe:08x}",
        "bytes":re-rs,"sha256":hashlib.sha256(raw[rs:re]).hexdigest(),
        "immediateValues":sorted(f["values"]),"immediateNames":[TARGETS[x] for x in sorted(f["values"])],
        "immediateHits":f["hits"]})
    rows.sort(key=lambda x:x["functionStartVa"])
    callers={fs:[] for fs in starts}
    edges=[]
    for s,i in allIns:
      if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
      t=int(i.operands[0].imm)&0xffffffff
      if t not in starts:continue
      cfs,cfe,crs,cre=bounds(raw,s,i.address)
      rec={"call":row(i),"callerFunctionStartVa":f"0x{cfs:08x}","targetFunctionStartVa":f"0x{t:08x}"}
      callers[t].append(rec);edges.append(rec)
    astarts={int(x["functionStartVa"],16) for x in rows if 0x1e00 in x["immediateValues"]}
    bstarts={int(x["functionStartVa"],16) for x in rows if 0x2000 in x["immediateValues"]}
    acallers={int(x["callerFunctionStartVa"],16) for t in astarts for x in callers[t]}
    bcallers={int(x["callerFunctionStartVa"],16) for t in bstarts for x in callers[t]}
    common=sorted(acallers&bcallers)
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact immediate hits and rel32 calls",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"immediateFunctionCount":len(rows),"criticalThresholdFunctionCount":len(astarts),
        "noncriticalReserveFunctionCount":len(bstarts),"sameFunctionCount":sum(set(x["immediateValues"])==set(TARGETS) for x in rows),
        "commonDirectCallerCount":len(common)},
      "functions":rows,"directCallEdgesToImmediateFunctions":edges,
      "commonDirectCallers":[f"0x{x:08x}" for x in common],
      "proofBoundary":"This probe intentionally does not assign allocator semantics. It proves only where the exact immediates occur and exact direct rel32 call relationships. The prior same-function invariant is disproven when sameFunctionCount=0; a common caller, if present, is locator evidence only."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in rows:print(x["functionStartVa"],x["immediateValues"],[(h["address"],h["opStr"]) for h in x["immediateHits"]])
    print("commonCallers",doc["commonDirectCallers"])
if __name__=="__main__":main()
