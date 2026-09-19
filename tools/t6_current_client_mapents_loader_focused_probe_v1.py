#!/usr/bin/env python3
"""Focused current-client probe around exact .mapents format-string references."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-mapents-loader-focused-probe-v1"
RANGE=(0x0064eb80,0x0064ee40)
TARGETS={0x00c41d00:"maps/mp/%s.mapents",0x00c2a890:"maps/%s.mapents"}
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
def locate(secs,va,n=1):
    for s in secs:
      if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:return s,s["rawOffset"]+va-s["va"]
    raise E(f"unbacked VA 0x{va:x}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def rel_calls(raw,secs,lo,hi):
    out=[]
    for s in secs:
      if not s["executable"]:continue
      b=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      for p in range(len(b)-5):
        if b[p]!=0xe8:continue
        va=s["va"]+p;disp=struct.unpack_from("<i",b,p+1)[0];t=(va+5+disp)&0xffffffff
        if lo<=t<hi:out.append({"callVa":f"0x{va:08x}","targetVa":f"0x{t:08x}","bytes":b[p:p+5].hex(),"section":s["name"]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw);start,end=RANGE;s,o=locate(secs,start,end-start);blob=raw[o:o+end-start]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=list(md.disasm(blob,start));refs=[]
    for i in ins:
      hits=[]
      for op in i.operands:
        if op.type==X86_OP_IMM and (int(op.imm)&0xffffffff) in TARGETS:hits.append(int(op.imm)&0xffffffff)
        elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and (int(op.mem.disp)&0xffffffff) in TARGETS:hits.append(int(op.mem.disp)&0xffffffff)
      if hits:refs.append({"instruction":row(i),"targets":[{"va":f"0x{x:08x}","text":TARGETS[x]} for x in sorted(set(hits))]})
    calls=rel_calls(raw,secs,start,end)
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "range":{"startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}","section":s["name"],"sha256":hashlib.sha256(blob).hexdigest(),"instructions":[row(i) for i in ins]},
      "exactMapentsStringOperandReferences":refs,"directRel32CallsIntoRange":calls,
      "proofBoundary":"Exact bounded client bytes/disassembly and decoded operand references to the two .mapents format strings, plus raw rel32 direct-call targets into this range. Range membership or format-string use alone does not prove gameplay MapEnt asset ownership, SpawnVar parser dataflow, or historical-retail equivalence."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"instructionCount":len(ins),"exactStringRefCount":len(refs),"directCallerCount":len(calls)},indent=2))
if __name__=="__main__":main()
