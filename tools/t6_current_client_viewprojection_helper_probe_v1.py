#!/usr/bin/env python3
"""Exact current-client probe of the base-16 code-matrix derive helper.

Upstream current-client proof maps baseIndex 16 to dispatcher thunk 0x772fc1,
which tail-jumps to 0x772ca0. This probe freezes the INT3-bounded function
containing 0x772ca0 and retains every direct call target and printable literal.
It is evidence for the next semantics projector; no formula is promoted here.
"""
from __future__ import annotations
import argparse,hashlib,json,struct,string
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-viewprojection-helper-probe-v1"
TARGET=0x00772ca0
SEARCH=0x900

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
def cstr(raw,secs,va,limit=300):
    try:s,o=vaoff(secs,va)
    except E:return None
    end=min(o+limit,s["rawOffset"]+s["rawSize"]);z=raw.find(b"\0",o,end)
    if z<0 or z==o:return None
    b=raw[o:z]
    if len(b)<4 or any(chr(x) not in string.printable for x in b):return None
    try:t=b.decode("ascii")
    except:return None
    return {"va":f"0x{va:08x}","section":s["name"],"text":t,"bytes":b.hex()}
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s,o=vaoff(secs,TARGET)
    sec_start=s["rawOffset"];sec_end=sec_start+s["rawSize"]
    # exact function boundaries from nearest >=8 INT3 pad; target itself should be first code byte after prior pad.
    before=raw[max(sec_start,o-SEARCH):o]
    p=before.rfind(b"\xcc"*8)
    req(p>=0,"preceding INT3 pad absent")
    start_off=max(sec_start,o-SEARCH)+p+8
    while start_off<o and raw[start_off]==0xcc:start_off+=1
    start_va=s["va"]+(start_off-sec_start)
    after=raw[o:min(sec_end,o+SEARCH)]
    q=after.find(b"\xcc"*8)
    req(q>0,"following INT3 pad absent")
    end_off=o+q;end_va=s["va"]+(end_off-sec_start)
    req(start_va==TARGET,f"target is not function entry: start 0x{start_va:x}")
    blob=raw[start_off:end_off];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,start_va));req(ins and ins[0].address==TARGET,"decode start drift")
    calls=[];lits={}
    for i in ins:
      if i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
        calls.append({"callVa":f"0x{i.address:08x}","targetVa":f"0x{int(i.operands[0].imm)&0xffffffff:08x}","bytes":i.bytes.hex()})
      for op in i.operands:
        if op.type==X86_OP_IMM:
          v=int(op.imm)&0xffffffff;cs=cstr(raw,secs,v)
          if cs:lits[v]=cs
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact INT3-bounded function bytes reached by the proven baseIndex-16 matrix dispatcher",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "dispatch":{"baseIndex":16,"dispatcherThunkVa":"0x00772fc1","helperEntryVa":f"0x{TARGET:08x}"},
      "function":{"startVa":f"0x{start_va:08x}","endVaExclusive":f"0x{end_va:08x}","bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),
                  "instructions":[row(i) for i in ins],"directCalls":calls,"referencedPrintableStrings":[lits[k] for k in sorted(lits)]},
      "summary":{"functionBytes":len(blob),"instructionCount":len(ins),"directCallCount":len(calls),"printableLiteralCount":len(lits)},
      "proofBoundary":"Exact current-client helper bytes only. The baseIndex-16 dispatch relation is inherited from independent current-client proof. No helper semantic name, source-state field meaning, matrix formula, depth-hack behavior, draw-time value, or historical-retail equivalence is promoted by this probe alone."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    print(json.dumps(calls,indent=2))
    print(json.dumps(doc["function"]["referencedPrintableStrings"],indent=2))
if __name__=="__main__":main()
