#!/usr/bin/env python3
"""Close the remaining live-in object provenance for T6 primary-lightmap writers.

Targets:
1) 0x009C2A88 path:
   0x009B5C0A -> 0x009B7E80 arg1 = [EDI+0x110] in caller region
   0x009B5960..0x009B5C93. Recover EDI's exact local provenance and incoming
   edges to that caller region.

2) 0x009C1DBB path:
   local entry 0x009C1D50 establishes writer base = live-in EBX + 0xF00.
   Enumerate all decoded direct control-flow edges to 0x009C1D50 and retain
   bounded predecessor context to recover EBX provenance.

Exact current-client SHA only. No source-level identity is inferred from offsets.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
CALLER_START=0x009B5960
CALLER_END=0x009B5C93
ARG_SOURCE=0x009B5B8C
CALL_TO_ENCLOSING=0x009B5C0A
ENTRY_9C1DBB=0x009C1D50
CTX=96

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]; req(raw[p:p+4]==b"PE\0\0","bad PE")
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
    raise E(f"unbacked {va:x}")

def rec(i): return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def parse_target(i):
    s=i.op_str.strip().lower()
    if not s.startswith("0x"): return None
    try:return int(s,16)
    except:return None

def quick(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=False;md.skipdata=True
    return [i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]

def detailed_range(raw,s,a,b):
    off=s["rawOffset"]+(a-s["va"])
    blob=raw[off:off+b-a]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,a))
    return md,ins,blob

def incoming_edges(raw,secs,target):
    out=[]
    for s in secs:
        if not s["executable"]:continue
        ins=quick(raw,s)
        for j,i in enumerate(ins):
            if not (i.mnemonic=="call" or i.mnemonic=="jmp" or i.mnemonic.startswith("j")): continue
            if parse_target(i)!=target:continue
            out.append({
              "section":s["name"],"edge":rec(i),
              "contextBefore":[rec(x) for x in ins[max(0,j-CTX):j]],
              "contextAfter":[rec(x) for x in ins[j+1:min(len(ins),j+24)]],
            })
    return out

def reg_writes(md,ins,reg,limit_addr=None):
    out=[]
    for i in ins:
        if limit_addr is not None and i.address>=limit_addr:break
        _r,w=i.regs_access()
        if any(md.reg_name(x)==reg for x in w):out.append(rec(i))
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=pe(raw)

    s=sec_for(secs,CALLER_START);req(sec_for(secs,CALLER_END-1)["name"]==s["name"],"caller crosses section")
    md,caller,caller_blob=detailed_range(raw,s,CALLER_START,CALLER_END)
    by={i.address:i for i in caller}
    req(ARG_SOURCE in by and by[ARG_SOURCE].mnemonic=="mov" and by[ARG_SOURCE].op_str=="ecx, dword ptr [edi + 0x110]","arg-source drift")
    req(CALL_TO_ENCLOSING in by and by[CALL_TO_ENCLOSING].mnemonic=="call" and parse_target(by[CALL_TO_ENCLOSING])==0x009B7E80,"call drift")
    edi_writes=reg_writes(md,caller,"edi",ARG_SOURCE)
    ecx_writes_after=[x for x in reg_writes(md,[i for i in caller if i.address>=ARG_SOURCE],"ecx",CALL_TO_ENCLOSING)]
    caller_incoming=incoming_edges(raw,secs,CALLER_START)

    entry_edges=incoming_edges(raw,secs,ENTRY_9C1DBB)

    doc={
      "format":"t6-current-client-primary-lightmap-remaining-livein-provenance-v1",
      "authority":"SHA-pinned targeted current-client register dataflow plus decoded direct-control-transfer census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "writer9C2A88Upstream":{
        "callerRegion":{"startVa":f"0x{CALLER_START:08X}","endVaExclusive":f"0x{CALLER_END:08X}","sha256":hashlib.sha256(caller_blob).hexdigest(),"instructionCount":len(caller)},
        "arg1Definition":rec(by[ARG_SOURCE]),
        "enclosingCall":rec(by[CALL_TO_ENCLOSING]),
        "ediWritesBeforeArg1Definition":edi_writes,
        "ecxWritesFromArgDefinitionToCall":ecx_writes_after,
        "directIncomingEdgesToCallerRegion":caller_incoming,
        "currentExpression":"*(EDI_at_0x009B5B8C + 0x110) + 0xF00"
      },
      "writer9C1DBBUpstream":{
        "entryVa":f"0x{ENTRY_9C1DBB:08X}",
        "writerBaseAtEntry":"live-in EBX + 0xF00",
        "directControlFlowEdgesToEntry":entry_edges
      },
      "summary":{
        "writer9C2A88EdiWriteCountBeforeArgDefinition":len(edi_writes),
        "writer9C2A88IncomingEdgeCountToCallerRegion":len(caller_incoming),
        "writer9C1DBBIncomingEdgeCountToEntry":len(entry_edges)
      },
      "proofBoundary":"Exact decoded current-client dataflow/census. Register writes are authoritative locally; incoming contexts are retained for provenance closure. No live-in register or pointed-to field receives a source-level type/name without separate identity evidence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__":main()
