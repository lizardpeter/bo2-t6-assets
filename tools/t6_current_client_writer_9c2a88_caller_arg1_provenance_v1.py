#!/usr/bin/env python3
"""Fast exact caller-arg provenance for the path feeding writer 0x009C2A88.

Prior proof:
  0x009B80E9 -> 0x009C1EF0
  0x009B80DA ESI=[EBP+8]
  downstream destination base = that value + 0xF00.

This version avoids full-image Capstone detail. It decodes executable sections
without detail for direct incoming-edge census and decodes only the local
anchor region for frame/argument proof.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ANCHOR=0x009B80E9
DOWNSTREAM=0x009C1EF0
CTX=96

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
def sec_for(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise E(f"unbacked VA {va:x}")
def rec(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def quick_dis(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=False;md.skipdata=True
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    return [i for i in md.disasm(data,s["va"]) if i.id]
def local_region(raw,s,anchor):
    off=s["rawOffset"]+(anchor-s["va"])
    lo=max(s["rawOffset"],off-0x10000);hi=min(s["rawOffset"]+s["rawSize"],off+0x10000)
    data=raw[lo:hi];base=s["va"]+(lo-s["rawOffset"]);rel=off-lo
    before=data.rfind(b"\xcc"*8,0,rel)
    req(before>=0,"no preceding int3 run")
    start=before+8
    while start<len(data) and data[start]==0xcc:start+=1
    after=data.find(b"\xcc"*8,rel)
    req(after>=0,"no following int3 run")
    va0=base+start;va1=base+after
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=False
    ins=list(md.disasm(raw[s["rawOffset"]+(va0-s["va"]):s["rawOffset"]+(va1-s["va"])],va0))
    return va0,va1,ins
def parse_target(op):
    op=op.strip().lower()
    try:
        return int(op,16) if op.startswith("0x") else None
    except: return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=pe(raw);s=sec_for(secs,ANCHOR)
    start,end,region=local_region(raw,s,ANCHOR)
    by={i.address:i for i in region}
    req(ANCHOR in by,"anchor absent local")
    req(by[ANCHOR].mnemonic=="call" and parse_target(by[ANCHOR].op_str)==DOWNSTREAM,"anchor drift")
    req(0x009B80DA in by and by[0x009B80DA].mnemonic=="mov" and by[0x009B80DA].op_str=="esi, dword ptr [ebp + 8]","arg load drift")

    # Determine whether the region establishes EBP as its own frame pointer before anchor.
    anchor_i=next(i for i,x in enumerate(region) if x.address==ANCHOR)
    pre=region[:anchor_i]
    frame=[rec(x) for x in pre if (x.mnemonic=="push" and x.op_str=="ebp") or (x.mnemonic=="mov" and x.op_str=="ebp, esp")]
    # Keep all textual EBP destination candidates; no regs_access required.
    ebp_defs=[rec(x) for x in pre if x.op_str.startswith("ebp,") or (x.mnemonic=="pop" and x.op_str=="ebp")]

    incoming=[]
    for es in secs:
        if not es["executable"]:continue
        ins=quick_dis(raw,es)
        for j,x in enumerate(ins):
            if x.mnemonic not in ("call","jmp"):continue
            if parse_target(x.op_str)!=start:continue
            incoming.append({"section":es["name"],"edge":rec(x),
                             "contextBefore":[rec(z) for z in ins[max(0,j-CTX):j]],
                             "contextAfter":[rec(z) for z in ins[j+1:min(len(ins),j+24)]]})
    frame_is_standard=any(x["mnemonic"]=="push" and x["opStr"]=="ebp" for x in frame) and any(x["mnemonic"]=="mov" and x["opStr"]=="ebp, esp" for x in frame)
    doc={
      "format":"t6-current-client-writer-9c2a88-caller-arg1-provenance-v2",
      "authority":"SHA-pinned local function region plus instruction-aligned direct incoming-edge census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "region":{"startVa":f"0x{start:08X}","endVaExclusive":f"0x{end:08X}","instructionCount":len(region),
                "frameSetupCandidates":frame,"ebpDefinitionsBeforeAnchor":ebp_defs,"instructions":[rec(x) for x in region]},
      "anchor":{"call":rec(by[ANCHOR]),"arg1Load":rec(by[0x009B80DA]),"downstreamDestinationBase":"[EBP+8] + 0xF00"},
      "directIncomingEdges":incoming,
      "summary":{"regionStartVa":f"0x{start:08X}","regionEndVaExclusive":f"0x{end:08X}",
                 "standardEbpFrameBeforeAnchor":frame_is_standard,
                 "directIncomingEdgeCount":len(incoming),
                 "downstreamBaseExpression":"this_function_arg1 + 0xF00" if frame_is_standard else "[EBP+8] + 0xF00"},
      "proofBoundary":"Exact current-client instruction-aligned census. INT3 region is diagnostic unless prologue/incoming-edge evidence confirms entry. No caller source-level identity is assigned from address or layout alone."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
