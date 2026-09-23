#!/usr/bin/env python3
"""Compact exact current-client direct-write clusters for retained-special float4 inputs."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SRC_FMT="t6-current-client-special-constant-direct-slot-xrefs-v1"
FORMAT="t6-current-client-special-constant-direct-write-clusters-v1"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text())
    if d.get("format")!=SRC_FMT:raise SystemExit("source format drift")
    rows=[]
    for r in d["rows"]:
      if int(r["directDestinationOrRmwCount"])<=0:continue
      xs=[]
      for x in r["xrefs"]:
        if not any(z["accessor"]==r["accessor"] and z["positionClass"]=="destination-or-rmw" for z in x["references"]):continue
        xs.append({"instruction":x["instruction"],"references":x["references"],
                   "before":x.get("contextBefore",[])[-16:],"after":x.get("contextAfter",[])[:16]})
      rows.append({"accessor":r["accessor"],"enumSymbol":r["enumSymbol"],"enumValue":r["enumValue"],
                   "totalOccurrences":r["totalOccurrences"],"fieldXrefCounts":r["fieldXrefCounts"],
                   "directDestinationOrRmwCount":r["directDestinationOrRmwCount"],"writes":xs})
    rows=sorted(rows,key=lambda x:(-int(x["totalOccurrences"]),x["accessor"]))
    if len(rows)!=9:raise SystemExit(f"expected 9 directly-written providers, got {len(rows)}")
    doc={"format":FORMAT,"authority":"exact reduction of SHA-classified current-client direct float4 slot writes",
      "client":d["client"],"source":{"path":str(a.source),"sha256":sha(a.source)},
      "summary":{"providerCount":len(rows),"occurrenceCount":sum(int(x["totalOccurrences"]) for x in rows),
                 "providers":[{"accessor":x["accessor"],"enumValue":x["enumValue"],"totalOccurrences":x["totalOccurrences"],
                               "writeCount":len(x["writes"])} for x in rows]},
      "rows":rows,
      "proofBoundary":"Exact direct destination/RMW neighborhoods only. This compact proof does not by itself promote formulas, source variables, update timing, command ownership, or historical-retail equivalence."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
