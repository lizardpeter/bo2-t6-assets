#!/usr/bin/env python3
"""Locate current-client RC_SET_CUSTOM_CONSTANT front-end constructor by exact call shape.

Pinned T6 lineage says R_AddCmdSetCustomConstantInternal obtains a
GfxCmdSetCustomConstant through R_GetCommandBuffer(RC_SET_CUSTOM_CONSTANT, 24).
The current-client backend independently proves command id 1 and a 24-byte record.

This probe searches only for the exact cdecl allocation call shape:
  push 0x18
  push 1
  call rel32
and retains full INT3-bounded caller functions plus the call target. It then
diagnoses writes through the returned EAX to record offsets 0,2,4,8,12,16,20.

Locator only: no source symbol is assigned until a semantic projector validates
the returned-record writes and caller relationship.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM,X86_REG_EAX

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-custom-constant-frontend-signature-v1"

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
def function_bounds(raw,s,va):
    o=s["rawOffset"]+va-s["va"];base=s["rawOffset"];end=s["rawOffset"]+s["rawSize"]
    lo=o
    while lo>base+4 and raw[lo-4:lo]!=b"\xcc"*4:lo-=1
    if raw[lo-4:lo]==b"\xcc"*4:start=lo
    else:start=max(base,o-1024)
    hi=o
    while hi<end-4 and raw[hi:hi+4]!=b"\xcc"*4:hi+=1
    stop=hi if hi<end-4 and raw[hi:hi+4]==b"\xcc"*4 else min(end,o+2048)
    return s["va"]+start-base,s["va"]+stop-base,start,stop
def decode_func(raw,s,fs,fe,rs,re):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    off=rs
    return [i for i in md.disasm(raw[off:re],fs) if i.id]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n in range(len(ins)-2):
            a0,a1,a2=ins[n:n+3]
            if a0.mnemonic!="push" or len(a0.operands)!=1 or a0.operands[0].type!=X86_OP_IMM or (int(a0.operands[0].imm)&0xffffffff)!=0x18:continue
            if a1.mnemonic!="push" or len(a1.operands)!=1 or a1.operands[0].type!=X86_OP_IMM or (int(a1.operands[0].imm)&0xffffffff)!=1:continue
            if a2.mnemonic!="call" or len(a2.operands)!=1 or a2.operands[0].type!=X86_OP_IMM:continue
            target=int(a2.operands[0].imm)&0xffffffff
            fs,fe,rs,re=function_bounds(raw,s,a0.address)
            body=decode_func(raw,s,fs,fe,rs,re)
            call_index=next((i for i,x in enumerate(body) if x.address==a2.address),None)
            after=body[call_index+1:call_index+50] if call_index is not None else []
            eax_writes=[]
            for x in after:
                for oi,op in enumerate(x.operands):
                    if op.type==X86_OP_MEM and op.mem.base==X86_REG_EAX and op.mem.index==0 and int(op.mem.disp) in (0,2,4,8,12,16,20):
                        eax_writes.append({"offset":int(op.mem.disp),"operandIndex":oi,"instruction":row(x),
                            "positionClass":"destination-or-rmw" if oi==0 and x.mnemonic not in ("cmp","test") else "source-or-other"})
            hits.append({
              "section":s["name"],"allocationSequence":[row(a0),row(a1),row(a2)],
              "allocatorTargetVa":f"0x{target:08x}",
              "functionStartVa":f"0x{fs:08x}","functionEndVaExclusive":f"0x{fe:08x}",
              "functionSha256":hashlib.sha256(raw[rs:re]).hexdigest(),
              "eaxRecordFieldReferencesAfterCall":eax_writes,
              "functionInstructions":[row(x) for x in body],
            })
    bytarget={}
    for h in hits:bytarget[h["allocatorTargetVa"]]=bytarget.get(h["allocatorTargetVa"],0)+1
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact cdecl push/call signature and bounded disassembly",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "signature":{"recordBytes":24,"commandId":1,"cdeclSequence":"push 0x18; push 1; call rel32"},
      "summary":{"signatureHitCount":len(hits),"uniqueAllocatorTargetCount":len(bytarget),"allocatorTargetHitCounts":dict(sorted(bytarget.items()))},
      "hits":hits,
      "proofBoundary":"Locator only. Exact current-client call sites matching the 24-byte/id-1 allocation shape are retained with full local function bytes and EAX-relative post-call record accesses. Pinned lineage motivates the signature but does not name any current-client function. A later projector must prove allocator header semantics and returned-record enum/vec4 writes before promoting the front-end custom-constant provider."
    }
    if not hits:raise SystemExit("no exact 24-byte/id-1 allocator call shape found")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for h in hits:
        print(h["functionStartVa"],h["allocatorTargetVa"],[(x["offset"],x["instruction"]["address"],x["instruction"]["opStr"]) for x in h["eaxRecordFieldReferencesAfterCall"]])
if __name__=="__main__":main()
