#!/usr/bin/env python3
"""Locate current-client custom-constant constructors from allocator callers.

Input is the exact current-client allocator-immediate locator. Every candidate
allocator VA is scanned for direct rel32 callers. Each caller is expanded to its
INT3-bounded function, then EAX (allocator return) aliases are tracked forward.

A constructor candidate must have destination writes to the same returned-record
alias at +4,+8,+12,+16,+20. This is still locator evidence: the allocator
candidate and field meanings require a later semantic projector.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM,X86_OP_REG,X86_REG_EAX

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
IN_FMT="t6-current-client-render-command-allocator-immediate-locator-v1"
OUT_FMT="t6-current-client-custom-constant-constructor-locator-v1"
REQUIRED={4,8,12,16,20}

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
def bounds(raw,s,va):
    o=s["rawOffset"]+va-s["va"];base=s["rawOffset"];end=s["rawOffset"]+s["rawSize"]
    lo=o
    while lo>base+4 and raw[lo-4:lo]!=b"\xcc"*4:lo-=1
    start=lo if lo>base and raw[lo-4:lo]==b"\xcc"*4 else max(base,o-2048)
    hi=o
    while hi<end-4 and raw[hi:hi+4]!=b"\xcc"*4:hi+=1
    stop=hi if hi<end-4 and raw[hi:hi+4]==b"\xcc"*4 else min(end,o+4096)
    return s["va"]+start-base,s["va"]+stop-base,start,stop
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--allocator-proof",type=Path,required=True);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    p=json.loads(a.allocator_proof.read_text());req(p.get("format")==IN_FMT,"allocator proof format drift")
    allocs={int(x["functionStartVa"],16) for x in p.get("candidates",[])}
    req(allocs,"allocator candidate set empty")
    ib,secs=pe(raw);callers=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            target=int(i.operands[0].imm)&0xffffffff
            if target not in allocs:continue
            fs,fe,rs,re=bounds(raw,s,i.address)
            body=[z for z in md.disasm(raw[rs:re],fs) if z.id]
            ci=next((k for k,z in enumerate(body) if z.address==i.address),None)
            if ci is None:continue
            aliases={X86_REG_EAX};writes=[]
            # Track return aliases until a call clobbers EAX; aliases copied out survive.
            for z in body[ci+1:min(len(body),ci+80)]:
                if z.mnemonic=="mov" and len(z.operands)==2:
                    d,src=z.operands
                    if d.type==X86_OP_REG and src.type==X86_OP_REG and src.reg in aliases:
                        aliases.add(d.reg)
                for oi,op in enumerate(z.operands):
                    if op.type!=X86_OP_MEM or op.mem.index!=0 or op.mem.base not in aliases:continue
                    disp=int(op.mem.disp)
                    if disp not in (0,2,4,8,12,16,20):continue
                    if oi==0 and z.mnemonic not in ("cmp","test"):
                        writes.append({"offset":disp,"baseReg":md.reg_name(op.mem.base),"instruction":row(z)})
            offs={x["offset"] for x in writes}
            callers.append({
              "allocatorTargetVa":f"0x{target:08x}","call":row(i),
              "functionStartVa":f"0x{fs:08x}","functionEndVaExclusive":f"0x{fe:08x}",
              "functionSha256":hashlib.sha256(raw[rs:re]).hexdigest(),
              "destinationWritesThroughAllocatorReturn":writes,
              "requiredCustomConstantFieldsCovered":REQUIRED.issubset(offs),
              "functionInstructions":[row(z) for z in body],
            })
    candidates=[x for x in callers if x["requiredCustomConstantFieldsCovered"]]
    doc={"format":OUT_FMT,"authority":"SHA-classified current-client direct callers of exact allocator-locator candidates",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "allocatorProof":{"path":str(a.allocator_proof),"sha256":hashlib.sha256(a.allocator_proof.read_bytes()).hexdigest(),"candidateVas":[f"0x{x:08x}" for x in sorted(allocs)]},
      "summary":{"allocatorCandidateCount":len(allocs),"directAllocatorCallCount":len(callers),"customConstantShapeCandidateCount":len(candidates)},
      "customConstantShapeCandidates":candidates,
      "allAllocatorCallers":callers,
      "proofBoundary":"Locator only. Candidates are exact current-client allocator callers whose returned-pointer aliases receive destination writes at +4,+8,+12,+16,+20. Field offsets match the independently proven backend custom-constant record, but no caller is promoted as the frontend producer until the allocator candidate is structurally closed and the caller dataflow is projected from function arguments into enum/vec4 fields."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in candidates:print(x["functionStartVa"],x["call"]["address"],[(w["offset"],w["instruction"]["address"],w["instruction"]["opStr"]) for w in x["destinationWritesThroughAllocatorReturn"]])
if __name__=="__main__":main()
