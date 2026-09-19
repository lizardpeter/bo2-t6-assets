#!/usr/bin/env python3
"""Two-level exact current-client pointer-chain probe for retained spawn parser strings.

For each exact C string:
  string VA -> every raw-backed dword equal to that VA -> every decoded executable
  operand equal to the dword-entry VA.
This preserves both levels explicitly and does not promote table proximity or
source-style string text into function identity.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-spawn-string-pointer-chain-v1"
TARGETS=[
 "G_ParseSpawnVars: MAX_SPAWN_VARS",
 "G_AddSpawnVarToken: MAX_SPAWN_VARS",
 "G_ParseSpawnVars: found %s when expecting {",
 "G_ParseSpawnVars: closing brace without data",
 "G_ParseSpawnVars: EOF without closing brace",
 "SpawnEntities: no entities",
]
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
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"executable":bool(ch&0x20000000)})
    return ib,secs
def offset_va(secs,o):
    for s in secs:
      if s["rawOffset"]<=o<s["rawOffset"]+s["rawSize"]:return s["va"]+o-s["rawOffset"],s
    return None,None
def find_cstr(raw,secs,t):
    needle=t.encode()+b"\0";out=[];p=0
    while True:
      p=raw.find(needle,p)
      if p<0:break
      va,s=offset_va(secs,p)
      if va is not None:out.append((p,va,s))
      p+=1
    return out
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw)
    targets={}
    entry_to_target={}
    for t in TARGETS:
      occ=find_cstr(raw,secs,t);req(len(occ)==1,f"{t}: occurrence count {len(occ)}")
      ro,va,s=occ[0];packed=struct.pack("<I",va);entries=[];p=0
      while True:
        p=raw.find(packed,p)
        if p<0:break
        eva,es=offset_va(secs,p)
        if eva is not None:
          rec={"rawOffset":p,"va":f"0x{eva:08x}","section":es["name"],"sectionExecutable":es["executable"]}
          entries.append(rec);entry_to_target.setdefault(eva,[]).append(t)
        p+=1
      targets[t]={"string":{"rawOffset":ro,"va":f"0x{va:08x}","section":s["name"]},"pointerEntries":entries}
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    xrefs=[]
    for s in secs:
      if not s["executable"]:continue
      blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      ins=list(md.disasm(blob,s["va"]))
      for n,i in enumerate(ins):
        hits=[]
        for op in i.operands:
          if op.type==X86_OP_IMM:v=int(op.imm)&0xffffffff
          elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0:v=int(op.mem.disp)&0xffffffff
          else:continue
          if v in entry_to_target:hits.append(v)
        if hits:
          lo=max(0,n-20);hi=min(len(ins),n+21)
          xrefs.append({"instruction":row(i),"section":s["name"],
            "pointerEntryVas":[f"0x{x:08x}" for x in sorted(set(hits))],
            "targetStrings":sorted({t for x in hits for t in entry_to_target[x]}),
            "before":[row(z) for z in ins[lo:n]],"after":[row(z) for z in ins[n+1:hi]]})
    for t in TARGETS:
      evas={int(x["va"],16) for x in targets[t]["pointerEntries"]}
      targets[t]["decodedSecondLevelXrefs"]=[x for x in xrefs if any(int(v,16) in evas for v in x["pointerEntryVas"])]
    summary={"targetStringCount":len(TARGETS),
      "pointerEntryCount":sum(len(x["pointerEntries"]) for x in targets.values()),
      "decodedSecondLevelXrefCount":len(xrefs),
      "targetsWithSecondLevelXrefs":sum(bool(x["decodedSecondLevelXrefs"]) for x in targets.values())}
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"targets":targets,
      "proofBoundary":"Exact two-level pointer chain only. A decoded executable operand is linked only when it equals the exact VA of a raw-backed dword whose exact value is the target C-string VA. String labels remain locators and no function identity, SpawnVar semantics, MapEnt ownership, or historical-retail equivalence is promoted solely from this chain."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
