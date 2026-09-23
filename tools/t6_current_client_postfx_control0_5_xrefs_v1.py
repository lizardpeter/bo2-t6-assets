#!/usr/bin/env python3
"""Focused current-client xrefs for postFxControl0..5 exact constant slots."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-postfx-control0-5-xrefs-v1"
VALUE_BASE=0x03A37300
VERSION_BASE=0x03A382E0
ENUMS={f"postFxControl{i}":107+i for i in range(6)}
CTX=60

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
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw)
    targets={}
    meta={}
    for acc,e in ENUMS.items():
        vals=[VALUE_BASE+e*16+j*4 for j in range(4)];ver=VERSION_BASE+e*2
        meta[acc]={"accessor":acc,"enumValue":e,"valueVas":[f"0x{x:08x}" for x in vals],"versionVa":f"0x{ver:08x}"}
        for j,v in enumerate(vals):targets.setdefault(v,[]).append((acc,f"value[{j}]"))
        targets.setdefault(ver,[]).append((acc,"version"))
    hits=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
        for n,i in enumerate(ins):
            if i.id==0:continue
            refs=[]
            for oi,op in enumerate(i.operands):
                vals=[]
                if op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and op.mem.disp:
                    vals.append((int(op.mem.disp)&0xffffffff,"absolute-memory"))
                elif op.type==X86_OP_IMM:
                    vals.append((int(op.imm)&0xffffffff,"immediate"))
                for v,kind in vals:
                    if v in targets:
                        for acc,field in targets[v]:
                            refs.append({"accessor":acc,"field":field,"targetVa":f"0x{v:08x}","kind":kind,
                                         "operandIndex":oi,"positionClass":"destination-or-rmw" if oi==0 and i.mnemonic not in ("cmp","test") else "source-or-other"})
            if refs:
                lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
                hits.append({"section":s["name"],"instruction":row(i),"references":refs,
                             "contextBefore":[row(x) for x in ins[lo:n]],"contextAfter":[row(x) for x in ins[n+1:hi]]})
    rows=[]
    for acc in ENUMS:
        ah=[h for h in hits if any(r["accessor"]==acc for r in h["references"])]
        fields={}
        dest=0
        for h in ah:
            for r in h["references"]:
                if r["accessor"]!=acc:continue
                fields[r["field"]]=fields.get(r["field"],0)+1
                if r["positionClass"]=="destination-or-rmw":dest+=1
        rows.append({**meta[acc],"directXrefInstructionCount":len(ah),"destinationOrRmwReferenceCount":dest,"fieldXrefCounts":fields,"xrefs":ah})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded operands + exact generic constant storage geometry",
         "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
         "summary":{"accessorCount":len(rows),"accessorsWithDirectXrefs":sum(x["directXrefInstructionCount"]>0 for x in rows),
                    "accessorsWithDestinationOrRmw":sum(x["destinationOrRmwReferenceCount"]>0 for x in rows),
                    "totalHitInstructions":len(hits)},
         "rows":rows,
         "proofBoundary":"Locator only. Exact slot xrefs and bounded current-client instruction context are retained. No producer formula, source-record ownership, update cadence, semantic units, or historical-retail equivalence is promoted until a dedicated projector closes exact dataflow."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in rows:print(x["accessor"],x["enumValue"],x["directXrefInstructionCount"],x["destinationOrRmwReferenceCount"],x["fieldXrefCounts"])
if __name__=="__main__":main()
