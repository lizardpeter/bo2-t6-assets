#!/usr/bin/env python3
"""Reduce the seven exact record-8 first-dword consumers to tight contexts."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SRC_FMT="t6-current-client-render-target-record8-first-dword-consumers-v1"
FORMAT="t6-current-client-record8-consumer-compact-v1"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text())
    if d.get("format")!=SRC_FMT:raise SystemExit("source format drift")
    rows=[]
    for c in d["consumers"]:
      rows.append({
        "instruction":c["instruction"],
        "references":c["references"],
        "before":c.get("contextBefore",[])[-10:],
        "after":c.get("contextAfter",[])[:10],
      })
    if len(rows)!=7:raise SystemExit(f"consumer count {len(rows)}")
    doc={"format":FORMAT,"authority":"exact reduction of record-8 first-dword current-client consumers",
      "client":d["client"],"source":{"path":str(a.source),"sha256":sha(a.source)},
      "summary":{"consumerCount":len(rows),"addresses":[x["instruction"]["address"] for x in rows]},
      "consumers":rows,
      "proofBoundary":"Exact bounded decoded neighborhoods only. No consumer semantics are promoted by reduction."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc,indent=2,sort_keys=True))
if __name__=="__main__":main()
