#!/usr/bin/env python3
"""Fast exact provenance proof for the 0x009C2A88 writer's upstream base.

Prior exact evidence establishes:
  0x009B80E9 -> 0x009C1EF0
  0x009B80DA loads ESI from [EBP+8]
  0x009B80E2 pushes ESI as callee arg1
  0x009C2A88 destination base = callee_arg1 + 0xF00

This proof resolves what EBP means in the exact caller region containing
0x009B80E9. It deliberately avoids whole-image detailed disassembly:
INT3 runs locate a diagnostic region by raw bytes, only that region is
decoded with register detail, and direct incoming edges are found with a
single detail-free .text pass.

INT3 boundaries remain diagnostic until the decoded prologue/control flow
supports a true function entry.
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ANCHOR=0x009B80E9
DOWNSTREAM=0x009C1EF0

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)

def parse_pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]
    req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4
    n=struct.unpack_from("<H",raw,coff+2)[0]
    osz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20
    base=struct.unpack_from("<I",raw,opt+28)[0]
    so=opt+osz
    secs=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append(dict(name=name,va=base+rva,virtualSize=vs,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,secs

def sec_for(secs,va):
    for s in secs:
        if s["va"] <= va < s["va"]+s["rawSize"]:
            return s
    raise E(f"VA 0x{va:08X} not backed")

def va_to_off(s,va): return s["rawOffset"] + (va-s["va"])

def rec(i):
    return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def diagnostic_raw_region(raw,s,anchor_va):
    rel=anchor_va-s["va"]
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    req(0 <= rel < len(data),"anchor outside section")
    before=list(re.finditer(b"\xCC{8,}",data[:rel]))
    req(before,"no preceding INT3 run")
    start_rel=before[-1].end()
    while start_rel < len(data) and data[start_rel]==0xCC:
        start_rel+=1
    after=re.search(b"\xCC{8,}",data[rel+1:])
    req(after is not None,"no following INT3 run")
    end_rel=rel+1+after.start()
    return s["va"]+start_rel,s["va"]+end_rel,data[start_rel:end_rel]

def disasm_region(blob,start,detail=True):
    md=Cs(CS_ARCH_X86,CS_MODE_32)
    md.detail=detail
    return md,list(md.disasm(blob,start))

def direct_edges_to(raw,s,target):
    # One detail-free .text pass: much faster than repeated detailed passes.
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    md=Cs(CS_ARCH_X86,CS_MODE_32)
    md.detail=True
    md.skipdata=True
    out=[]
    for ins in md.disasm(data,s["va"]):
        if ins.mnemonic not in ("call","jmp") or len(ins.operands)!=1:
            continue
        op=ins.operands[0]
        if op.type==X86_OP_IMM and (int(op.imm)&0xffffffff)==target:
            out.append(rec(ins))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--revision",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    raw=a.exe.read_bytes()
    dg=hashlib.sha256(raw).hexdigest()
    req(dg==SHA,f"SHA drift {dg}")
    base,secs=parse_pe(raw)
    s=sec_for(secs,ANCHOR)

    start,end,blob=diagnostic_raw_region(raw,s,ANCHOR)
    md,ins=disasm_region(blob,start,True)
    by={i.address:i for i in ins}
    req(ANCHOR in by,"anchor not decoded")
    ai=next(i for i,x in enumerate(ins) if x.address==ANCHOR)
    anchor=ins[ai]
    req(anchor.mnemonic=="call" and anchor.op_str.lower()=="0x9c1ef0",f"anchor drift {anchor.mnemonic} {anchor.op_str}")
    req(0x009B80DA in by and by[0x009B80DA].op_str=="esi, dword ptr [ebp + 8]","arg-source load drift")
    req(0x009B80E2 in by and by[0x009B80E2].mnemonic=="push" and by[0x009B80E2].op_str=="esi","arg push drift")

    # All EBP definitions before the downstream call in this exact region.
    ebp_defs=[]
    for x in ins[:ai]:
        _r,w=x.regs_access()
        if any(md.reg_name(r)=="ebp" for r in w):
            ebp_defs.append(rec(x))

    # Establish whether EBP is a conventional frame pointer.
    first_nontrivial=[x for x in ins[:16] if x.mnemonic!="nop"]
    frame_pairs=[]
    for j,x in enumerate(ins[:-1]):
        y=ins[j+1]
        if x.mnemonic=="push" and x.op_str=="ebp" and y.mnemonic=="mov" and y.op_str=="ebp, esp":
            frame_pairs.append({"push":rec(x),"mov":rec(y)})
    last_ebp_def=ebp_defs[-1] if ebp_defs else None

    # Exact local context around [EBP+8] and call.
    lo=max(0,ai-96); hi=min(len(ins),ai+40)
    local=[rec(x) for x in ins[lo:hi]]

    incoming=direct_edges_to(raw,s,start)

    # If EBP was set from a register/stack object after any frame-pair, retain the
    # exact last definition instead of calling [EBP+8] an argument.
    frame_pointer_at_anchor=False
    if frame_pairs and last_ebp_def:
        fp_mov=frame_pairs[-1]["mov"]["address"]
        frame_pointer_at_anchor = last_ebp_def["address"]==fp_mov

    classification = (
        "function-arg1-via-frame-pointer"
        if frame_pointer_at_anchor else
        "object-or-register-relative-field-not-proven-function-arg"
    )

    doc={
      "format":"t6-current-client-writer-9c2a88-caller-ebp-provenance-v2",
      "authority":"SHA-pinned current-client bounded region + exact register writes + single-pass decoded direct-edge census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "region":{"diagnosticStartVa":f"0x{start:08X}","diagnosticEndVaExclusive":f"0x{end:08X}",
                "bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),"instructionCount":len(ins)},
      "anchor":{"call":rec(anchor),"sourceLoad":rec(by[0x009B80DA]),"argPush":rec(by[0x009B80E2]),
                "downstreamDestinationBase":"value loaded from [EBP+8] + 0xF00"},
      "ebp":{"definitionsBeforeAnchor":ebp_defs,"lastDefinitionBeforeAnchor":last_ebp_def,
             "frameSetupPairs":frame_pairs,"framePointerAtAnchor":frame_pointer_at_anchor,
             "classification":classification},
      "directIncomingEdgesToDiagnosticStart":incoming,
      "localContext":local,
      "summary":{"diagnosticStartVa":f"0x{start:08X}","diagnosticEndVaExclusive":f"0x{end:08X}",
                 "instructionCount":len(ins),"ebpDefinitionCountBeforeAnchor":len(ebp_defs),
                 "frameSetupPairCount":len(frame_pairs),"framePointerAtAnchor":frame_pointer_at_anchor,
                 "ebpClassification":classification,"directIncomingEdgeCount":len(incoming),
                 "destinationBaseExpression":"value_at_[EBP+8] + 0xF00"},
      "proofBoundary":"Closes the exact local meaning of EBP at the 0x009B80E9 direct-call occurrence. INT3 boundaries are diagnostic. If EBP is not proven to be the active frame pointer, [EBP+8] is not promoted as function arg1; it remains an object/register-relative field until upstream EBP provenance is closed."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__":
    main()
