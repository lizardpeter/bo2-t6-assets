#!/usr/bin/env python3
"""Recover the true current-client boundary around the owner+0x5DAC constructor.

Scans all decoded executable direct CALL/JMP edges into 0x0067D200..0x0067D3A7
and preserves the exact local range. Intended to distinguish the true entry at
0x0067D250 from nearby code/padding without treating INT3 alone as authority.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
LO=0x0067D200
HI=0x0067D3A7
CAND=0x0067D250

class E(RuntimeError):pass
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
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked {va:x}")
def off(s,va):return s["rawOffset"]+va-s["va"]
def row(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,ss=pe(raw);s=sec(ss,LO);req(sec(ss,HI-1)["name"]==s["name"],"range crosses section")
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    blob=raw[off(s,LO):off(s,HI)]
    local=[i for i in md.disasm(blob,LO) if i.id]
    cand=[i for i in local if i.address>=CAND]
    req(cand and cand[0].address==CAND,"candidate does not decode cleanly")
    req(cand[0].mnemonic=="mov" and cand[0].op_str=="eax, ecx","candidate entry drift")
    ret=next((i for i in cand if i.address==0x0067D3A4),None)
    req(ret and ret.mnemonic=="ret" and ret.op_str=="0xc","candidate return drift")

    incoming=[]
    for es in ss:
        if not es["executable"]:continue
        data=raw[es["rawOffset"]:es["rawOffset"]+es["rawSize"]]
        ins=[i for i in md.disasm(data,es["va"]) if i.id]
        for idx,i in enumerate(ins):
            if i.mnemonic not in ("call","jmp") or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            t=int(i.operands[0].imm)&0xffffffff
            if LO<=t<HI:
                incoming.append({"source":row(i),"targetVa":f"0x{t:08X}","section":es["name"],
                                 "before":[row(x) for x in ins[max(0,idx-24):idx]],
                                 "after":[row(x) for x in ins[idx+1:min(len(ins),idx+13)]]})
    targets=sorted({x["targetVa"] for x in incoming})
    cand_blob=raw[off(s,CAND):off(s,0x0067D3A7)]
    doc={
      "format":"t6-current-client-owner-5dac-constructor-boundary-v1",
      "authority":"SHA-pinned current-client exact local bytes plus decoded direct incoming-control-transfer census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "window":{"startVa":f"0x{LO:08X}","endVaExclusive":f"0x{HI:08X}","instructions":[row(i) for i in local]},
      "candidate":{"startVa":f"0x{CAND:08X}","endVaExclusive":"0x0067D3A7","returnVa":"0x0067D3A4",
                   "sha256":hashlib.sha256(cand_blob).hexdigest()},
      "incomingEdges":incoming,
      "summary":{"incomingEdgeCount":len(incoming),"incomingTargetVAs":targets,
                 "candidateDirectIncomingEdgeCount":sum(1 for x in incoming if x["targetVa"]==f"0x{CAND:08X}")},
      "proofBoundary":"Direct decoded CALL/JMP census plus exact bytes. Indirect entries are not excluded. Candidate entry is accepted only as an exact decoded boundary when supported by its entry/return shape and incoming-edge topology; source-level name remains unassigned."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
