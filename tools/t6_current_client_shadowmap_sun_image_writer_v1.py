#!/usr/bin/env python3
"""Exact current-client shadowmapSamplerSun slot-6 image writer/caller proof.

Freezes function 0x009A7A30, its three pointer arguments and all direct rel32
callers. This is intentionally image-side provenance only; sampler-state byte
closure is joined separately.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadowmap-sun-image-writer-v1"
START=0x009A7A30
END=0x009A7A83
CTX=48
GATES={
 0x009A7A30:("8b44240c","mov","eax, dword ptr [esp + 0xc]"),
 0x009A7A35:("8bf1","mov","esi, ecx"),
 0x009A7A37:("8b4c2408","mov","ecx, dword ptr [esp + 8]"),
 0x009A7A3B:("898640150000","mov","dword ptr [esi + 0x1540], eax"),
 0x009A7A41:("8b44240c","mov","eax, dword ptr [esp + 0xc]"),
 0x009A7A48:("898648150000","mov","dword ptr [esi + 0x1548], eax"),
 0x009A7A55:("898e44150000","mov","dword ptr [esi + 0x1544], ecx"),
 0x009A7A5B:("c7864c15000004000000","mov","dword ptr [esi + 0x154c], 4"),
 0x009A7A6F:("898650150000","mov","dword ptr [esi + 0x1550], eax"),
}
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
def locate(secs,va,n=1):
    for s in secs:
        if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:return s,s["rawOffset"]+va-s["va"]
    raise E(f"VA 0x{va:x}+{n} not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def callers(raw,secs):
    out=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
        if not s["exec"]:continue
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            if (int(i.operands[0].imm)&0xffffffff)!=START:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            out.append({"call":rr(i),"section":s["name"],"contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s,o=locate(secs,START,END-START);blob=raw[o:o+END-START]
    md=Cs(CS_ARCH_X86,CS_MODE_32);ins=list(md.disasm(blob,START));by={i.address:i for i in ins}
    for va,(bb,mn,op) in GATES.items():
        i=by.get(va);req(i is not None,f"missing gate 0x{va:x}")
        got=(i.bytes.hex(),i.mnemonic,i.op_str);req(got==(bb,mn,op),f"gate drift 0x{va:x}: {got}")
    cc=callers(raw,secs)
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact slot-6 image-writer bytes + every direct rel32 caller",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "writer":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":s["name"],
        "sha256":hashlib.sha256(blob).hexdigest(),"instructions":[rr(i) for i in ins],
        "dataflow":{
          "sourceStateBase":"incoming ECX -> ESI at 0x009A7A35",
          "slot4Image":"original third stack argument -> source+0x1540",
          "slot6Image":"original second stack argument -> source+0x1548",
          "slot5Image":"original first stack argument minus 4 -> source+0x1544",
          "slot7Image":"constant pointer/integer value 4 -> source+0x154C",
          "slot8Value":"clamped difference between slot6 pointer/value and slot5 pointer/value -> source+0x1550"
        }},
      "directCallers":cc,
      "summary":{"directCallerCount":len(cc),"sourceStateBaseClosed":True,"slot6ImageArgumentClosed":True},
      "proofBoundary":"Closes current-client slot-6 image-writer mechanics exactly: generic source-state base and the writer's second pointer argument feed source+0x1548. It does not by itself name the pointed resource, prove caller argument provenance, sampler-state byte semantics, historical-retail equivalence or framebuffer behavior."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
