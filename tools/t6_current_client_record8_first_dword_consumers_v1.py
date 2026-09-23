#!/usr/bin/env python3
"""Project exact current-client references to render-target record 8 first dword."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SRC_FMT="t6-current-client-render-target-record8-xref-v1"
FORMAT="t6-current-client-render-target-record8-first-dword-consumers-v1"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text())
    if d.get("format")!=SRC_FMT:raise SystemExit("source format drift")
    xs=[]
    for x in d.get("xrefs",[]):
      if any(r["targetVa"]=="0x03a267c0" for r in x.get("references",[])):xs.append(x)
    if len(xs)!=7:raise SystemExit(f"record8 first-dword xrefs={len(xs)}")
    xs=sorted(xs,key=lambda x:int(x["instruction"]["address"],16))
    doc={"format":FORMAT,"authority":"exact projection of SHA-classified current-client record-8 xref census",
      "client":d["client"],"source":{"path":str(a.source),"sha256":sha(a.source)},
      "summary":{"consumerInstructionCount":len(xs),"consumerAddresses":[x["instruction"]["address"] for x in xs]},
      "consumers":xs,
      "proofBoundary":"Exact record-8 first-dword consumers only. No consumer is yet assigned floatZ, image, resolve, sampler, or render-pass semantics."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
