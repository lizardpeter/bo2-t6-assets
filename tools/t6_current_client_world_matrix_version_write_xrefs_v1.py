#!/usr/bin/env python3
"""Focused current-client locator for worldMatrix producer writes.

Exact upstream proof establishes:
  source+0x0000 : matrix[0] bytes (worldMatrix group base)
  source+0x1986 : constVersions[CONST_SRC_CODE_WORLD_MATRIX=211]
  source+0x19c6 : matrixVersions[0]

This locator finds every decoded executable instruction whose memory operand uses
exact displacement 0x1986 or 0x19c6, classifies destination/RMW vs source use,
and retains bounded context. It does not assume a source register or function name.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-world-matrix-version-write-xrefs-v1"
TARGETS={0x1986:"worldConstVersion",0x19c6:"worldMatrixVersion"}
CTX=70
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
    ib,secs=pe(raw);hits=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
        for n,i in enumerate(ins):
            if i.id==0:continue
            refs=[]
            for oi,op in enumerate(i.operands):
                if op.type!=X86_OP_MEM:continue
                disp=int(op.mem.disp)&0xffffffff
                if disp not in TARGETS:continue
                refs.append({"field":TARGETS[disp],"displacementHex":f"0x{disp:04x}",
                    "baseReg":i.reg_name(op.mem.base) if op.mem.base else None,
                    "indexReg":i.reg_name(op.mem.index) if op.mem.index else None,
                    "scale":op.mem.scale,"operandIndex":oi,
                    "positionClass":"destination-or-rmw" if oi==0 and i.mnemonic not in ("cmp","test") else "source-or-other"})
            if refs:
                lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
                hits.append({"section":s["name"],"instruction":row(i),"references":refs,
                    "contextBefore":[row(x) for x in ins[lo:n]],"contextAfter":[row(x) for x in ins[n+1:hi]]})
    summary={
      "hitInstructionCount":len(hits),
      "worldConstVersionHitCount":sum(any(r["field"]=="worldConstVersion" for r in h["references"]) for h in hits),
      "worldMatrixVersionHitCount":sum(any(r["field"]=="worldMatrixVersion" for r in h["references"]) for h in hits),
      "destinationOrRmwHitCount":sum(any(r["positionClass"]=="destination-or-rmw" for r in h["references"]) for h in hits),
    }
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded memory operands + previously proven matrix-getter offsets",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "provenUpstream":{"worldMatrixEnum":211,"worldConstVersionOffset":0x1986,"worldMatrixVersionOffset":0x19c6,
        "matrixStorageBaseOffset":0,"matrixStrideBytes":64},
      "summary":summary,"hits":hits,
      "proofBoundary":"Locator only. Exact source-relative displacement uses are retained without assuming the base register is GfxCmdBufSourceState. A dedicated projector must close function extent, source-base identity, world matrix writes, version relation, and formula before worldMatrix is provider-closed."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for h in hits:print(h["instruction"]["address"],h["instruction"]["mnemonic"],h["instruction"]["opStr"],h["references"])
if __name__=="__main__":main()
