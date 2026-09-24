#!/usr/bin/env python3
"""Promote exact current-client generic code-constant setter semantics and callers.

Exact observed path:
  arg -> wrapper record pointer -> runtime record
  enum = runtimeRecord+4
  values = runtimeRecord+8/+C/+10/+14
  dst = 0x03A37300 + enum*16
  version[enum]++ at 0x03A382E0 + enum*2
The proof also retains every direct rel32 caller so per-enum provider records can
be joined without guessing.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-generic-code-constant-setter-semantics-v1"
START=0x00745B70
END=0x00745BBE
CTX=36
GATES={
 0x00745B79:("8b7c240c","mov","edi, dword ptr [esp + 0xc]"),
 0x00745B7D:("8b37","mov","esi, dword ptr [edi]"),
 0x00745B86:("8b4e04","mov","ecx, dword ptr [esi + 4]"),
 0x00745B89:("d94608","fld","dword ptr [esi + 8]"),
 0x00745B8C:("8bc1","mov","eax, ecx"),
 0x00745B8E:("c1e004","shl","eax, 4"),
 0x00745B91:("050073a303","add","eax, 0x3a37300"),
 0x00745B96:("d918","fstp","dword ptr [eax]"),
 0x00745B98:("d9460c","fld","dword ptr [esi + 0xc]"),
 0x00745B9B:("d95804","fstp","dword ptr [eax + 4]"),
 0x00745B9E:("d94610","fld","dword ptr [esi + 0x10]"),
 0x00745BA1:("d95808","fstp","dword ptr [eax + 8]"),
 0x00745BA4:("d94614","fld","dword ptr [esi + 0x14]"),
 0x00745BA7:("d9580c","fstp","dword ptr [eax + 0xc]"),
 0x00745BAA:("66ff044de082a303","inc","word ptr [ecx*2 + 0x3a382e0]"),
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
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact generic code-constant setter bytes + all direct rel32 callers",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "setter":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":s["name"],
        "sha256":hashlib.sha256(blob).hexdigest(),"instructions":[rr(i) for i in ins]},
      "dataflow":{
        "wrapperArgument":"first stack argument after saved ESI/EDI -> EDI; runtimeRecord = *(void**)EDI",
        "enumValue":"uint32(runtimeRecord+0x04)",
        "lane0":"float32(runtimeRecord+0x08)",
        "lane1":"float32(runtimeRecord+0x0C)",
        "lane2":"float32(runtimeRecord+0x10)",
        "lane3":"float32(runtimeRecord+0x14)",
        "valueDestination":"0x03A37300 + enumValue*16",
        "versionOperation":"uint16[0x03A382E0 + enumValue*2] += 1",
      },
      "directCallers":cc,
      "summary":{"directCallerCount":len(cc),"genericValueCopyClosed":True,"genericVersionUpdateClosed":True,"currentClientGenericSetterClosed":True},
      "proofBoundary":"Closes the SHA-classified current-client generic code-constant setter mechanism exactly. It does not establish which enum records reach this setter, the physical meaning or units of record lanes, indirect/non-rel32 callers, historical-retail executable equivalence or framebuffer behavior. Per-enum provider closure requires an exact caller/record join."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
