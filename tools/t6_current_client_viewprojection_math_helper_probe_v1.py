#!/usr/bin/env python3
"""Probe exact current-client math helpers used by base-16 code-matrix derivation."""
from __future__ import annotations
import argparse,hashlib,json,struct,string
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-viewprojection-math-helper-probe-v1"
TARGETS={"matrixHelper":0x005866b0,"vectorHelper":0x0064d510}
SEARCH=0x1200

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
def vaoff(secs,va):
    for s in secs:
      if s["va"]<=va<s["va"]+s["rawSize"]:return s,s["rawOffset"]+va-s["va"]
    raise E(f"VA 0x{va:x} unbacked")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def function(raw,secs,target):
    s,o=vaoff(secs,target);sec0=s["rawOffset"];sec1=sec0+s["rawSize"]
    before=raw[max(sec0,o-SEARCH):o];p=before.rfind(b"\xcc"*8)
    start_off=max(sec0,o-SEARCH)+p+8 if p>=0 else o
    while start_off<o and raw[start_off]==0xcc:start_off+=1
    # If target is an exported/internal entry inside a larger function, preserve target as entry instead
    # rather than falsely extending backwards.
    if s["va"]+(start_off-sec0)!=target:start_off=o
    after=raw[o:min(sec1,o+SEARCH)];q=after.find(b"\xcc"*8);req(q>0,f"no end pad for 0x{target:x}")
    end_off=o+q;blob=raw[start_off:end_off];start=s["va"]+(start_off-sec0);end=s["va"]+(end_off-sec0)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=list(md.disasm(blob,start));req(ins and ins[0].address==target,f"decode entry drift 0x{target:x}")
    calls=[]
    for i in ins:
      if i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
        calls.append({"callVa":f"0x{i.address:08x}","targetVa":f"0x{int(i.operands[0].imm)&0xffffffff:08x}","bytes":i.bytes.hex()})
    return {"startVa":f"0x{start:08x}","endVaExclusive":f"0x{end:08x}","bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),
            "instructionCount":len(ins),"instructions":[row(i) for i in ins],"directCalls":calls}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);funcs={k:function(raw,secs,v) for k,v in TARGETS.items()}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact INT3-bounded helper bytes called by exact base-16 matrix derive path",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "helpers":funcs,
      "summary":{k:{"entryVa":f"0x{TARGETS[k]:08x}","bytes":v["bytes"],"instructionCount":v["instructionCount"],"directCallCount":len(v["directCalls"])} for k,v in funcs.items()},
      "proofBoundary":"Exact helper bytes only. Labels matrixHelper/vectorHelper describe call-site roles, not promoted source symbols. A dedicated semantics projector must prove the arithmetic and argument order before these helpers are treated as matrix multiply/vector transform."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
