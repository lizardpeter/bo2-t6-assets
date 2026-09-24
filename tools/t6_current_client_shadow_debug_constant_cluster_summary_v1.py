#!/usr/bin/env python3
"""Compact the large shadow/debug constant xref proof into accessor-specific clusters."""
from __future__ import annotations
import argparse,json,hashlib
from collections import defaultdict
from pathlib import Path
FORMAT="t6-current-client-shadow-debug-constant-cluster-summary-v1"
SOURCE="t6-current-client-shadow-debug-constant-storage-xrefs-v1"
TARGETS=("shadowmapSwitchPartition","sunShadowmapPixelSize","debugPerformance")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 d=json.loads(a.source.read_text())
 if d.get("format")!=SOURCE:raise SystemExit("source format drift")
 out={}
 for name in TARGETS:
  by=defaultdict(list)
  for h in d.get("hits",[]):
   refs=[r for r in h.get("references",[]) if r.get("accessor")==name]
   if not refs:continue
   by[h["diagnosticFunctionStartVa"]].append((h,refs))
  rows=[]
  for fs,items in by.items():
   refs=[r for _,rs in items for r in rs]
   rows.append({
    "diagnosticFunctionStartVa":fs,
    "instructionAddresses":[h["instruction"]["address"] for h,_ in items],
    "valueDestinationLanes":sorted({r["lane"] for r in refs if r["kind"]=="valueLane" and r["role"]=="destination-or-rmw"}),
    "valueSourceLanes":sorted({r["lane"] for r in refs if r["kind"]=="valueLane" and r["role"]=="source-or-read"}),
    "versionDestinationCount":sum(r["kind"]=="version" and r["role"]=="destination-or-rmw" for r in refs),
    "versionSourceCount":sum(r["kind"]=="version" and r["role"]=="source-or-read" for r in refs),
    "baseRegisters":sorted({r.get("baseReg") for r in refs if r.get("baseReg")}),
    "hitCount":len(items),
   })
  rows.sort(key=lambda x:(-(len(x["valueDestinationLanes"]) + (4 if x["versionDestinationCount"] else 0)),-x["hitCount"],x["diagnosticFunctionStartVa"]))
  out[name]={"sourceSummary":d["summary"][name],"clusters":rows}
 doc={"format":FORMAT,"authority":"deterministic projection of exact current-client storage-xref proof",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "accessors":out,
      "proofBoundary":"Compaction only. No function is promoted as a provider by cluster co-occurrence; base provenance and exact source/value/version dataflow remain required."}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:{"clusterCount":len(v["clusters"]),"top":v["clusters"][:8]} for k,v in out.items()},indent=2,sort_keys=True))
if __name__=="__main__":main()
