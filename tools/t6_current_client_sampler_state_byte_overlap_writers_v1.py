#!/usr/bin/env python3
"""Exact current-client destination-store overlap census for sampler-state bytes 6 and 16.

Retain every decoded destination memory operand [base + disp] whose fixed byte
write interval covers generic source-state sampler byte offset 0x1612 (slot 6)
or 0x161C (slot 16), regardless of the store's starting displacement.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-sampler-state-byte-overlap-writers-v1"
TARGETS={"shadowmapSamplerSun":0x1612,"dlightAttenuationSampler":0x161C}
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
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows={k:[] for k in TARGETS}
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic in READ_ONLY or not i.operands:continue
            op=i.operands[0]
            if op.type!=X86_OP_MEM or op.size<=0 or op.mem.base==0 or op.mem.index!=0:continue
            lo=int(op.mem.disp);hi=lo+int(op.size)
            matched=[acc for acc,t in TARGETS.items() if lo<=t<hi]
            if not matched:continue
            a0=max(0,n-CTX);a1=min(len(ins),n+CTX+1)
            rec={"instruction":rr(i),"section":s["name"],"baseReg":md.reg_name(op.mem.base),
                 "disp":lo,"widthBytes":int(op.size),"coveredRange":[lo,hi],
                 "contextBefore":[rr(x) for x in ins[a0:n]],"contextAfter":[rr(x) for x in ins[n+1:a1]]}
            for acc in matched:rows[acc].append(rec)
    summary={acc:{"targetOffset":t,"writerInstructionCount":len(rows[acc]),
                  "writerAddresses":[x["instruction"]["address"] for x in rows[acc]]}
             for acc,t in TARGETS.items()}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded destination-memory byte ranges",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"rows":rows,
      "proofBoundary":"Closes only the decoded fixed-width base-register-relative destination-store denominator overlapping generic sampler-state bytes 0x1612 and 0x161C. Base object identity, branch reachability, final values, resource ownership and historical-retail equivalence remain separate semantic gates."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
