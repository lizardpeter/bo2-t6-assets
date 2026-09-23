#!/usr/bin/env python3
"""Locate current-client GfxRenderTarget table geometry from exact access patterns.

Source-lineage usages are locator-only:
  codeImages[8] <- gfxRenderTargets[1].image
  width/height <- gfxRenderTargets[2]
  callback(gfxRenderTargets[25].image)

This scanner does NOT assume the table base/stride. It finds absolute .data/.bss
memory operands clustered in functions that also contain independently recognizable
handler shapes, and ranks arithmetic progressions that satisfy one common stride for
entry 1,2,25 fields. Later proof must anchor semantics.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-target-table-geometry-locator-v1"
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
      secs.append({"name":name,"va":ib+rva,"virtualSize":vs,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def abs_mem(i):
    out=[]
    for op in getattr(i,"operands",[]):
      if op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and op.mem.disp:
        out.append(int(op.mem.disp)&0xffffffff)
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    # Retain every absolute data operand in executable sections, grouped by 0x400-byte local function-like windows.
    ops=[]
    data_ranges=[(s["va"],s["va"]+max(s["virtualSize"],s["rawSize"]),s["name"]) for s in secs if not s["exec"]]
    def data_section(v):
      for lo,hi,n in data_ranges:
        if lo<=v<hi:return n
      return None
    for s in secs:
      if not s["exec"]:continue
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      for i in ins:
        for v in abs_mem(i):
          ds=data_section(v)
          if ds:ops.append({"instruction":row(i),"targetVa":v,"targetVaHex":f"0x{v:08x}","targetSection":ds})
    # Candidate strides: table must fit 72 entries and be 4-byte aligned; keep common practical sizes.
    strides=[x for x in range(16,257,4)]
    byva={}
    for x in ops:byva.setdefault(x["targetVa"],[]).append(x)
    candidates=[]
    vas=sorted(byva)
    # Any three addresses that can represent entry1 field F, entry2 field W/H near same record,
    # and entry25 same field F. Rank only; do not promote.
    for stride in strides:
      delta24=24*stride
      for a1 in vas:
        a25=a1+delta24
        if a25 not in byva:continue
        base=a1-stride
        if base<ib:continue
        # collect observed absolute operands inside the first few entries for diagnostics
        near=[v for v in vas if base<=v<base+3*stride]
        if len(near)<2:continue
        candidates.append({
          "candidateBaseVa":base,"candidateBaseVaHex":f"0x{base:08x}","strideBytes":stride,
          "entry1FieldVa":a1,"entry25SameFieldVa":a25,
          "entry1Refs":byva[a1][:12],"entry25Refs":byva[a25][:12],
          "firstThreeEntryObservedVas":[f"0x{x:08x}" for x in near],
          "score":len(byva[a1])+len(byva[a25])+len(near)
        })
    candidates.sort(key=lambda x:(-x["score"],x["strideBytes"],x["candidateBaseVa"]))
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded absolute memory operands; OpenBO2 usages are locator motivation only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"absoluteDataOperandOccurrenceCount":len(ops),"uniqueAbsoluteDataTargetCount":len(byva),
                 "candidateBaseStrideCount":len(candidates)},
      "candidates":candidates[:500],
      "proofBoundary":"Locator only. Candidate base/stride rows are arithmetic rankings from exact absolute client operands. No row is promoted as gfxRenderTargets, no field is assigned image/width/height semantics, and source-lineage index relationships are not retail/current-client proof until a dedicated dataflow projector closes them."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in candidates[:20]:print(x["candidateBaseVaHex"],x["strideBytes"],x["score"],f"0x{x['entry1FieldVa']:08x}",f"0x{x['entry25SameFieldVa']:08x}")
if __name__=="__main__":main()
