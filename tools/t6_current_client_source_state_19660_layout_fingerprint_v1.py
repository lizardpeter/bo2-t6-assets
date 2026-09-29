#!/usr/bin/env python3
"""Fingerprint the current-client object at base+0x19660.

The target live range begins at 0x009BC5FD:
    lea edi,[esi+0x19660]
and ends before EDI is redefined at 0x009BC77E.

Within that exact range, enumerate every memory operand based on EDI and
classify offsets that coincide with independently proven GfxCmdBufSourceState
layout anchors. This proves layout coincidence only; semantic promotion
requires at least two independent anchor classes and exact base provenance.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x009BC5FD
END=0x009BC77E
KNOWN={
  0x800:"input.consts_base",
  0x1530:"input.codeImages_base",
  0x160C:"codeImageSamplerStates_base",
  0x17E0:"constVersions_base",
}
class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)
def parse_pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        secs.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro))
    return base,secs
def sec_for(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked {va:x}")
def rec(i): return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=parse_pe(raw);s=sec_for(secs,START);req(sec_for(secs,END-1)["name"]==s["name"],"cross-section")
    off=s["rawOffset"]+(START-s["va"]);blob=raw[off:off+(END-START)]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,START));req(ins and ins[0].address==START,"decode drift")
    req(ins[0].mnemonic=="lea" and ins[0].op_str=="edi, [esi + 0x19660]",f"base setup drift {ins[0].mnemonic} {ins[0].op_str}")
    refs=[]
    anchor_hits=[]
    for i in ins:
        for oi,op in enumerate(i.operands):
            if op.type!=X86_OP_MEM: continue
            mem=op.mem
            if md.reg_name(mem.base)!="edi": continue
            disp=int(mem.disp)
            row={"instruction":rec(i),"operandIndex":oi,"disp":disp,"dispHex":f"0x{disp:X}"}
            refs.append(row)
            for k,name in KNOWN.items():
                # Array/member accesses can land inside an anchor region.
                if disp==k or (k==0x160C and 0x160C<=disp<0x16E8):
                    anchor_hits.append({**row,"anchor":name,"anchorBaseHex":f"0x{k:X}"})
    exact_classes=sorted({x["anchor"] for x in anchor_hits})
    doc={
      "format":"t6-current-client-source-state-19660-layout-fingerprint-v1",
      "authority":"SHA-pinned current-client exact live-range memory-reference census joined to independently proven source-state layout offsets",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "liveRange":{"startVa":f"0x{START:08X}","endVaExclusive":f"0x{END:08X}","setup":rec(ins[0]),"sha256":hashlib.sha256(blob).hexdigest()},
      "knownLayoutAnchors":{f"0x{k:X}":v for k,v in KNOWN.items()},
      "ediMemoryReferences":refs,
      "anchorHits":anchor_hits,
      "summary":{"ediMemoryReferenceCount":len(refs),"anchorHitCount":len(anchor_hits),"independentAnchorClasses":exact_classes,
                 "independentAnchorClassCount":len(exact_classes),
                 "baseExpression":"ESI+0x19660"},
      "proofBoundary":"Exact local layout fingerprint only. The +0x19660 object may be promoted to a GfxCmdBufSourceState occurrence only when this fingerprint is joined with independent exact base provenance and the established cross-build source-state layout bridge; no owner/source-level name is inferred from displacement alone."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
