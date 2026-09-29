#!/usr/bin/env python3
"""Resolve the exact stack meaning of [ESP+0x7C] at 0x009B59F6.

SHA-pinned current-client proof for the path feeding primary-lightmap writer
0x009C2A88. The proof tracks ESP from the exact 0x009B5960 entry to the EDI
load at 0x009B59F6 and maps the accessed address back to the entry stack S.

No source-level type/name is assigned from the resulting stack slot alone.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_REG

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x009B5960
ANCHOR=0x009B59F6
DISP=0x7C

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)

def parse_pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]; req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4; n=struct.unpack_from("<H",raw,c+2)[0]; os=struct.unpack_from("<H",raw,c+16)[0]
    op=c+20; base=struct.unpack_from("<I",raw,op+28)[0]; so=op+os
    ss=[]
    for i in range(n):
        x=so+i*40
        name=raw[x:x+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,x+8)
        ch=struct.unpack_from("<I",raw,x+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss

def sec_for(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise E(f"unbacked {va:x}")

def row(i): return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def function_region(raw,s,start):
    off=s["rawOffset"]+(start-s["va"])
    end=s["rawOffset"]+s["rawSize"]
    pad=raw.find(b"\xcc"*8,off)
    req(pad>=0 and pad<end,"no following INT3 pad")
    blob=raw[off:pad]
    md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True
    ins=list(md.disasm(blob,start))
    req(ins and ins[0].address==start,"decode start failed")
    return md,ins,blob,s["va"]+(pad-s["rawOffset"])

def signed32(x):
    return x-0x100000000 if x & 0x80000000 else x

def esp_delta_step(md,i,delta):
    # delta is current ESP - entry_S.
    mn=i.mnemonic.lower()
    if mn=="push":
        return delta-4, "push => ESP-4"
    if mn=="pop":
        return delta+4, "pop => ESP+4"
    if mn in ("sub","add") and len(i.operands)==2:
        a,b=i.operands
        if a.type==X86_OP_REG and md.reg_name(a.reg)=="esp" and b.type==X86_OP_IMM:
            imm=int(b.imm)&0xffffffff
            simm=signed32(imm)
            if mn=="sub": return delta-simm, f"sub esp,{simm:#x}"
            else: return delta+simm, f"add esp,{simm:#x}"
    if mn=="lea" and i.op_str.startswith("esp, [esp"):
        # Handle common LEA ESP,[ESP+imm] textual shape conservatively.
        txt=i.op_str.lower()
        if "+" in txt:
            try:
                imm=int(txt.split("+",1)[1].split("]",1)[0].strip(),16)
                return delta+imm,f"lea esp,[esp+{imm:#x}]"
            except: pass
        if "-" in txt:
            try:
                imm=int(txt.split("-",1)[1].split("]",1)[0].strip(),16)
                return delta-imm,f"lea esp,[esp-{imm:#x}]"
            except: pass
    return delta,None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--revision",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    raw=a.exe.read_bytes(); dg=hashlib.sha256(raw).hexdigest(); req(dg==SHA,f"sha drift {dg}")
    base,ss=parse_pe(raw); s=sec_for(ss,START)
    md,ins,blob,end=function_region(raw,s,START)
    by={i.address:i for i in ins}
    req(ANCHOR in by,"anchor missing")
    req(by[ANCHOR].mnemonic=="mov" and by[ANCHOR].op_str=="edi, dword ptr [esp + 0x7c]",
        f"anchor drift {by[ANCHOR].mnemonic} {by[ANCHOR].op_str}")

    delta=0
    trace=[]
    for i in ins:
        if i.address>ANCHOR: break
        before=delta
        if i.address==ANCHOR:
            effective=delta+DISP
            trace.append({"instruction":row(i),"espRelativeToEntryBefore":before,
                          "memoryAddressRelativeToEntry":effective})
            break
        delta,why=esp_delta_step(md,i,delta)
        if why:
            trace.append({"instruction":row(i),"espRelativeToEntryBefore":before,
                          "espRelativeToEntryAfter":delta,"effect":why})

    effective=delta+DISP
    if effective==0: slot="entry return address [S+0]"
    elif effective>=4 and effective%4==0:
        slot=f"stack argument {(effective-4)//4 + 1} at [S+0x{effective:X}]"
    elif effective<0: slot=f"callee-local/saved area at [S{effective:+#x}]"
    else: slot=f"entry-relative stack slot [S+0x{effective:X}]"

    # Preserve exact entry prefix through anchor for independent review.
    prefix=[row(i) for i in ins if i.address<=ANCHOR]

    doc={
      "format":"t6-current-client-writer-9c2a88-owner-stack-slot-v1",
      "authority":"SHA-pinned exact entry-to-anchor ESP arithmetic",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "function":{"startVa":f"0x{START:08X}","diagnosticEndVaExclusive":f"0x{end:08X}",
                  "sha256":hashlib.sha256(blob).hexdigest()},
      "anchor":{"instruction":row(by[ANCHOR]),"espRelativeToEntry":delta,
                "displacement":DISP,"effectiveEntryRelativeOffset":effective,
                "classification":slot},
      "espTrace":trace,
      "entryPrefix":prefix,
      "summary":{"ediLoadVa":f"0x{ANCHOR:08X}","espRelativeToEntryAtLoad":delta,
                 "effectiveEntryRelativeOffset":effective,"slotClassification":slot},
      "proofBoundary":"Closes exact stack geometry from the decoded 0x009B5960 entry to 0x009B59F6. It does not identify the semantic type of the loaded pointer or prove indirect/internal entries absent."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__": main()
