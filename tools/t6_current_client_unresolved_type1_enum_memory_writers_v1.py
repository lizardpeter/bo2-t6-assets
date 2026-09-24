#!/usr/bin/env python3
"""Locate dynamic construction writes for unresolved type-1 code-constant enums.

The exact type-1 ABI stores enumValue as uint32(record+0x04), but the retained
six unresolved indirect constants have no literal structurally valid records in
the PE image. This probe finds executable immediate-to-memory writes of those
enum values and preserves bounded context for record-construction joins.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-unresolved-type1-enum-memory-writers-v1"
TARGETS={37:"shadowmapSwitchPartition",38:"sunShadowmapPixelSize",
         60:"spotShadowmapPixelAdjust",61:"dlightSpotShadowmapPixelAdjust",
         111:"postFxControl4",112:"postFxControl5"}
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
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic!="mov" or len(i.operands)!=2:continue
            dst,src=i.operands
            if dst.type!=X86_OP_MEM or src.type!=X86_OP_IMM:continue
            val=int(src.imm)&0xffffffff
            if val not in TARGETS:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            rows.append({
              "accessor":TARGETS[val],"enumValue":val,"instruction":rr(i),"section":s["name"],
              "destination":{"baseReg":md.reg_name(dst.mem.base) if dst.mem.base else None,
                             "indexReg":md.reg_name(dst.mem.index) if dst.mem.index else None,
                             "scale":dst.mem.scale,"disp":int(dst.mem.disp),
                             "size":dst.size},
              "contextBefore":[rr(x) for x in ins[lo:n]],
              "contextAfter":[rr(x) for x in ins[n+1:hi]]
            })
    summary={}
    for enum,acc in TARGETS.items():
        hits=[r for r in rows if r["enumValue"]==enum]
        summary[acc]={"enumValue":enum,"memoryImmediateWriterCount":len(hits),
                      "addresses":[r["instruction"]["address"] for r in hits],
                      "recordPlus4ShapeCount":sum(r["destination"]["disp"]==4 for r in hits)}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact immediate-to-memory decoded operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "type1Contract":{"enumOffset":4,"enumWidthBytes":4,"recordType":1},
      "summary":summary,"rows":rows,
      "proofBoundary":"Exact dynamic-construction candidate locator only. A matching immediate write is not automatically a type-1 record; base/index provenance, neighboring size/type/lane fields, runtime reachability and stream ownership require subsequent joins."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
