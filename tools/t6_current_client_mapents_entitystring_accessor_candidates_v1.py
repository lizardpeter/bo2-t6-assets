#!/usr/bin/env python3
"""Locate exact current-client candidates for clipMap.mapEnts->entityString access.

Native PC32 evidence independently fixes clipMap.mapEnts at +0xA8 and
MapEnts.entityString at +4. This scanner does not assign CM_EntityString by
shape. It reports short executable sequences that:
  A) load a pointer from absolute memory, then dereference +4 and return; or
  B) load a base/global pointer, dereference +0xA8, then +4 and return.
For each candidate it retains exact bounded instructions and raw rel32 callers.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-mapents-entitystring-accessor-candidates-v1"
REG=r"(eax|ebx|ecx|edx|esi|edi|ebp)"
ABS_RE=re.compile(rf"^({REG}), dword ptr \[(0x[0-9a-f]+)\]$")
DEREF4_RE=re.compile(rf"^({REG}), dword ptr \[({REG}) \+ 4\]$")
DEREFA8_RE=re.compile(rf"^({REG}), dword ptr \[({REG}) \+ 0xa8\]$")

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
def raw_callers(raw,secs,target):
    out=[]
    for s in secs:
      if not s["exec"]:continue
      b=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      for p in range(len(b)-5):
        if b[p]!=0xe8:continue
        va=s["va"]+p;disp=struct.unpack_from("<i",b,p+1)[0]
        if ((va+5+disp)&0xffffffff)==target:
          out.append({"callVa":f"0x{va:08x}","bytes":b[p:p+5].hex(),"section":s["name"]})
    return out
def short_end(ins,start_index,max_after=6):
    return ins[start_index:min(len(ins),start_index+max_after)]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;candidates=[]
    for s in secs:
      if not s["exec"]:continue
      blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];ins=list(md.disasm(blob,s["va"]))
      for n,i in enumerate(ins):
        if i.mnemonic!="mov":continue
        m=ABS_RE.match(i.op_str)
        if not m:continue
        first_reg=m.group(1);abs_addr=int(m.group(3),16)
        seq=short_end(ins,n,8)
        # Shape A: absolute slot is already clipMap.mapEnts, then +4.
        for j in range(1,min(len(seq),5)):
          q=seq[j]
          m4=DEREF4_RE.match(q.op_str) if q.mnemonic=="mov" else None
          if not m4 or m4.group(4)!=first_reg:continue
          if not any(z.mnemonic=="ret" for z in seq[j+1:j+4]):continue
          start=i.address
          candidates.append({"shape":"absolute-mapents-slot-then-entityString+4","startVa":f"0x{start:08x}",
            "absoluteLoadVa":f"0x{abs_addr:08x}","instructions":[row(z) for z in seq[:min(j+4,len(seq))]],
            "rawRel32Callers":raw_callers(raw,secs,start)})
        # Shape B: absolute slot/base pointer -> +A8 -> +4.
        for j in range(1,min(len(seq),4)):
          qa=seq[j];ma=DEREFA8_RE.match(qa.op_str) if qa.mnemonic=="mov" else None
          if not ma or ma.group(4)!=first_reg:continue
          a8_reg=ma.group(1)
          for k in range(j+1,min(len(seq),6)):
            q4=seq[k];m4=DEREF4_RE.match(q4.op_str) if q4.mnemonic=="mov" else None
            if not m4 or m4.group(4)!=a8_reg:continue
            if not any(z.mnemonic=="ret" for z in seq[k+1:k+4]):continue
            start=i.address
            candidates.append({"shape":"absolute-base-then-mapEnts+0xA8-then-entityString+4","startVa":f"0x{start:08x}",
              "absoluteLoadVa":f"0x{abs_addr:08x}","instructions":[row(z) for z in seq[:min(k+4,len(seq))]],
              "rawRel32Callers":raw_callers(raw,secs,start)})
    # exact candidate identity is address+shape; dedup repeated pattern discovery
    by={}
    for c in candidates:by[(c["shape"],c["startVa"])]=c
    rows=sorted(by.values(),key=lambda x:(x["shape"],x["startVa"]))
    summary={
      "candidateCount":len(rows),
      "shapeCounts":{shape:sum(r["shape"]==shape for r in rows) for shape in sorted({r["shape"] for r in rows})},
      "candidateWithDirectCallerCount":sum(bool(r["rawRel32Callers"]) for r in rows),
      "totalRawRel32CallerCount":sum(len(r["rawRel32Callers"]) for r in rows),
    }
    doc={"format":FORMAT,"authority":"SHA-classified current client exact instructions; PC32 +0xA8/+4 layout is independently source/retail-structure grounded",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "nativeLayout":{"clipMapMapEntsOffset":168,"mapEntsEntityStringOffset":4},
      "summary":summary,"candidates":rows,
      "proofBoundary":"Locator-only. A matching dereference shape is not assigned to CM_EntityString or MapEnt ownership. Absolute addresses are not labeled as clipMap globals until independent dataflow identifies them. Callers are exact raw rel32 references only; semantic promotion requires a later proof tying one candidate to the loaded clipMap/MapEnt path."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for r in rows:print(r["shape"],r["startVa"],r["absoluteLoadVa"],len(r["rawRel32Callers"]))
if __name__=="__main__":main()
