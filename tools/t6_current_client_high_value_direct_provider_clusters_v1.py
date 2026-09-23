#!/usr/bin/env python3
"""Project compact exact write clusters for scriptVector0 and renderTargetSize."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SRC_FMT="t6-current-client-special-constant-direct-write-clusters-v1"
FORMAT="t6-current-client-high-value-direct-provider-clusters-v1"
WANTED={"scriptVector0","renderTargetSize"}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text())
    if d.get("format")!=SRC_FMT:raise SystemExit("source format drift")
    rows=[x for x in d["rows"] if x["accessor"] in WANTED]
    if {x["accessor"] for x in rows}!=WANTED:raise SystemExit("wanted provider rows missing")
    for x in rows:
      if len(x["writes"])!=5:raise SystemExit(f"{x['accessor']}: expected five writes, got {len(x['writes'])}")
    doc={"format":FORMAT,"authority":"exact reduction of SHA-classified current-client direct write clusters",
      "client":d["client"],"source":{"path":str(a.source),"sha256":sha(a.source)},
      "summary":{"providerCount":2,"occurrenceCount":sum(int(x["totalOccurrences"]) for x in rows),
                 "providers":[{"accessor":x["accessor"],"enumValue":x["enumValue"],"totalOccurrences":x["totalOccurrences"]} for x in rows]},
      "rows":sorted(rows,key=lambda x:x["accessor"]),
      "proofBoundary":"Exact direct write neighborhoods only; formulas, source identities, update cadence and historical-retail equivalence remain unpromoted until dedicated projectors close them."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
