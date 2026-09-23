#!/usr/bin/env python3
"""Project the exact current-client gameTime write cluster from the generic slot census."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SRC_FMT="t6-current-client-special-constant-direct-slot-xrefs-v1"
FORMAT="t6-current-client-gametime-write-cluster-v1"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text())
    if d.get("format")!=SRC_FMT:raise SystemExit("source format drift")
    rows=[x for x in d["rows"] if x["accessor"]=="gameTime"]
    if len(rows)!=1:raise SystemExit(f"gameTime rows={len(rows)}")
    r=rows[0]
    if r["enumValue"]!=25 or r["directXrefInstructionCount"]!=5 or r["directDestinationOrRmwCount"]!=5:
        raise SystemExit(f"gameTime census drift {r}")
    expected={"value[0]":1,"value[1]":1,"value[2]":1,"value[3]":1,"version":1}
    if r["fieldXrefCounts"]!=expected:raise SystemExit(f"field census drift {r['fieldXrefCounts']}")
    # Keep only unique decoded instruction/context rows for this exact provider.
    xs=sorted(r["xrefs"],key=lambda x:int(x["instruction"]["address"],16))
    addrs=[int(x["instruction"]["address"],16) for x in xs]
    doc={
      "format":FORMAT,
      "authority":"exact projection of SHA-classified current-client direct slot xref census",
      "client":d["client"],
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "runtimeInput":{"accessor":"gameTime","enumValue":25,"enumSymbol":r["enumSymbol"],"totalOccurrences":r["totalOccurrences"],
                      "valueVas":r["valueVas"],"versionVa":r["versionVa"]},
      "summary":{"xrefInstructionCount":len(xs),"minimumXrefVa":f"0x{min(addrs):08x}","maximumXrefVa":f"0x{max(addrs):08x}",
                 "xrefSpanBytes":max(addrs)-min(addrs),"allFiveSlotsDirect":True},
      "xrefs":xs,
      "proofBoundary":"Exact current-client slot-write cluster only. This does not yet assign the containing function, source scalar, trigonometric/fraction formula, update timing, or historical-retail equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in xs:print(x["instruction"]["address"],x["instruction"]["mnemonic"],x["instruction"]["opStr"],x["references"])
if __name__=="__main__":main()
