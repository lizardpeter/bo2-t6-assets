#!/usr/bin/env python3
"""Locate current-client clipMap submodel consumers using exact T6 PC32 layout.

Inputs:
- SHA-classified rev-5346 client.
- structural clipMap base candidates.
- independently fixed PC32 offsets: numSubModels +0x90, cmodels +0x94.
- independently fixed T6 cmodel_t size 76 (0x4c).

A retained window must reference BOTH exact absolute addresses for the same
candidate base. Stride-related instructions are diagnostic until a later
dataflow projector proves handle -> cmodels[handle].
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-clipmap-submodel-consumer-locator-v1"
NUM_OFF=0x90
CMODEL_OFF=0x94
CMODEL_SIZE=0x4c
RADIUS=28

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
def abs_refs(i):
    out=set()
    for op in i.operands:
      if op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0:
        out.add(int(op.mem.disp)&0xffffffff)
    return out
def imms(i):
    return [int(op.imm)&0xffffffff for op in i.operands if op.type==X86_OP_IMM]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--candidates",type=Path,required=True);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    cand=json.loads(a.candidates.read_text());req(cand.get("format")=="t6-current-client-clipmap-global-layout-candidates-v1","candidate format drift")
    req(cand["client"]["sha256"]==dg,"candidate/client SHA mismatch")
    bases=[int(x["baseVa"],16) for x in cand.get("candidates",[])]
    req(bases,"no clipMap candidates")
    target_to_base=collections.defaultdict(list)
    for base in bases:
      target_to_base[base+NUM_OFF].append((base,"numSubModels"))
      target_to_base[base+CMODEL_OFF].append((base,"cmodels"))
    ib,secs=pe(raw);windows=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      refs_by_n=[]
      for n,i in enumerate(ins):
        hits=[]
        for va in abs_refs(i):
          hits.extend(target_to_base.get(va,[]))
        if hits:refs_by_n.append((n,i,hits))
      # For each candidate base, require both field kinds within +/- radius.
      by_base=collections.defaultdict(list)
      for n,i,hits in refs_by_n:
        for base,kind in hits:by_base[base].append((n,i,kind))
      for base,items in by_base.items():
        nums=[n for n,i,k in items if k=="numSubModels"]
        cms=[n for n,i,k in items if k=="cmodels"]
        for n0 in nums:
          near=[n1 for n1 in cms if abs(n1-n0)<=RADIUS]
          if not near:continue
          lo=max(0,min([n0]+near)-RADIUS);hi=min(len(ins),max([n0]+near)+RADIUS+1)
          seq=ins[lo:hi]
          exact_refs=[]
          stride_diag=[]
          for z in seq:
            ar=abs_refs(z)
            kinds=[]
            if base+NUM_OFF in ar:kinds.append("numSubModels")
            if base+CMODEL_OFF in ar:kinds.append("cmodels")
            if kinds:exact_refs.append({"instruction":row(z),"fields":kinds})
            vals=imms(z)
            if CMODEL_SIZE in vals or 19 in vals:
              stride_diag.append({"instruction":row(z),"immediates":[v for v in vals if v in (CMODEL_SIZE,19)]})
          key=(base,ins[lo].address,ins[hi-1].address)
          windows.append({
            "candidateBaseVa":f"0x{base:08x}",
            "numSubModelsVa":f"0x{base+NUM_OFF:08x}",
            "cmodelsVa":f"0x{base+CMODEL_OFF:08x}",
            "section":s["name"],
            "windowStartVa":f"0x{ins[lo].address:08x}",
            "windowEndVa":f"0x{ins[hi-1].address+len(ins[hi-1].bytes):08x}",
            "exactFieldReferences":exact_refs,
            "cmodelStrideDiagnostics":stride_diag,
            "instructions":[row(z) for z in seq],
          })
    # Dedup overlapping windows by exact candidate and field-reference instruction set.
    uniq={}
    for w in windows:
      k=(w["candidateBaseVa"],tuple((r["instruction"]["address"],tuple(r["fields"])) for r in w["exactFieldReferences"]))
      uniq[k]=w
    rows=sorted(uniq.values(),key=lambda x:(x["candidateBaseVa"],x["windowStartVa"]))
    bybase=collections.Counter(x["candidateBaseVa"] for x in rows)
    summary={
      "inputCandidateCount":len(bases),
      "candidateWithPairedFieldWindowCount":len(bybase),
      "pairedFieldWindowCount":len(rows),
      "pairedFieldWindowWithStrideDiagnosticCount":sum(bool(x["cmodelStrideDiagnostics"]) for x in rows),
      "candidateBasesWithStrideDiagnostic":sorted({x["candidateBaseVa"] for x in rows if x["cmodelStrideDiagnostics"]}),
    }
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact absolute memory operands + independent T6 PC32 clipMap offsets and cmodel_t size",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "nativeLayout":{"numSubModelsOffset":NUM_OFF,"cmodelsOffset":CMODEL_OFF,"cmodelRecordBytes":CMODEL_SIZE},
      "summary":summary,"windows":rows,
      "proofBoundary":"Locator only. Every row exactly co-references one structural candidate's numSubModels and cmodels absolute addresses. 0x4c/19 immediates are retained only as stride diagnostics. No candidate base, function identity, handle dataflow, bounds semantics, cmodels indexing, parsed entity model ownership, or historical-retail equivalence is promoted here."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for x in rows:print(x["candidateBaseVa"],x["windowStartVa"],len(x["cmodelStrideDiagnostics"]))
if __name__=="__main__":main()
