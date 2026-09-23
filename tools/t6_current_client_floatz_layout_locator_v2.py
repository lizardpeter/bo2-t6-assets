#!/usr/bin/env python3
"""Locate current-client floatZ code-image/state pair from exact T6 input layout.

Scans for byte-immediate 97 stores and pairs them with a nearby 32-bit store to
same base register exactly 0xA6 bytes earlier. The +0xA6 relation is the exact
T6 GfxCmdBufInput layout delta between codeImages[18] and
codeImageSamplerStates[18] given 55 pointer entries.

This remains locator evidence until the containing function/dataflow is
independently anchored as the floatZ provider.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-floatz-layout-locator-v2"
DELTA=0xA6
CTX=48

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
def state97(i):
    if i.mnemonic!="mov" or len(i.operands)!=2:return None
    d,s=i.operands
    if d.type!=X86_OP_MEM or d.size!=1 or d.mem.base==0 or d.mem.index!=0:return None
    if s.type!=X86_OP_IMM or (int(s.imm)&0xff)!=0x61:return None
    return (d.mem.base,int(d.mem.disp))
def dword_store(i,base,disp):
    if i.mnemonic!="mov" or len(i.operands)!=2:return False
    d=i.operands[0]
    return d.type==X86_OP_MEM and d.size==4 and d.mem.base==base and d.mem.index==0 and int(d.mem.disp)==disp
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);candidates=[]
    for sec in secs:
      if not sec["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
      ins=list(md.disasm(raw[sec["rawOffset"]:sec["rawOffset"]+sec["rawSize"]],sec["va"]))
      for n,i in enumerate(ins):
        st=state97(i)
        if not st:continue
        base,sdisp=st;idisp=sdisp-DELTA
        nearby=[]
        for m in range(max(0,n-CTX),min(len(ins),n+CTX+1)):
          if dword_store(ins[m],base,idisp):
            nearby.append({"imageStore":row(ins[m]),"relativeInstructionDistance":m-n})
        if not nearby:continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        direct_calls=[]
        for z in ins[lo:hi]:
          if z.mnemonic=="call":direct_calls.append(row(z))
        candidates.append({
          "section":sec["name"],"samplerStateStore":row(i),"baseRegisterId":base,
          "samplerStateDisplacement":sdisp,"imageDisplacement":idisp,
          "matchedImageStores":nearby,"nearbyCalls":direct_calls,
          "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]
        })
    doc={"format":FORMAT,"authority":"SHA-classified current client exact decoded instructions; pinned T6 input layout used as locator geometry",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"samplerState97WithMatchingImageStoreCount":len(candidates),"matchedImageStoreCount":sum(len(x["matchedImageStores"]) for x in candidates)},
      "layout":{"codeImageToSamplerStateDelta":DELTA,"samplerStateValue":97},
      "candidates":candidates,
      "proofBoundary":"Exact current-client same-base 32-bit image-store / byte-97 state-store layout matches only. The +0xA6 relation derives from T6 GfxCmdBufInput layout and is locator geometry. No destination is promoted as codeImages[18], no source value is named, and no function is assigned floatZ semantics until independently anchored."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in candidates:print(c["samplerStateStore"]["address"],hex(c["imageDisplacement"]),hex(c["samplerStateDisplacement"]),[x["imageStore"]["address"] for x in c["matchedImageStores"]])
if __name__=="__main__":main()
