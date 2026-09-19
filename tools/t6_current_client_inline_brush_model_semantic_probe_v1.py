#!/usr/bin/env python3
"""Deep exact-byte/current-client probe for the candidate inline brush-model parser.

Adds three forms of evidence absent from the first focused probe:
- literal C strings referenced by the candidate path;
- direct call xrefs into the candidate function neighborhood;
- the body of the base-10 conversion callee used by the '*' suffix wrapper.

No source symbol name is assumed.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-inline-brush-model-semantic-probe-v1"
CANDIDATE=(0x007c33c0,0x007c3580)
BASE10=(0x00a73004,0x00a7303b)
LITERAL_VAS=[0x00c2d058,0x00c61bb8,0x00c096c0]

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);chars=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"characteristics":chars})
    return ib,secs
def vaoff(secs,va,n=1):
    for s in secs:
        if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:
            return s,s["rawOffset"]+(va-s["va"])
    raise E(f"VA 0x{va:x}+{n} not raw-backed")
def blob(raw,secs,a,b):
    s,o=vaoff(secs,a,b-a);return s,raw[o:o+b-a]
def cstr(raw,secs,va,limit=512):
    s,o=vaoff(secs,va,1);end=min(len(raw),s["rawOffset"]+s["rawSize"],o+limit)
    z=raw.find(b"\0",o,end);req(z>=0,f"unterminated string 0x{va:x}")
    b=raw[o:z]
    return {"va":f"0x{va:08x}","section":s["name"],"bytes":b.hex(),"text":b.decode("ascii","replace")}
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def dis(raw,secs,a,b):
    s,bb=blob(raw,secs,a,b);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    return {"startVa":f"0x{a:08x}","endVaExclusive":f"0x{b:08x}","section":s["name"],
      "bytes":len(bb),"sha256":hashlib.sha256(bb).hexdigest(),"instructions":[row(i) for i in md.disasm(bb,a)]}
def direct_calls(raw,secs,lo,hi):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;out=[]
    for s in secs:
        if not (s["characteristics"]&0x20000000):continue
        bb=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        for i in md.disasm(bb,s["va"]):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            t=int(i.operands[0].imm)&0xffffffff
            if lo<=t<hi:out.append({"call":row(i),"targetVa":f"0x{t:08x}"})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw)
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "candidateRange":dis(raw,secs,*CANDIDATE),"base10CalleeRange":dis(raw,secs,*BASE10),
      "literalStrings":[cstr(raw,secs,v) for v in LITERAL_VAS],
      "directCallsIntoCandidateRange":direct_calls(raw,secs,*CANDIDATE),
      "proofBoundary":"Exact current-client bytes, direct-call operands, and raw-backed C strings only. Candidate function/source identity, numeric-parser library symbol, brushmodel semantics, MapEnt model-field semantics, and historical-retail equivalence remain unpromoted until a fail-closed semantic projector joins the control/data flow."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"literals":doc["literalStrings"],"callerCount":len(doc["directCallsIntoCandidateRange"]),"candidateInstructions":len(doc["candidateRange"]["instructions"]),"base10Instructions":len(doc["base10CalleeRange"]["instructions"])},indent=2))
if __name__=="__main__":main()
