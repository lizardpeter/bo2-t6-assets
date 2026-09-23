#!/usr/bin/env python3
"""Retain exact current-client bodies for all seven canonical code-matrix derive helpers."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-matrix-base-helper-corpus-v1"
TARGETS={4:0x007729e0,8:0x00772ac0,12:0x00772a30,16:0x00772ca0,20:0x00772d20,24:0x00772de0,28:0x00772e30}
MAX=0x1000
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
    raise E(f"unbacked 0x{va:x}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def body(raw,secs,target):
    s,o=vaoff(secs,target);end=min(o+MAX,s["rawOffset"]+s["rawSize"]);blob=raw[o:end]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=list(md.disasm(blob,target));req(ins and ins[0].address==target,"entry decode drift")
    stop=None
    for i in ins:
        if i.mnemonic not in ("ret","retf"):continue
        nxt=o+(i.address-target)+len(i.bytes)
        if nxt<end and raw[nxt]==0xcc:
            stop=i.address+len(i.bytes);break
    req(stop is not None,f"no ret+INT3 end for 0x{target:x}")
    kept=[i for i in ins if i.address<stop]
    b=raw[o:o+(stop-target)]
    calls=[]
    for i in kept:
        if i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
            calls.append({"callVa":f"0x{i.address:08x}","targetVa":f"0x{int(i.operands[0].imm)&0xffffffff:08x}","bytes":i.bytes.hex()})
    return {"entryVa":f"0x{target:08x}","endVaExclusive":f"0x{stop:08x}","bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),
            "instructionCount":len(kept),"directCalls":calls,"instructions":[row(i) for i in kept]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}");ib,secs=pe(raw)
    helpers={str(k):body(raw,secs,v) for k,v in TARGETS.items()}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact canonical helper entries inherited from exact derive-dispatch proof",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "helpers":helpers,
      "summary":{"helperCount":len(helpers),"baseIndices":sorted(TARGETS),"totalBytes":sum(x["bytes"] for x in helpers.values()),
                 "totalDirectCalls":sum(len(x["directCalls"]) for x in helpers.values())},
      "proofBoundary":"Exact helper bodies only, bounded by decoded ret followed immediately by INT3. BaseIndex-to-entry mapping is inherited from exact current-client dispatcher evidence. No physical semantic names or formulas are promoted here; each helper requires dataflow proof."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for k,v in helpers.items():print(k,v["entryVa"],v["endVaExclusive"],v["bytes"],v["directCalls"])
if __name__=="__main__":main()
