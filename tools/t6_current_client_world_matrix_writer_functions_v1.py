#!/usr/bin/env python3
"""Recover INT3-bounded current-client functions that directly update worldMatrix version slots."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-world-matrix-writer-functions-v1"
WORLD_CONST_OFF=0x1986
WORLD_MATRIX_VER_OFF=0x19c6
SEARCH=0x1800

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
def vaoff(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s,s["rawOffset"]+va-s["va"]
    raise E(f"VA 0x{va:x} unbacked")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def direct_world_writes(raw,secs):
    hits=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]):
            if i.id==0 or i.mnemonic in ("cmp","test"):continue
            for oi,op in enumerate(i.operands):
                if oi!=0 or op.type!=X86_OP_MEM:continue
                if op.mem.index!=0:continue
                disp=int(op.mem.disp)&0xffffffff
                if disp in (WORLD_MATRIX_VER_OFF,WORLD_CONST_OFF):
                    hits.append({"address":i.address,"field":"matrixVersion" if disp==WORLD_MATRIX_VER_OFF else "constVersion",
                                 "instruction":row(i),"baseReg":i.reg_name(op.mem.base) if op.mem.base else None})
    return hits
def extent(raw,secs,va):
    s,o=vaoff(secs,va);lo=max(s["rawOffset"],o-SEARCH);hi=min(s["rawOffset"]+s["rawSize"],o+SEARCH)
    before=raw[lo:o];p=before.rfind(b"\xcc"*8);req(p>=0,f"no prior pad for 0x{va:x}")
    start=lo+p+8
    while start<o and raw[start]==0xcc:start+=1
    after=raw[o:hi];q=after.find(b"\xcc"*8);req(q>0,f"no next pad for 0x{va:x}")
    end=o+q
    return s["va"]+(start-s["rawOffset"]),s["va"]+(end-s["rawOffset"]),start,end,s
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=direct_world_writes(raw,secs)
    groups={}
    for h in hits:
        st,en,so,eo,s=extent(raw,secs,h["address"]);k=(st,en)
        g=groups.setdefault(k,{"startVa":f"0x{st:08x}","endVaExclusive":f"0x{en:08x}","rawStart":so,"rawEnd":eo,"section":s["name"],"writerHits":[]})
        g["writerHits"].append({k:v for k,v in h.items() if k!="address"}|{"address":f"0x{h['address']:08x}"})
    rows=[]
    for (st,en),g in sorted(groups.items()):
        blob=raw[g.pop("rawStart"):g.pop("rawEnd")];md=Cs(CS_ARCH_X86,CS_MODE_32)
        ins=list(md.disasm(blob,st))
        g["bytes"]=len(blob);g["sha256"]=hashlib.sha256(blob).hexdigest();g["instructionCount"]=len(ins);g["instructions"]=[row(i) for i in ins]
        g["matrixVersionWriteCount"]=sum(x["field"]=="matrixVersion" for x in g["writerHits"])
        g["constVersionWriteCount"]=sum(x["field"]=="constVersion" for x in g["writerHits"])
        rows.append(g)
    summary={"directDestinationWriteInstructionCount":len(hits),"functionCount":len(rows),
             "functionsWritingMatrixVersion":sum(x["matrixVersionWriteCount"]>0 for x in rows),
             "functionsWritingConstVersion":sum(x["constVersionWriteCount"]>0 for x in rows),
             "functionsWritingBoth":sum(x["matrixVersionWriteCount"]>0 and x["constVersionWriteCount"]>0 for x in rows)}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact direct memory writes + INT3-bounded function bytes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"functions":rows,
      "proofBoundary":"Exact writer-function recovery only. Direct writes are limited to memory operands with no index and exact proven source-state displacements +0x19C6/+0x1986. Base-register identity, placement semantics, matrix arithmetic, writer role, draw-time cadence, and historical-retail equivalence require dedicated dataflow proofs."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for x in rows:print(x["startVa"],x["endVaExclusive"],x["matrixVersionWriteCount"],x["constVersionWriteCount"],[h["address"] for h in x["writerHits"]])
if __name__=="__main__":main()
