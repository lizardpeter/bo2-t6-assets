#!/usr/bin/env python3
"""Locate the current-client T6 versioned code-matrix getter by structural fingerprint.

T6 static enum authority fixes CONST_SRC_FIRST_CODE_MATRIX at 0xD3.
Candidate functions are located only if a bounded decoded region contains:
- immediate 0xD3 used in arithmetic/comparison;
- group-of-four masking/alignment via immediate 0xFFFFFFFC or equivalent 0xFC;
- XOR immediate 1 and XOR immediate 2;
- at least one scale-by-64 operation (shift by 6 or multiply 0x40);
- multiple memory word/dword version-style comparisons.

No lineage formula is promoted here; this is a current-client candidate locator.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-matrix-structural-locator-v1"
WINDOW=96
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
def imms(i):
    out=[]
    if i.id==0:return out
    for op in i.operands:
      if op.type==X86_OP_IMM:out.append(int(op.imm)&0xffffffff)
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);cands=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      anchors=[n for n,i in enumerate(ins) if i.id and 0xD3 in imms(i)]
      for n in anchors:
        lo=max(0,n-WINDOW);hi=min(len(ins),n+WINDOW+1);w=[x for x in ins[lo:hi] if x.id]
        allim=[v for x in w for v in imms(x)]
        has_mask=0xFFFFFFFC in allim or 0xFC in allim
        has_x1=any(x.mnemonic=="xor" and 1 in imms(x) for x in w)
        has_x2=any(x.mnemonic=="xor" and 2 in imms(x) for x in w)
        has64=any((x.mnemonic in ("shl","sal") and 6 in imms(x)) or (x.mnemonic=="imul" and 0x40 in imms(x)) for x in w)
        cmps=sum(x.mnemonic in ("cmp","test") and ("ptr [" in x.op_str) for x in w)
        score=sum((has_mask,has_x1,has_x2,has64,cmps>=2))
        if score>=3:
          cands.append({"anchor":row(ins[n]),"score":score,"hasGroupMask":has_mask,"hasXor1":has_x1,"hasXor2":has_x2,"hasScale64":has64,
                        "memoryCompareCount":cmps,"context":[row(x) for x in w]})
    # exact anchor dedup
    uniq={x["anchor"]["address"]:x for x in cands}
    rows=[uniq[k] for k in sorted(uniq,key=lambda z:int(z,16))]
    doc={"format":FORMAT,"authority":"SHA-classified current-client decoded instruction structure + pinned T6 enum value 0xD3",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"anchorImmediateD3CandidateCount":len(rows),"highScoreCandidateCount":sum(x["score"]>=5 for x in rows)},
      "candidates":rows,
      "proofBoundary":"Locator only. Candidates are selected by exact current-client instruction structure around immediate 0xD3. The 0xD3 value is authoritative T6 enum vocabulary, but no candidate is named R_GetCodeMatrix and no matrix storage/version/provider semantics are promoted until a dedicated projector closes exact dataflow."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
