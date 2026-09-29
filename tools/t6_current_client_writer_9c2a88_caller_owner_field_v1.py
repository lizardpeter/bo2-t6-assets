#!/usr/bin/env python3
"""Close the enclosing caller argument feeding current-client writer 0x009C2A88.

Upstream path-sensitive proof established:
  0x009B5C0A -> 0x009B7E80
  enclosing-function arg1 -> 0x009C1EF0 arg1
  0x009C2A88 destination base = enclosing-function arg1 + 0xF00

This proof resolves the exact value pushed as arg1 at 0x009B5C09 and traces
the owner register EDI within the bounded caller region.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
CALL=0x009B5C0A
LOAD=0x009B5B8C
PUSH=0x009B5C09
TARGET=0x009B7E80

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def parse_pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,secs
def sec_for(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked {va:x}")
def raw_region(raw,s,va):
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];rel=va-s["va"]
    pre=list(re.finditer(b"\xCC{8,}",data[:rel]));req(pre,"no prior int3")
    a=pre[-1].end()
    while a<len(data) and data[a]==0xcc:a+=1
    post=re.search(b"\xCC{8,}",data[rel+1:]);req(post,"no next int3")
    b=rel+1+post.start()
    return s["va"]+a,s["va"]+b,data[a:b]
def rec(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=parse_pe(raw);s=sec_for(secs,CALL);start,end,blob=raw_region(raw,s,CALL)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,start));by={x.address:x for x in ins}
    gates={LOAD:("mov","ecx, dword ptr [edi + 0x110]"),PUSH:("push","ecx"),CALL:("call","0x9b7e80")}
    for va,(mn,op) in gates.items():
        x=by.get(va);req(x is not None,f"missing {va:x}");req(x.mnemonic==mn and x.op_str.lower()==op.lower(),f"drift {va:x}: {x.mnemonic} {x.op_str}")
    li=next(i for i,x in enumerate(ins) if x.address==LOAD);pi=next(i for i,x in enumerate(ins) if x.address==PUSH)
    req(li<pi,"bad order")
    ecx_defs=[]
    edi_defs=[]
    for x in ins[:pi]:
        _r,w=x.regs_access()
        names={md.reg_name(z) for z in w}
        if "ecx" in names:ecx_defs.append(rec(x))
        if "edi" in names:edi_defs.append(rec(x))
    between=[]
    for x in ins[li+1:pi]:
        _r,w=x.regs_access()
        if any(md.reg_name(z)=="ecx" for z in w):between.append(rec(x))
    req(not between,f"ECX redefined after owner field load: {between}")
    # EDI reaching definition at LOAD.
    edi_before=[]
    for x in ins[:li]:
        _r,w=x.regs_access()
        if any(md.reg_name(z)=="edi" for z in w):edi_before.append(rec(x))
    last_edi=edi_before[-1] if edi_before else None

    # Detect conventional frame setup and caller arguments if EDI was loaded from one.
    frame_pairs=[]
    for j,x in enumerate(ins[:-1]):
        y=ins[j+1]
        if x.mnemonic=="push" and x.op_str=="ebp" and y.mnemonic=="mov" and y.op_str=="ebp, esp":
            frame_pairs.append({"push":rec(x),"mov":rec(y)})

    doc={
      "format":"t6-current-client-writer-9c2a88-caller-owner-field-v1",
      "authority":"SHA-pinned current-client bounded caller dataflow",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "region":{"diagnosticStartVa":f"0x{start:08X}","diagnosticEndVaExclusive":f"0x{end:08X}","sha256":hashlib.sha256(blob).hexdigest(),"instructionCount":len(ins)},
      "argFlow":{"ownerFieldLoad":rec(by[LOAD]),"push":rec(by[PUSH]),"call":rec(by[CALL]),
                 "ecxWritesBetweenLoadAndPush":between,
                 "conclusion":"0x009B7E80 arg1 = *(EDI+0x110) on this decoded call occurrence"},
      "edi":{"definitionsBeforeOwnerFieldLoad":edi_before,"lastDefinitionBeforeOwnerFieldLoad":last_edi},
      "frameSetupPairs":frame_pairs,
      "summary":{"callerRegionStart":f"0x{start:08X}","arg1Expression":"*(EDI+0x110)",
                 "writerDestinationBaseExpression":"*(EDI+0x110)+0xF00",
                 "ecxRedefinitionCountAfterFieldLoad":len(between),
                 "lastEdiDefinitionBeforeFieldLoad":last_edi},
      "proofBoundary":"Closes the exact caller argument expression for the decoded 0x009B5C0A -> 0x009B7E80 occurrence. EDI semantic owner identity is only promoted if its reaching definition proves it; indirect callers remain outside this proof."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
