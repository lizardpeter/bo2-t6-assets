#!/usr/bin/env python3
"""Compact exact postFxControl0..3 writer dataflow windows for semantic closure.

Consumes the already-frozen complete writer-family proof and emits a small,
reviewable projection around every exact value/version write plus every direct
caller. This is deliberately a projection only: it does not promote formulas.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FORMAT="t6-current-client-postfx-control0-3-compact-dataflow-v1"
SOURCE_FORMAT="t6-current-client-postfx-control0-3-complete-writer-family-v1"
TARGETS={f"postFxControl{i}":107+i for i in range(4)}
PRE=18
POST=6

def sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def req(c,m):
    if not c: raise SystemExit(m)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    d=json.loads(a.source.read_text())
    req(d.get("format")==SOURCE_FORMAT,"source format drift")
    funcs=[]
    total_windows=0
    for f in d.get("functions",[]):
        ins=f.get("instructions",[])
        by_addr={x["address"]:i for i,x in enumerate(ins)}
        windows=[]
        for w in f.get("writes",[]):
            addr=w["instruction"]["address"]
            n=by_addr.get(addr)
            req(n is not None,f"{f.get('startVa')}: missing write instruction {addr}")
            lo=max(0,n-PRE); hi=min(len(ins),n+POST+1)
            windows.append({
                "accessor":w["accessor"],
                "enumValue":w["enumValue"],
                "field":w["field"],
                "targetVa":w["targetVa"],
                "write":w["instruction"],
                "window":ins[lo:hi],
            })
        # Compact caller windows further: the source proof retains 28 instructions
        # on each side; keep 20/10 around the exact call.
        callers=[]
        for c in f.get("directCallers",[]):
            callers.append({
                "call":c["call"],
                "contextBefore":c.get("contextBefore",[])[-20:],
                "contextAfter":c.get("contextAfter",[])[:10],
            })
        # Retain memory-touching instructions once per function so source-record
        # accesses that sit just outside an individual write window remain visible.
        mem=[x for x in ins if "[" in x.get("opStr","")]
        funcs.append({
            "startVa":f["startVa"],
            "endVaExclusive":f["endVaExclusive"],
            "instructionCount":f["instructionCount"],
            "accessorWrites":f["accessorWrites"],
            "directCallerCount":len(f.get("directCallers",[])),
            "callers":callers,
            "writeWindows":windows,
            "memoryInstructions":mem,
        })
        total_windows += len(windows)
    denom=d.get("summary",{}).get("accessorWriterDenominator",{})
    req(set(denom)==set(TARGETS),"accessor denominator drift")
    out={
      "format":FORMAT,
      "authority":"lossless compact projection of frozen complete current-client postFxControl0..3 writer-family proof",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "summary":{
        "functionCount":len(funcs),
        "writeWindowCount":total_windows,
        "accessorWriterDenominator":denom,
        "functionMemoryInstructionCounts":{f["startVa"]:len(f["memoryInstructions"]) for f in funcs},
        "directCallerCounts":{f["startVa"]:f["directCallerCount"] for f in funcs},
      },
      "functions":funcs,
      "proofBoundary":"Projection only. Exact frozen instructions/callers/writes are preserved in compact form; no lane formula, source-record semantic identity, historical-retail equivalence or framebuffer effect is promoted by this file."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))

if __name__=="__main__":
    main()
