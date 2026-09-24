#!/usr/bin/env python3
"""Focused exact probe for candidate light helper 0x00415940.

Retains the complete local callee body and only exact direct callsites where the
local argument sequence is exactly two pushes with exactly one retained light enum.
No helper semantics are assumed.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-light-helper-415940-probe-v1"
TARGET=0x00415940
ENUMS={0:"lightPosition",1:"lightDiffuse",2:"lightSpotDir",3:"lightSpotFactors",5:"lightFallOffA",6:"lightFallOffB",
7:"lightSpotMatrix0",8:"lightSpotMatrix1",9:"lightSpotMatrix2",11:"lightSpotAABB",12:"lightConeControl1",
14:"lightSpotCookieSlideControl",60:"spotShadowmapPixelAdjust"}
MAX_BACK=14
BOUNDARY={"call","ret","retf","jmp"}
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
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def sec_for(secs,va):
    for s in secs:
      if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"VA 0x{va:x} not raw-backed")
def function_body(raw,secs,entry):
    s=sec_for(secs,entry);o=s["rawOffset"]+entry-s["va"];end=s["rawOffset"]+s["rawSize"]
    # entry is exact direct-call target. Stop at first 4-byte INT3 pad after entry,
    # but retain at least through first ret.
    hi=o
    while hi<end-4:
      if hi>o and raw[hi:hi+4]==b"\xcc"*4:break
      hi+=1
    blob=raw[o:hi]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=[i for i in md.disasm(blob,entry)]
    return s,blob,ins
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s,blob,body=function_body(raw,secs,TARGET)
    callsites=[]
    for sec in secs:
      if not sec["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[sec["rawOffset"]:sec["rawOffset"]+sec["rawSize"]],sec["va"]) if i.id]
      for n,i in enumerate(ins):
        if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM or (int(i.operands[0].imm)&0xffffffff)!=TARGET:continue
        lo=max(0,n-MAX_BACK)
        for k in range(n-1,lo-1,-1):
          if ins[k].mnemonic in BOUNDARY:lo=k+1;break
        seq=ins[lo:n];pushes=[z for z in seq if z.mnemonic=="push"]
        enumPush=[]
        for p in pushes:
          if len(p.operands)==1 and p.operands[0].type==X86_OP_IMM:
            v=int(p.operands[0].imm)&0xffffffff
            if v in ENUMS:enumPush.append((v,p))
        if len(pushes)==2 and len(enumPush)==1:
          v,p=enumPush[0]
          callsites.append({"section":sec["name"],"call":rr(i),"enumValue":v,"accessor":ENUMS[v],
            "pushes":[rr(x) for x in pushes],"argInstructions":[rr(x) for x in seq]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact direct-call target/body and two-push callsites",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "target":{"entryVa":f"0x{TARGET:08x}","section":s["name"],"bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),
        "instructions":[rr(i) for i in body]},
      "summary":{"calleeInstructionCount":len(body),"twoPushLightCallsiteCount":len(callsites),
        "distinctLightEnums":sorted({x["enumValue"] for x in callsites}),
        "distinctLightAccessors":sorted({x["accessor"] for x in callsites})},
      "callsites":callsites,
      "proofBoundary":"Focused locator only. Exact callee bytes and exact two-push callsites are retained, but argument semantic roles and helper source identity are not inferred solely from cdecl-like shape."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for i in body:print(i.address, i.mnemonic, i.op_str)
if __name__=="__main__":main()
