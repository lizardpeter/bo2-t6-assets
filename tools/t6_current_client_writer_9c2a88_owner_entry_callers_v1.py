#!/usr/bin/env python3
"""Trace direct callers and arg1 provenance for the true 0x009B59F0 owner-caller entry.

Upstream exact proof closes:
  0x009B59F6 EDI = function arg1
  0x009B5B8C ECX = [EDI+0x110]
  0x009B5C0A -> 0x009B7E80 arg1 = ECX
  value-1 primary-lightmap writer base = *(0x009B59F0_arg1+0x110)+0xF00

This probe validates the 0x009B59F0 prologue, enumerates all decoded direct
CALL/JMP edges to that exact entry, and retains bounded predecessor context
plus the last stack push before each call so arg1 can be closed without
name/address guessing.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ENTRY=0x009B59F0
CTX=128

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

def dis(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=False;md.skipdata=True
    return [i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--revision",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,ss=pe(raw);s=sec_for(ss,ENTRY)
    ins=dis(raw,s);by={i.address:i for i in ins}
    gates={
      0x009B59F0:("sub","esp, 0x6c"),
      0x009B59F3:("push","ebp"),
      0x009B59F4:("push","esi"),
      0x009B59F5:("push","edi"),
      0x009B59F6:("mov","edi, dword ptr [esp + 0x7c]"),
    }
    for va,(mn,op) in gates.items():
        x=by.get(va);req(x is not None,f"missing {va:x}")
        req(x.mnemonic==mn and x.op_str.lower()==op.lower(),f"drift {va:x}: {x.mnemonic} {x.op_str}")

    edges=[]
    for es in ss:
        if not es["executable"]: continue
        xs=dis(raw,es)
        for j,x in enumerate(xs):
            if x.mnemonic not in ("call","jmp"): continue
            if parse_target(x)!=ENTRY: continue
            before=xs[max(0,j-CTX):j]
            after=xs[j+1:min(len(xs),j+24)]
            last_push=None
            for p in reversed(before):
                if p.mnemonic=="push":
                    last_push=rec(p);break
                if p.mnemonic.startswith("ret") or p.mnemonic=="jmp":
                    break
            # preserve last register/immediate textual definitions in bounded context
            pushed_reg=None
            if last_push and last_push["opStr"].lower() in ("eax","ebx","ecx","edx","esi","edi","ebp"):
                pushed_reg=last_push["opStr"].lower()
            defs=[]
            if pushed_reg:
                for p in before:
                    op=p.op_str.lower()
                    if op.startswith(pushed_reg+",") or (p.mnemonic=="pop" and op==pushed_reg):
                        defs.append(rec(p))
            edges.append({
              "section":es["name"],
              "edge":rec(x),
              "lastPushBeforeEdge":last_push,
              "pushedRegister":pushed_reg,
              "pushedRegisterDefinitionsInContext":defs,
              "lastPushedRegisterDefinition":defs[-1] if defs else None,
              "contextBefore":[rec(p) for p in before],
              "contextAfter":[rec(p) for p in after],
            })

    doc={
      "format":"t6-current-client-writer-9c2a88-owner-entry-callers-v1",
      "authority":"SHA-pinned exact 0x009B59F0 entry validation plus instruction-aligned direct incoming-edge census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "entry":{"va":f"0x{ENTRY:08X}","prologue":[rec(by[x]) for x in sorted(gates)],
               "arg1Load":rec(by[0x009B59F6]),
               "downstreamWriterBase":"*(arg1+0x110)+0xF00"},
      "directIncomingEdges":edges,
      "summary":{"entryVa":f"0x{ENTRY:08X}","directIncomingEdgeCount":len(edges),
                 "edgeArgPushes":[{"edge":e["edge"],"lastPush":e["lastPushBeforeEdge"],"lastDefinition":e["lastPushedRegisterDefinition"]} for e in edges]},
      "proofBoundary":"Exact decoded direct CALL/JMP census only. Last push is retained as direct call-site evidence but semantic arg identity is promoted only where calling convention and local dataflow are unambiguous. Indirect calls remain outside this proof."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__": main()
