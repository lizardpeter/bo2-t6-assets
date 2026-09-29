#!/usr/bin/env python3
"""Resolve the original entry-stack identity of EDI at 0x009B59F6.

Exact upstream proof establishes:
  0x009B59F6: EDI = [ESP+0x7C]
  0x009B5B8C: ECX = [EDI+0x110]
  0x009B5C09: push ECX
  0x009B5C0A: call 0x009B7E80
  downstream 0x009C2A88 destination base = arg1 + 0xF00

This probe decodes the exact function prefix 0x009B5960..0x009B59F6,
tracks caller-visible ESP changes instruction by instruction, and fails closed
if non-linear control flow or unsupported ESP mutation occurs before the EDI load.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x009B5960
LOAD=0x009B59F6
END=0x009B59FC

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro))
    return base,ss
def sec(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked {va:x}")
def rec(i,delta=None):
    d={"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
    if delta is not None:d["entryEspDeltaAfter"]=delta
    return d
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,ss=pe(raw);s=sec(ss,START);req(sec(ss,END-1)["name"]==s["name"],"cross-section")
    off=s["rawOffset"]+(START-s["va"]);blob=raw[off:off+END-START]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,START));by={x.address:x for x in ins}
    req(START in by and LOAD in by,"decode drift")
    load=by[LOAD];req(load.mnemonic=="mov" and load.op_str=="edi, dword ptr [esp + 0x7c]",f"load drift {load.mnemonic} {load.op_str}")

    delta=0
    trace=[]
    unsupported=[]
    branches=[]
    for x in ins:
        if x.address>=LOAD:break
        mn=x.mnemonic;op=x.op_str.lower()
        if mn.startswith("j") or mn in ("loop","loope","loopne"):
            branches.append(rec(x))
        if mn=="push":
            delta-=4
        elif mn=="pop":
            delta+=4
        elif mn=="sub" and op.startswith("esp, "):
            delta-=int(op.split(",",1)[1].strip(),0)
        elif mn=="add" and op.startswith("esp, "):
            delta+=int(op.split(",",1)[1].strip(),0)
        elif mn=="lea" and op.startswith("esp, [esp + ") and op.endswith("]"):
            imm=op[len("esp, [esp + "):-1]
            delta+=int(imm,0)
        elif mn=="lea" and op.startswith("esp, [esp - ") and op.endswith("]"):
            imm=op[len("esp, [esp - "):-1]
            delta-=int(imm,0)
        else:
            # Fail closed only for explicit ESP writes not handled above.
            _r,w=x.regs_access()
            if any(md.reg_name(z)=="esp" for z in w) and mn!="call":
                unsupported.append(rec(x))
        trace.append(rec(x,delta))
    req(not unsupported,f"unsupported ESP writes: {unsupported}")
    req(not branches,f"non-linear branch before load: {branches}")

    effective=delta+0x7c
    if effective>=4 and effective%4==0:
        ordinal=(effective-4)//4+1
        entry_expr=f"entry_arg{ordinal}" if ordinal>=1 else f"entry_esp+0x{effective:X}"
    else:
        ordinal=None;entry_expr=f"entry_esp{effective:+#x}"

    doc={
      "format":"t6-current-client-writer-9c2a88-owner-stack-identity-v1",
      "authority":"SHA-pinned current-client exact function-prefix stack arithmetic",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "prefix":{"startVa":f"0x{START:08X}","loadVa":f"0x{LOAD:08X}","sha256":hashlib.sha256(blob[:LOAD-START+load.size]).hexdigest(),
                "instructions":trace},
      "load":rec(load),
      "stack":{"entryEspDeltaAtLoad":delta,"loadDisplacement":0x7c,
               "effectiveEntryEspOffset":effective,"entryArgumentOrdinal":ordinal,
               "entryExpression":entry_expr},
      "summary":{"ediExpression":entry_expr,"writerOwnerExpression":entry_expr,
                 "writerDestinationBaseExpression":f"*({entry_expr}+0x110)+0xF00",
                 "branchCountBeforeLoad":len(branches),"unsupportedEspMutationCount":len(unsupported)},
      "proofBoundary":"Closes only the exact entry-stack identity reaching EDI at 0x009B59F6 for the straight-line decoded prefix. The semantic type of that entry argument remains unassigned until separately evidenced."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
