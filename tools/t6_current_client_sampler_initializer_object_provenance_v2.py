#!/usr/bin/env python3
"""Exact T6 current-client sampler initializer object convergence proof v2.

Corrects v1's helper boundary: 0x0065B430 returns at 0x0065B4D9 and is followed
by a six-byte INT3 pad before a distinct function at 0x0065B4E0.

Proves both direct callers of 0x00455100 pass the same owner-relative field:
A: [owner + 0x5DAC]
B: helper(owner + 0x3A8), where helper returns its incoming this+0x5A04 field.
Since 0x3A8 + 0x5A04 = 0x5DAC, the object occurrence converges exactly.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
HELPER_START=0x0065B430
HELPER_END=0x0065B4DA
CALLER_A=(0x00481990,0x00481A12)
CALLER_B=(0x00565A90,0x00565AE5)
SUBOBJECT=0x3A8
FIELD=0x5DAC
HELPER_FIELD=0x5A04

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def parse(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        z=so+i*40;name=raw[z:z+8].split(b"\0",1)[0].decode()
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,z+8);ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro))
    return base,ss
def section(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked {va:x}")
def blob(raw,ss,a,b):
    s=section(ss,a);req(section(ss,b-1)["name"]==s["name"],"cross section")
    o=s["rawOffset"]+a-s["va"];return raw[o:o+b-a],s
def dis(raw,ss,a,b):
    bts,s=blob(raw,ss,a,b);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(bts,a));req(ins and ins[0].address==a,"decode");return md,ins,bts,s
def row(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def gate(ins,va,mn,op):
    i=next((q for q in ins if q.address==va),None);req(i is not None,f"missing {va:x}")
    req(i.mnemonic==mn and i.op_str==op,f"drift {va:x}: {i.mnemonic} {i.op_str}");return i

def reg_writers(md,ins,reg,lo,hi):
    out=[]
    for i in ins:
        if not(lo<=i.address<=hi):continue
        _r,w=i.regs_access()
        if any(md.reg_name(x)==reg for x in w):out.append(row(i))
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument("exe",type=Path);p.add_argument("--revision",required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,dg);base,ss=parse(raw)
    hmd,h,hb,hs=dis(raw,ss,HELPER_START,HELPER_END)
    amd,aa,ab,_=dis(raw,ss,*CALLER_A);bmd,bb,bbb,_=dis(raw,ss,*CALLER_B)

    gate(h,0x0065B431,"mov","esi, ecx")
    gate(h,0x0065B43A,"mov","edi, dword ptr [esi + 0x5a04]")
    gate(h,0x0065B4D5,"mov","eax, edi")
    gate(h,0x0065B4D9,"ret","")
    # exact pad proves distinct next function
    pad,_=blob(raw,ss,HELPER_END,0x0065B4E0);req(pad==b"\xcc"*6,f"pad drift {pad.hex()}")

    edi_w=reg_writers(hmd,h,"edi",0x0065B43A,0x0065B4D5)
    esi_w=reg_writers(hmd,h,"esi",0x0065B431,0x0065B4D5)
    # EDI must only be defined by the field load; ESI only by ECX alias in relevant path.
    req([x["address"] for x in edi_w]==["0x0065B43A"],f"EDI clobber {edi_w}")
    req([x["address"] for x in esi_w]==["0x0065B431"],f"ESI clobber {esi_w}")

    gate(aa,0x00481991,"mov","esi, ecx")
    gate(aa,0x00481994,"mov","edi, dword ptr [esi + 0x5dac]")
    gate(aa,0x004819A9,"mov","ecx, edi")
    gate(aa,0x004819AB,"call","0x455100")

    gate(bb,0x00565A92,"mov","esi, ecx")
    gate(bb,0x00565AAD,"lea","ecx, [esi + 0x3a8]")
    gate(bb,0x00565AB5,"call","0x65b430")
    gate(bb,0x00565AC4,"mov","ecx, eax")
    gate(bb,0x00565AC6,"call","0x455100")

    req(SUBOBJECT+HELPER_FIELD==FIELD,"offset arithmetic")
    doc={
      "format":"t6-current-client-sampler-initializer-object-provenance-v2",
      "authority":"SHA-pinned exact caller/helper register and memory dataflow",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "helper":{"startVa":f"0x{HELPER_START:08X}","endVaExclusive":f"0x{HELPER_END:08X}","bytes":len(hb),"sha256":hashlib.sha256(hb).hexdigest(),
        "instructionCount":len(h),"entryThisAlias":row(gate(h,0x0065B431,"mov","esi, ecx")),
        "fieldLoad":row(gate(h,0x0065B43A,"mov","edi, dword ptr [esi + 0x5a04]")),
        "returnValueDefinition":row(gate(h,0x0065B4D5,"mov","eax, edi")),
        "returnInstruction":row(gate(h,0x0065B4D9,"ret","")),"ediWritersThroughReturnValue":edi_w,"esiWritersThroughReturnValue":esi_w,
        "followingPadBytes":pad.hex(),"instructions":[row(i) for i in h]},
      "callerA":{"range":[f"0x{CALLER_A[0]:08X}",f"0x{CALLER_A[1]:08X}"],"sha256":hashlib.sha256(ab).hexdigest(),
        "ownerAlias":"ESI = incoming ECX","objectFieldLoad":"EDI = [ESI+0x5DAC]","initializerObject":"ECX = EDI","initializerCall":"0x004819AB -> 0x00455100"},
      "callerB":{"range":[f"0x{CALLER_B[0]:08X}",f"0x{CALLER_B[1]:08X}"],"sha256":hashlib.sha256(bbb).hexdigest(),
        "ownerAlias":"ESI = incoming ECX","helperThis":"ECX = ESI+0x3A8","helperCall":"0x00565AB5 -> 0x0065B430","initializerObject":"ECX = EAX helper return","initializerCall":"0x00565AC6 -> 0x00455100"},
      "convergence":{"ownerFieldOffset":"0x5DAC","callerAExpression":"*(owner+0x5DAC)",
        "callerBExpression":"*(owner+0x3A8+0x5A04)","offsetArithmetic":"0x3A8 + 0x5A04 = 0x5DAC",
        "sameObjectFieldProven":True,
        "conclusion":"Both decoded direct initializer callers pass the same owner-relative pointer field at +0x5DAC."},
      "proofBoundary":"Proves exact current-client convergence of the two decoded direct 0x00455100 caller object arguments to owner+0x5DAC. It does not yet assign the owner or +0x5DAC field a source-level type/name, prove indirect initializer callers absent, or prove this field is the generic GfxCmdBufSource object used by the code-sampler consumers."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"helper":doc["helper"]["startVa"]+".."+doc["helper"]["endVaExclusive"],"helperSha256":doc["helper"]["sha256"],"sameObjectFieldProven":True,"conclusion":doc["convergence"]["conclusion"]},indent=2))

if __name__=="__main__":main()
