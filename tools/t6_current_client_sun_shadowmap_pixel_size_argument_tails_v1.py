#!/usr/bin/env python3
"""Compact exact argument tails for all five sunShadowmapPixelSize callers."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-sun-shadowmap-pixel-size-argument-tails-v1"
SOURCE_FORMAT="t6-current-client-sun-shadowmap-pixel-size-caller-arguments-v1"

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c: raise SystemExit(m)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    d=json.loads(a.source.read_text())
    req(d.get("format")==SOURCE_FORMAT,"source format drift")
    rows=[]
    for c in d["callers"]:
        before=c.get("contextBefore",[])
        pushes=[x for x in before if x.get("mnemonic")=="push"]
        req(len(pushes)>=2,f"{c['call']['address']}: fewer than two pushes in caller window")
        rows.append({
          "call":c["call"],
          "lastTwoPushes":pushes[-2:],
          "tail":before[-20:],
          "contextAfter":c.get("contextAfter",[])[:6],
        })
    out={
      "format":FORMAT,
      "authority":"lossless compact projection of exact five-callsite argument setup windows",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "target":d["target"],
      "summary":{"callerCount":len(rows),"callAddresses":[r["call"]["address"] for r in rows]},
      "callers":rows,
      "proofBoundary":"Projection only. The two nearest pushes and final 20 setup instructions are retained exactly; register/source provenance and semantic naming require the next reduction."
    }
    req(len(rows)==5,"caller denominator drift")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__": main()
