#!/usr/bin/env python3
"""Locate current-client T6 code-constant setter/assertion paths.

Searches exact raw-backed strings that describe:
- g_codeConstUpdateFreq custom/rare assertion,
- CONST_SRC_CODE_COUNT_FLOAT4 bounds,
- source->constVersions bounds,
- r_state.h / r_shade.cpp source paths.

All decoded executable operands equal to exact string VAs are retained with
wide context. String/source-line semantics are locators; later proof must bind
specific stores and enum identities.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-constant-assertion-xref-v1"
NEEDLES=(
 "g_codeConstUpdateFreq[constant]",
 "CONST_SRC_CODE_COUNT_FLOAT4",
 "source->constVersions",
 "r_state.h",
 "r_shade.cpp",
)
CTX=64

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
def offva(secs,off):
    for s in secs:
      if s["rawOffset"]<=off<s["rawOffset"]+s["rawSize"]:return s["va"]+off-s["rawOffset"],s
    return None,None
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);strings=[]
    for m in re.finditer(rb"[\x20-\x7e]{4,}\x00",raw):
      b=m.group()[:-1]
      try:t=b.decode("ascii")
      except:continue
      if not any(n.lower() in t.lower() for n in NEEDLES):continue
      va,s=offva(secs,m.start())
      if va is not None:strings.append({"text":t,"va":va,"vaHex":f"0x{va:08x}","rawOffset":m.start(),"section":s["name"]})
    targets={x["va"]:x for x in strings};refs=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      for n,i in enumerate(ins):
        hits=set()
        for op in i.operands:
          if op.type==X86_OP_IMM and (int(op.imm)&0xffffffff) in targets:hits.add(int(op.imm)&0xffffffff)
          elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and (int(op.mem.disp)&0xffffffff) in targets:hits.add(int(op.mem.disp)&0xffffffff)
        if not hits:continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        refs.append({"section":s["name"],"instruction":row(i),
          "targetStrings":[targets[v]["text"] for v in sorted(hits)],
          "targetVas":[f"0x{v:08x}" for v in sorted(hits)],
          "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]})
    byneedle={n:sum(n.lower() in x["text"].lower() for x in strings) for n in NEEDLES}
    xbyneedle={n:sum(any(n.lower() in t.lower() for t in r["targetStrings"]) for r in refs) for n in NEEDLES}
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client exact raw strings and decoded executable operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"relevantStringCount":len(strings),"decodedXrefCount":len(refs),"stringCountsByNeedle":byneedle,"xrefCountsByNeedle":xbyneedle},
      "strings":strings,"xrefs":refs,
      "proofBoundary":"Exact string/xref locator evidence only. Source filenames/assert text may identify likely renderer invariants but do not assign function names, GfxCmdBufInput addresses, enum values, setter semantics, HDR formulas, or historical-retail equivalence until later client-only dataflow proof."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
