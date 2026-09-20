#!/usr/bin/env python3
"""Locate current-client pointer-relative clipMap cmodels consumers.

This does not depend on a global clipMap VA. It scans exact rev-5346 code for
bounded windows where the SAME base register is dereferenced at:
  +0x90  T6 PC32 clipMap_t.numSubModels
  +0x94  T6 PC32 clipMap_t.cmodels
and retains 0x4c/19 arithmetic plus 0xfff comparisons as diagnostics.

No semantics are promoted from offsets alone; a later projector must prove
handle bounds and cmodels[handle] address dataflow.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-clipmap-relative-submodel-locator-v1"
NUM_OFF=0x90;CMODEL_OFF=0x94;CMODEL_SIZE=0x4c;CAPSULE=0xfff
RADIUS=24

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
def fieldrefs(i):
    out=[]
    for oi,op in enumerate(i.operands):
      if op.type!=X86_OP_MEM or op.mem.base==0 or op.mem.index!=0:continue
      disp=int(op.mem.disp)
      if disp in (NUM_OFF,CMODEL_OFF):
        out.append({"operandIndex":oi,"baseReg":i.reg_name(op.mem.base),"disp":disp,"field":"numSubModels" if disp==NUM_OFF else "cmodels"})
    return out
def imms(i):
    return [int(op.imm)&0xffffffff for op in i.operands if op.type==X86_OP_IMM]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      byreg=collections.defaultdict(list)
      for n,i in enumerate(ins):
        for fr in fieldrefs(i):byreg[fr["baseReg"]].append((n,i,fr))
      for reg,items in byreg.items():
        nums=[x for x in items if x[2]["field"]=="numSubModels"]
        cms=[x for x in items if x[2]["field"]=="cmodels"]
        for n0,i0,f0 in nums:
          for n1,i1,f1 in cms:
            if abs(n1-n0)>RADIUS:continue
            lo=max(0,min(n0,n1)-RADIUS);hi=min(len(ins),max(n0,n1)+RADIUS+1);seq=ins[lo:hi]
            refs=[]
            stride=[];caps=[]
            for z in seq:
              for fr in fieldrefs(z):
                if fr["baseReg"]==reg:refs.append({"instruction":row(z),**fr})
              vals=imms(z)
              if any(v in (CMODEL_SIZE,19) for v in vals):stride.append({"instruction":row(z),"immediates":[v for v in vals if v in (CMODEL_SIZE,19)]})
              if CAPSULE in vals:caps.append({"instruction":row(z)})
            rows.append({"section":s["name"],"baseRegister":reg,"windowStartVa":f"0x{seq[0].address:08x}",
              "windowEndVa":f"0x{seq[-1].address+len(seq[-1].bytes):08x}","fieldReferences":refs,
              "strideDiagnostics":stride,"capsuleHandleDiagnostics":caps,"instructions":[row(z) for z in seq]})
    # Dedup same structural refs.
    uniq={}
    for x in rows:
      k=(x["baseRegister"],tuple((r["instruction"]["address"],r["field"]) for r in x["fieldReferences"]))
      uniq[k]=x
    rows=sorted(uniq.values(),key=lambda x:(x["windowStartVa"],x["baseRegister"]))
    summary={
      "pairedRelativeWindowCount":len(rows),
      "pairedRelativeWindowWithStrideDiagnosticCount":sum(bool(x["strideDiagnostics"]) for x in rows),
      "pairedRelativeWindowWithCapsuleDiagnosticCount":sum(bool(x["capsuleHandleDiagnostics"]) for x in rows),
      "uniqueWindowBaseRegisters":sorted({x["baseRegister"] for x in rows}),
    }
    doc={"format":FORMAT,"authority":"SHA-classified current client exact register-relative memory operands + independently fixed T6 PC32 clipMap offsets/cmodel size",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "nativeLayout":{"numSubModelsOffset":NUM_OFF,"cmodelsOffset":CMODEL_OFF,"cmodelRecordBytes":CMODEL_SIZE},
      "summary":summary,"windows":rows,
      "proofBoundary":"Locator only. Same-register +0x90/+0x94 co-reference is exact but does not alone identify clipMap_t. 0x4c/19 and 0xfff immediates are diagnostics only. Function identity, handle bounds, cmodels indexing, global object ownership, parsed entity model linkage, and historical-retail equivalence remain unpromoted."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for x in rows:print(x["windowStartVa"],x["baseRegister"],len(x["strideDiagnostics"]),len(x["capsuleHandleDiagnostics"]))
if __name__=="__main__":main()
