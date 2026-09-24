#!/usr/bin/env python3
"""Destination-only current-client writer census for postFxControl0..5.

Scans exact executable operands for writes/RMWs to the six code-constant value
vectors and version words. Reads are intentionally excluded. Writers are grouped
by local INT3-bounded function extents, but function boundaries remain diagnostic
until a semantic projector freezes a selected provider.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-postfx-control0-5-destination-writers-v1"
VALUE_BASE=0x03A37300
VERSION_BASE=0x03A382E0
ENUMS={f"postFxControl{i}":107+i for i in range(6)}
READ_ONLY={"cmp","test","comiss","ucomiss","comisd","ucomisd"}
CTX=20
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
def classify(v):
    for acc,e in ENUMS.items():
        base=VALUE_BASE+e*16
        for lane in range(4):
            if v==base+lane*4:return acc,e,f"value[{lane}]"
        if v==VERSION_BASE+e*2:return acc,e,"version"
    return None
def fextent(ins,n):
    p=-1
    for k in range(n-1,-1,-1):
        if ins[k].mnemonic=="int3":
            while k+1<n and ins[k+1].mnemonic=="int3":k+=1
            p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
        if ins[k].mnemonic=="int3":q=k;break
    body=ins[p+1:q]
    if not body:return None
    return body[0].address,body[-1].address+body[-1].size
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);writes=[];clusters=defaultdict(list)
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic in READ_ONLY or not i.operands:continue
            op=i.operands[0]
            if op.type!=X86_OP_MEM or op.mem.base!=0 or op.mem.index!=0:continue
            v=int(op.mem.disp)&0xffffffff;c=classify(v)
            if c is None:continue
            ext=fextent(ins,n);req(ext is not None,f"writer 0x{i.address:x} has no extent")
            acc,e,field=c;lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            row={"accessor":acc,"enumValue":e,"field":field,"targetVa":f"0x{v:08x}",
                 "functionStartVa":f"0x{ext[0]:08x}","functionEndVaExclusive":f"0x{ext[1]:08x}",
                 "instruction":rr(i),"contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]}
            writes.append(row);clusters[ext].append(row)
    funcs=[]
    for (st,en),rows in sorted(clusters.items()):
        by=defaultdict(list)
        for r in rows:by[r["accessor"]].append(r)
        funcs.append({"startVa":f"0x{st:08x}","endVaExclusive":f"0x{en:08x}","writeCount":len(rows),
          "accessors":{acc:{"fields":sorted({x["field"] for x in rs}),"writeCount":len(rs),
                            "writeAddresses":[x["instruction"]["address"] for x in rs]} for acc,rs in sorted(by.items())}})
    summary={}
    for acc,e in ENUMS.items():
        rs=[x for x in writes if x["accessor"]==acc]
        fields=sorted({x["field"] for x in rs})
        fs=sorted({x["functionStartVa"] for x in rs})
        summary[acc]={"enumValue":e,"destinationWriteCount":len(rs),"fields":fields,"writerFunctionCount":len(fs),"writerFunctions":fs,
                      "hasAllFourValueLanes":all(f"value[{i}]" in fields for i in range(4)),
                      "hasVersionWrite":"version" in fields}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact destination/RMW decoded operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"functions":funcs,"writes":writes,
      "proofBoundary":"Exact destination/RMW xref census only. Reads are excluded. INT3-bounded function grouping is diagnostic. No source-record ownership, lane formula, update cadence, physical meaning, historical-retail equivalence or framebuffer semantics are promoted until dedicated provider projectors close exact dataflow."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
