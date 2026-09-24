#!/usr/bin/env python3
"""Freeze late 0x009AF970 source-state helpers and classify code-image/state writes."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadow-builder-late-helpers-v1"
TARGETS=(0x009A7A90,0x009A7B20)
CODE_IMAGES_BASE=0x1530
SAMPLER_STATES_BASE=0x160C
SAMPLER_END=0x1680
SEARCH=0x8000
CTX=36

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
def secfor(secs,va):
    for s in secs:
      if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"VA 0x{va:x} not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def body(raw,s,anchor):
    ro=s["rawOffset"]+anchor-s["va"];lo=max(s["rawOffset"],ro-SEARCH);hi=min(s["rawOffset"]+s["rawSize"],ro+SEARCH)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(raw[lo:hi],s["va"]+lo-s["rawOffset"]) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==anchor),None);req(n is not None,f"{anchor:x} missing")
    p=-1
    for k in range(n-1,-1,-1):
      if ins[k].mnemonic=="int3":
        while k+1<n and ins[k+1].mnemonic=="int3":k+=1
        p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
      if ins[k].mnemonic=="int3":q=k;break
    out=ins[p+1:q];req(out and out[0].address==anchor,f"{anchor:x} function-start drift")
    return out
def callers(raw,secs,target):
    out=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
      if not s["exec"]:continue
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
        if (int(i.operands[0].imm)&0xffffffff)!=target:continue
        out.append({"call":rr(i),"section":s["name"],
          "contextBefore":[rr(x) for x in ins[max(0,n-CTX):n]],
          "contextAfter":[rr(x) for x in ins[n+1:min(len(ins),n+CTX+1)]]})
    return out
def classify_writes(ins):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    out=[]
    # Re-disassemble individual bytes for reliable operand metadata.
    for src in ins:
      di=next(md.disasm(src.bytes,src.address),None)
      if di is None or not di.operands:continue
      op=di.operands[0]
      if op.type!=X86_OP_MEM:continue
      disp=int(op.mem.disp)
      kind=None;slot=None
      if CODE_IMAGES_BASE<=disp<SAMPLER_STATES_BASE and (disp-CODE_IMAGES_BASE)%4==0:
        kind="codeImage";slot=(disp-CODE_IMAGES_BASE)//4
      elif SAMPLER_STATES_BASE<=disp<SAMPLER_END:
        kind="samplerStateRegion"
      if kind:
        out.append({"kind":kind,"slot":slot,"instruction":rr(src),
          "memory":{"baseReg":md.reg_name(op.mem.base) if op.mem.base else None,
                    "indexReg":md.reg_name(op.mem.index) if op.mem.index else None,
                    "scale":op.mem.scale,"disp":disp,"size":op.size}})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows=[]
    for target in TARGETS:
      s=secfor(secs,target);ins=body(raw,s,target);writes=classify_writes(ins);cc=callers(raw,secs,target)
      rows.append({"entryVa":f"0x{target:08x}","instructionCount":len(ins),"instructions":[rr(x) for x in ins],
                   "classifiedWrites":writes,"callers":cc})
    summary={r["entryVa"]:{"instructionCount":r["instructionCount"],"callerCount":len(r["callers"]),
                           "classifiedWriteCount":len(r["classifiedWrites"]),
                           "codeImageSlots":sorted({w["slot"] for w in r["classifiedWrites"] if w["kind"]=="codeImage"})} for r in rows}
    doc={"format":FORMAT,"authority":"SHA-classified exact helper bodies/callers plus canonical code-image/state offset classification",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "geometry":{"codeImagesBase":CODE_IMAGES_BASE,"samplerStatesBase":SAMPLER_STATES_BASE},
      "summary":summary,"helpers":rows,
      "proofBoundary":"Exact destination-offset classification only. A classified write still requires base-pointer provenance and source-resource semantics before it closes a code-sampler provider."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
