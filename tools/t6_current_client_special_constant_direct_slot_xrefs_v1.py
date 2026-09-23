#!/usr/bin/env python3
"""Locate direct current-client provider references for all retained-special constants.

Uses exact current-client generic code-constant storage proven by the materialColor
closure:
  values:  0x03A37300 + enum * 16 + {0,4,8,12}
  version: 0x03A382E0 + enum * 2

The denominator comes from the exact 37-input retained-special static identity proof.
Only constant-class rows are scanned. Direct decoded operands are retained; no
provider semantics are promoted by this locator.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
DEN_FMT="t6-retail-special-omitted-code-input-static-identity-v1"
FORMAT="t6-current-client-special-constant-direct-slot-xrefs-v1"
VALUE_BASE=0x03A37300
VERSION_BASE=0x03A382E0
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
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True)
    ap.add_argument("--denominator",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    den=json.loads(a.denominator.read_text());req(den.get("format")==DEN_FMT,"denominator format drift")
    constants=[x for x in den["rows"] if x["sourceClass"]=="constant"]
    req(len(constants)==32,f"expected 32 constants, got {len(constants)}")
    target_map={}
    meta={}
    for x in constants:
      e=int(x["enumValue"]);acc=x["accessor"]
      slots=[VALUE_BASE+e*16+j*4 for j in range(4)]
      ver=VERSION_BASE+e*2
      meta[acc]={"accessor":acc,"enumValue":e,"enumSymbol":x["enumSymbol"],"totalOccurrences":x["totalOccurrences"],
                 "valueVas":[f"0x{v:08x}" for v in slots],"versionVa":f"0x{ver:08x}"}
      for j,v in enumerate(slots):target_map.setdefault(v,[]).append((acc,f"value[{j}]"))
      target_map.setdefault(ver,[]).append((acc,"version"))
    ib,secs=pe(raw);hits=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      for n,i in enumerate(ins):
        refs=[]
        for oi,op in enumerate(i.operands):
          vals=[]
          if op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and op.mem.disp:
            vals.append((int(op.mem.disp)&0xffffffff,"absolute-memory",oi))
          elif op.type==X86_OP_IMM:
            vals.append((int(op.imm)&0xffffffff,"immediate",oi))
          for v,kind,oi2 in vals:
            if v in target_map:
              for acc,field in target_map[v]:
                refs.append({"accessor":acc,"field":field,"targetVa":f"0x{v:08x}","kind":kind,"operandIndex":oi2,
                             "positionClass":"destination-or-rmw" if oi2==0 and i.mnemonic not in ("cmp","test") else "source-or-other"})
        if refs:
          lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
          hits.append({"section":s["name"],"instruction":row(i),"references":refs,
            "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]})
    rows=[]
    for x in constants:
      acc=x["accessor"];ah=[h for h in hits if any(r["accessor"]==acc for r in h["references"])]
      fields={}
      for h in ah:
        for r in h["references"]:
          if r["accessor"]==acc:fields[r["field"]]=fields.get(r["field"],0)+1
      rows.append({**meta[acc],"directXrefInstructionCount":len(ah),"fieldXrefCounts":fields,
                   "directDestinationOrRmwCount":sum(any(r["accessor"]==acc and r["positionClass"]=="destination-or-rmw" for r in h["references"]) for h in ah),
                   "xrefs":ah})
    summary={
      "constantInputCount":len(rows),
      "constantsWithAnyDirectXref":sum(x["directXrefInstructionCount"]>0 for x in rows),
      "constantsWithDirectDestinationOrRmw":sum(x["directDestinationOrRmwCount"]>0 for x in rows),
      "totalDirectXrefInstructions":len(hits),
      "valueBaseVa":f"0x{VALUE_BASE:08x}","versionBaseVa":f"0x{VERSION_BASE:08x}"
    }
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded operands + exact current-client generic code-constant storage + exact retained-special constant denominator",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"rows":rows,
      "proofBoundary":"Locator only. Exact direct operands to mathematically derived current-client constant value/version slots are retained. Destination-position diagnostics do not by themselves prove producer formulas, command ownership, update timing, draw-time values, or historical-retail equivalence. Constants accessed only through generic indexed helpers may legitimately have zero direct xrefs."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for x in rows:
      if x["directXrefInstructionCount"]:print(x["accessor"],x["enumValue"],x["directXrefInstructionCount"],x["directDestinationOrRmwCount"],x["fieldXrefCounts"])
if __name__=="__main__":main()
