#!/usr/bin/env python3
"""Compact the exact unresolved sampler storage census to sun/dlight provider candidates."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-sun-dlight-sampler-writer-candidates-v1"
SRC_FMT="t6-current-client-unresolved-sampler-storage-xrefs-v1"
TARGETS={"shadowmapSamplerSun","dlightAttenuationSampler"}

def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text())
    if d.get("format")!=SRC_FMT:raise SystemExit(f"source format drift {d.get('format')!r}")
    hits=[]
    for h in d.get("hits",[]):
        refs=[r for r in h.get("references",[]) if r.get("accessor") in TARGETS]
        if not refs:continue
        hits.append({
          "section":h.get("section"),
          "diagnosticFunctionStartVa":h.get("diagnosticFunctionStartVa"),
          "instruction":h["instruction"],
          "references":refs,
          "contextBefore":h.get("contextBefore",[]),
          "contextAfter":h.get("contextAfter",[]),
        })
    rows={}
    for acc in sorted(TARGETS):
        ah=[h for h in hits if any(r.get("accessor")==acc for r in h["references"])]
        dest=[(h,r) for h in ah for r in h["references"] if r.get("accessor")==acc and r.get("role")=="destination-or-rmw"]
        src=[(h,r) for h in ah for r in h["references"] if r.get("accessor")==acc and r.get("role")=="source-or-read"]
        rows[acc]={
          "hitInstructionCount":len(ah),
          "destinationReferenceCount":len(dest),
          "sourceReferenceCount":len(src),
          "destinationInstructions":[{"instruction":h["instruction"],"reference":r,"diagnosticFunctionStartVa":h.get("diagnosticFunctionStartVa")} for h,r in dest],
          "sourceInstructions":[{"instruction":h["instruction"],"reference":r,"diagnosticFunctionStartVa":h.get("diagnosticFunctionStartVa")} for h,r in src],
          "hits":ah,
        }
    doc={"format":FORMAT,
      "authority":"exact subset projection of SHA-classified current-client unresolved sampler storage xrefs",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "rows":rows,
      "summary":{acc:{k:v for k,v in rows[acc].items() if k in ("hitInstructionCount","destinationReferenceCount","sourceReferenceCount")} for acc in sorted(rows)},
      "proofBoundary":"Projection only. It preserves exact destination/source instructions and bounded contexts for the two target unresolved samplers. No base-register source-state identity, image provenance, sampler-state meaning, historical-retail equivalence or framebuffer semantics is promoted."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
