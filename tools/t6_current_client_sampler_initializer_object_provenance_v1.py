#!/usr/bin/env python3
"""Prove object convergence for the corrected current-client sampler initializer.

Focus:
- caller A at 0x00481990 passes [owner+0x5DAC] as ECX to 0x00455100.
- caller B at 0x00565A90 calls 0x0065B430 with ECX=owner+0x3A8 and passes
  returned EAX to 0x00455100.
- 0x5DAC - 0x3A8 == 0x5A04.

This probe recovers the exact 0x0065B430 body and establishes whether its
returned value is the owner-relative field corresponding to +0x5DAC.
No source-level symbol is assigned from address similarity.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
HELPER=0x0065B430
CALLER_A=(0x00481990,0x00481A12)
CALLER_B=(0x00565A90,0x00565AE5)
INIT=0x00455100
OWNER_SUBOBJECT=0x3A8
OWNER_FIELD=0x5DAC
DELTA=OWNER_FIELD-OWNER_SUBOBJECT

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        x=so+i*40;name=raw[x:x+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,x+8);ch=struct.unpack_from("<I",raw,x+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def sec(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise E(f"unbacked {va:x}")
def vaoff(s,va): return s["rawOffset"]+va-s["va"]
def row(i): return dict(address=f"0x{i.address:08X}",bytes=i.bytes.hex(),mnemonic=i.mnemonic,opStr=i.op_str)
def bounded(raw,ss,start):
    s=sec(ss,start);o=vaoff(s,start);end=s["rawOffset"]+s["rawSize"]
    p=raw.find(b"\xcc"*8,o)
    req(p>=0 and p<end,"no following INT3 pad")
    blob=raw[o:p]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,start));req(ins and ins[0].address==start,"bad decode")
    return md,ins,blob,s,p

def fixed(raw,ss,a,b):
    s=sec(ss,a);req(sec(ss,b-1)["name"]==s["name"],"cross section")
    o=vaoff(s,a);blob=raw[o:o+b-a]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,a));req(ins and ins[0].address==a,"bad fixed decode")
    return md,ins,blob

def find_exact(ins,va,mn,op):
    z=next((i for i in ins if i.address==va),None);req(z is not None,f"missing {va:x}")
    req(z.mnemonic==mn and z.op_str==op,f"drift {va:x}: {z.mnemonic} {z.op_str}")
    return z

def main():
    a=argparse.ArgumentParser();a.add_argument("exe",type=Path);a.add_argument("--revision",required=True);a.add_argument("--out",type=Path,required=True);x=a.parse_args()
    raw=x.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha {dg}");base,ss=pe(raw)

    hmd,hins,hblob,hs,hpad=bounded(raw,ss,HELPER)
    amd,ains,ablob=fixed(raw,ss,*CALLER_A)
    bmd,bins,bblob=fixed(raw,ss,*CALLER_B)

    # Caller gates.
    find_exact(ains,0x00481994,"mov","edi, dword ptr [esi + 0x5dac]")
    find_exact(ains,0x004819A9,"mov","ecx, edi")
    find_exact(ains,0x004819AB,"call","0x455100")
    find_exact(ains,0x004819B0,"lea","ecx, [esi + 0x3a8]")
    find_exact(ains,0x004819B6,"call","0x65b430")

    find_exact(bins,0x00565AAD,"lea","ecx, [esi + 0x3a8]")
    find_exact(bins,0x00565AB5,"call","0x65b430")
    find_exact(bins,0x00565AC4,"mov","ecx, eax")
    find_exact(bins,0x00565AC6,"call","0x455100")

    # Collect helper memory reads/writes and EAX definitions.
    mem=[];eax_defs=[]
    for i in hins:
        reads,writes=i.regs_access()
        if any(hmd.reg_name(r)=="eax" for r in writes): eax_defs.append(row(i))
        for op in i.operands:
            if op.type==X86_OP_MEM:
                mem.append({
                    **row(i),
                    "base":hmd.reg_name(op.mem.base) if op.mem.base else None,
                    "index":hmd.reg_name(op.mem.index) if op.mem.index else None,
                    "scale":op.mem.scale,
                    "disp":op.mem.disp,
                    "dispHex":f"0x{op.mem.disp & 0xffffffff:X}",
                })
    matching=[m for m in mem if m["base"]=="ecx" and m["index"] in (None,"") and m["disp"]==DELTA]

    # Fail closed: only promote convergence when helper visibly defines EAX from exact field
    # and no later EAX definition before a return on that straight-line return path.
    exact_load=[i for i in hins if i.mnemonic=="mov" and i.op_str=="eax, dword ptr [ecx + 0x5a04]"]
    direct_return_pattern=False
    pattern=None
    for load in exact_load:
        after=[i for i in hins if i.address>load.address]
        for j,i in enumerate(after):
            if i.mnemonic.startswith("ret"):
                intervening=after[:j]
                eax_clobber=[]
                for k in intervening:
                    _r,w=k.regs_access()
                    if any(hmd.reg_name(z)=="eax" for z in w): eax_clobber.append(row(k))
                if not eax_clobber:
                    direct_return_pattern=True
                    pattern={"load":row(load),"return":row(i),"interveningEaxClobbers":[]}
                break
        if direct_return_pattern: break

    doc={
      "format":"t6-current-client-sampler-initializer-object-provenance-v1",
      "authority":"SHA-pinned current-client exact caller/helper machine-code dataflow",
      "client":{"revision":x.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "layoutArithmetic":{"ownerFieldOffset":f"0x{OWNER_FIELD:X}","helperThisSubobjectOffset":f"0x{OWNER_SUBOBJECT:X}","delta":f"0x{DELTA:X}"},
      "callerA":{"range":[f"0x{CALLER_A[0]:08X}",f"0x{CALLER_A[1]:08X}"],"sha256":hashlib.sha256(ablob).hexdigest(),"instructions":[row(i) for i in ains]},
      "callerB":{"range":[f"0x{CALLER_B[0]:08X}",f"0x{CALLER_B[1]:08X}"],"sha256":hashlib.sha256(bblob).hexdigest(),"instructions":[row(i) for i in bins]},
      "helper":{"startVa":f"0x{HELPER:08X}","endVaExclusive":f"0x{hs['va']+(hpad-hs['rawOffset']):08X}","sha256":hashlib.sha256(hblob).hexdigest(),"instructionCount":len(hins),"instructions":[row(i) for i in hins],"memoryOperands":mem,"eaxDefinitions":eax_defs,"exactEcxPlus5A04Operands":matching},
      "convergence":{"exactFieldLoadCount":len(exact_load),"directReturnPattern":direct_return_pattern,"pattern":pattern,
        "conclusion":("caller A [owner+0x5DAC] and caller B helper(owner+0x3A8) converge to the same object field" if direct_return_pattern else "not proven")},
      "proofBoundary":"Exact current-client machine-code object dataflow only. A proven owner-field convergence identifies the same object occurrence supplied to the initializer in both direct callers, but does not by itself assign the owner or field a source-level type/name or prove this object is the generic renderer source object used at every draw."
    }
    x.out.parent.mkdir(parents=True,exist_ok=True);x.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"helperStart":doc["helper"]["startVa"],"helperEnd":doc["helper"]["endVaExclusive"],"helperInstructions":len(hins),"matchingFieldOperands":len(matching),"directReturnPattern":direct_return_pattern,"conclusion":doc["convergence"]["conclusion"]},indent=2))

if __name__=="__main__":main()
