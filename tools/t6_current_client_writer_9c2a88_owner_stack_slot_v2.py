#!/usr/bin/env python3
"""Corrected exact stack proof for the value-1 primary-lightmap writer owner.

Separates the function ending at 0x009B59EC from the real framed function
starting at 0x009B59F0. Then proves [ESP+0x7C] at 0x009B59F6 is arg1 of the
0x009B59F0 function.

This supersedes the earlier v1 boundary claim that started at 0x009B5960.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_REG

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
PREV_RET=0x009B59EC
START=0x009B59F0
ANCHOR=0x009B59F6
DISP=0x7C

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
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
def off(s,va):return s["rawOffset"]+(va-s["va"])
def row(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def esp_step(md,i,d):
    mn=i.mnemonic.lower()
    if mn=="push":return d-4,"push => ESP-4"
    if mn=="pop":return d+4,"pop => ESP+4"
    if mn in ("sub","add") and len(i.operands)==2:
        a,b=i.operands
        if a.type==X86_OP_REG and md.reg_name(a.reg)=="esp" and b.type==X86_OP_IMM:
            imm=int(b.imm)
            return (d-imm if mn=="sub" else d+imm),f"{mn} esp,{imm:#x}"
    return d,None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,ss=pe(raw);s=sec(ss,START)

    # Hard boundary gates.
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    gate_blob=raw[off(s,PREV_RET):off(s,START)+7]
    gate=list(md.disasm(gate_blob,PREV_RET));by={i.address:i for i in gate}
    req(PREV_RET in by and by[PREV_RET].mnemonic=="ret","previous function ret drift")
    req(raw[off(s,0x009B59ED):off(s,0x009B59F0)]==b"\xcc\xcc\xcc","padding drift")
    req(START in by and by[START].mnemonic=="sub" and by[START].op_str=="esp, 0x6c","new function prologue drift")

    # Decode exact current function until next 8-byte INT3 pad.
    start_off=off(s,START);pad=raw.find(b"\xcc"*8,start_off)
    req(pad>=0,"next pad not found")
    blob=raw[start_off:pad];ins=list(md.disasm(blob,START));by2={i.address:i for i in ins}
    req(ANCHOR in by2,"anchor missing")
    req(by2[ANCHOR].mnemonic=="mov" and by2[ANCHOR].op_str=="edi, dword ptr [esp + 0x7c]","anchor drift")

    d=0;trace=[]
    for i in ins:
        if i.address>ANCHOR:break
        before=d
        if i.address==ANCHOR:
            eff=d+DISP
            trace.append({"instruction":row(i),"espRelativeToEntryBefore":before,"memoryAddressRelativeToEntry":eff})
            break
        d,why=esp_step(md,i,d)
        if why:trace.append({"instruction":row(i),"espRelativeToEntryBefore":before,"espRelativeToEntryAfter":d,"effect":why})
    eff=d+DISP
    req(eff==4,f"expected arg1 [S+4], got {eff:#x}")

    doc={
      "format":"t6-current-client-writer-9c2a88-owner-stack-slot-v2",
      "authority":"SHA-pinned exact function-boundary gates and entry-relative ESP arithmetic",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "boundary":{"previousRet":row(by[PREV_RET]),"padding":"0x009B59ED..0x009B59EF = INT3","functionStart":row(by[START])},
      "function":{"startVa":f"0x{START:08X}","diagnosticEndVaExclusive":f"0x{s['va']+(pad-s['rawOffset']):08X}","sha256":hashlib.sha256(blob).hexdigest()},
      "anchor":{"instruction":row(by2[ANCHOR]),"espRelativeToEntry":d,"effectiveEntryRelativeOffset":eff,"classification":"arg1 at [S+0x4]"},
      "espTrace":trace,
      "summary":{"correctFunctionStartVa":f"0x{START:08X}","ediExpression":"arg1","downstreamWriterBaseExpression":"*(arg1+0x110)+0xF00","previousFunctionReturnVa":f"0x{PREV_RET:08X}"},
      "proofBoundary":"Closes the exact 0x009B59F0 function boundary and proves EDI at 0x009B59F6 equals this function's arg1. It does not assign arg1 a source-level type or exclude indirect/internal entry paths elsewhere."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
