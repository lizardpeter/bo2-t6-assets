#!/usr/bin/env python3
"""Locate current-client front-end RC_SET_CUSTOM_CONSTANT producer candidates for light enums.

Exact upstream handler proof establishes command record layout:
  +0 uint16 byteCount
  +4 uint32 enum
  +8,+12,+16,+20 float4 payload

This locator scans executable instructions for exact immediate stores of retained
light enum values to [base+4], then retains a bounded function-local neighborhood
and same-base stores to record offsets 0,8,12,16,20. It is locator evidence only.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-light-custom-constant-producer-locator-v1"
LIGHT_ENUMS={
 0:"lightPosition",1:"lightDiffuse",2:"lightSpotDir",3:"lightSpotFactors",
 5:"lightFallOffA",6:"lightFallOffB",7:"lightSpotMatrix0",8:"lightSpotMatrix1",
 9:"lightSpotMatrix2",11:"lightSpotAABB",12:"lightConeControl1",14:"lightSpotCookieSlideControl"
}
CTX=45

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
def rname(md,r):return md.reg_name(r) if r else None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        if i.mnemonic!="mov" or len(i.operands)!=2:continue
        dst,src=i.operands
        if dst.type!=X86_OP_MEM or src.type!=X86_OP_IMM:continue
        if int(dst.mem.disp)!=4:continue
        enum=int(src.imm)&0xffffffff
        if enum not in LIGHT_ENUMS:continue
        base=rname(md,dst.mem.base)
        if not base or dst.mem.index:continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        nearby=[]
        for z in ins[lo:hi]:
          for oi,op in enumerate(z.operands):
            if op.type!=X86_OP_MEM or rname(md,op.mem.base)!=base or op.mem.index:continue
            disp=int(op.mem.disp)
            if disp in (0,4,8,12,16,20):
              nearby.append({"instruction":row(z),"offset":disp,"operandIndex":oi,
                             "positionClass":"destination-or-rmw" if oi==0 and z.mnemonic not in ("cmp","test") else "source-or-other"})
        hits.append({
          "accessor":LIGHT_ENUMS[enum],"enumValue":enum,"section":s["name"],"enumStore":row(i),
          "recordBaseRegister":base,"sameBaseRecordFieldReferences":nearby,
          "contextBefore":[row(x) for x in ins[lo:n]],"contextAfter":[row(x) for x in ins[n+1:hi]]
        })
    by={name:[] for name in LIGHT_ENUMS.values()}
    for h in hits:by[h["accessor"]].append(h)
    summary={
      "candidateInstructionCount":len(hits),
      "accessorHitCounts":{k:len(v) for k,v in sorted(by.items())},
      "accessorsWithCandidateCount":sum(bool(v) for v in by.values()),
      "targetAccessorCount":len(by),
    }
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded immediate stores matching exact RC_SET_CUSTOM_CONSTANT enum-field layout",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "upstreamRecordLayout":{"enumOffset":4,"payloadOffsets":[8,12,16,20]},
      "targets":[{"enumValue":e,"accessor":LIGHT_ENUMS[e]} for e in sorted(LIGHT_ENUMS)],
      "summary":summary,"hits":hits,
      "proofBoundary":"Locator only. A candidate requires an exact mov immediate light enum to [base+4] and retains same-base command-field accesses nearby. It does not prove the base points to an RC_SET_CUSTOM_CONSTANT record, identify the allocator, promote payload formulas/source ownership, or establish historical-retail equivalence. A dedicated projector must close those gates."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for h in hits:print(h["accessor"],h["enumStore"]["address"],h["recordBaseRegister"],[(x["offset"],x["instruction"]["address"],x["positionClass"]) for x in h["sameBaseRecordFieldReferences"]])
if __name__=="__main__":main()
