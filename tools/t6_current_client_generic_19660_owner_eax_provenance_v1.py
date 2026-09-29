#!/usr/bin/env python3
"""Trace EAX -> ESI at 0x009BB676, which feeds the generic +0x19660 source owner."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x009BB670
ANCHOR=0x009BB676
CTX=64

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def sec(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked {va:x}")
def rec(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def target(i):
    if len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:return int(i.operands[0].imm)&0xffffffff
    return None
def dis(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    return md,[i for i in md.disasm(data,s["va"]) if i.id]
def writes(md,i,name):
    try:
        _r,w=i.regs_access()
        return any(md.reg_name(x)==name for x in w)
    except:return False
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha {dg}")
    base,ss=pe(raw);s=sec(ss,START)
    off=s["rawOffset"]+(START-s["va"]);pad=raw.find(b"\xcc"*8,off);req(pad>=0,"pad")
    blob=raw[off:pad]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,START));by={i.address:i for i in ins}
    req(START in by and ANCHOR in by,"decode")
    req(by[ANCHOR].mnemonic=="mov" and by[ANCHOR].op_str=="esi, eax","anchor drift")
    prefix=[i for i in ins if i.address<=ANCHOR]
    eax_defs=[rec(i) for i in prefix if i.address<ANCHOR and writes(md,i,"eax")]
    req(eax_defs,"no EAX def before anchor")

    incoming=[]
    for es in ss:
        if not es["executable"]:continue
        emd,eins=dis(raw,es)
        for j,i in enumerate(eins):
            if i.mnemonic not in ("call","jmp"):continue
            if target(i)!=START:continue
            incoming.append({"section":es["name"],"edge":rec(i),
                             "contextBefore":[rec(x) for x in eins[max(0,j-CTX):j]],
                             "contextAfter":[rec(x) for x in eins[j+1:min(len(eins),j+24)]]})
    doc={
      "format":"t6-current-client-generic-19660-owner-eax-provenance-v1",
      "authority":"SHA-pinned exact function prefix and direct incoming-edge census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "function":{"startVa":f"0x{START:08X}","diagnosticEndVaExclusive":f"0x{s['va']+(pad-s['rawOffset']):08X}","sha256":hashlib.sha256(blob).hexdigest(),"instructions":[rec(i) for i in ins]},
      "anchor":rec(by[ANCHOR]),
      "eaxDefinitionsBeforeAnchor":eax_defs,
      "directIncomingEdges":incoming,
      "summary":{"lastEaxDefinitionBeforeAnchor":eax_defs[-1],"directIncomingEdgeCount":len(incoming),"esiExpressionAtAnchor":"EAX_at_0x009BB676"},
      "proofBoundary":"Closes exact local EAX->ESI provenance at 0x009BB676 and decoded direct incoming calls to 0x009BB670. Source-level semantic identity still requires joining the EAX producer/caller argument path."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
