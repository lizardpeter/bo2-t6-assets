#!/usr/bin/env python3
"""Project high stack-region provenance for the current-client shadow/source-state builder.

The 0x009AF970 window is already frozen exactly. This extracts every ESP-based
reference in the 0x1500..0x1600 band, which contains the source-state/code-image
arguments used by the shadow/dlight sampler path, and preserves nearby calls.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-shadow-source-state-high-stack-provenance-v1"
SOURCE_FORMAT="t6-current-client-shadowmap-sun-image-caller-stack-provenance-v1"
LO=0x1500; HI=0x1600; CTX=10

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c: raise SystemExit(m)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--source",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    d=json.loads(a.source.read_text()); req(d.get("format")==SOURCE_FORMAT,"source format drift")
    ins=d["instructions"]; by={x["address"]:i for i,x in enumerate(ins)}
    rows=[]
    for s in d.get("stackReferences",[]):
        refs=[r for r in s.get("stackRefs",[]) if r.get("baseReg")=="esp" and LO<=int(r.get("disp",0))<HI]
        if not refs: continue
        n=by.get(s["instruction"]["address"]); req(n is not None,"stack reference instruction missing")
        rows.append({
          "instruction":s["instruction"],"stackRefs":refs,
          "contextBefore":ins[max(0,n-CTX):n],
          "contextAfter":ins[n+1:min(len(ins),n+CTX+1)]
        })
    calls=[x for x in ins if x["mnemonic"]=="call"]
    out={
      "format":FORMAT,
      "authority":"lossless projection of exact frozen caller window high-stack references",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "range":{"minDisp":LO,"maxDispExclusive":HI},
      "summary":{"referenceInstructionCount":len(rows),"callCount":len(calls),
                 "displacements":sorted({r["disp"] for x in rows for r in x["stackRefs"]})},
      "references":rows,"calls":calls,
      "proofBoundary":"Projection only. High stack addresses and neighboring exact instructions are retained; source-state field naming, pointer identity and runtime resource semantics require explicit dataflow joins."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
