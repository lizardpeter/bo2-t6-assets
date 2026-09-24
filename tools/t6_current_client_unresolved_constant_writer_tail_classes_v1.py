#!/usr/bin/env python3
"""Deduplicate unresolved absolute-writer source tails into compact classes."""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path

FORMAT="t6-current-client-unresolved-constant-writer-tail-classes-v1"
SOURCE_FORMAT="t6-current-client-unresolved-constant-absolute-writers-v1"
TAIL=8

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c: raise SystemExit(m)
def sig(row):
    ins=row.get("contextBefore",[])[-TAIL:]+[row["instruction"]]
    return tuple((x.get("bytes"),x.get("mnemonic"),x.get("opStr")) for x in ins)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    d=json.loads(a.source.read_text())
    req(d.get("format")==SOURCE_FORMAT,"source format drift")
    groups=defaultdict(list)
    for w in d.get("writes",[]):
        groups[(w["accessor"],w["field"],w["functionStartVa"],sig(w))].append(w)
    classes=defaultdict(list)
    for (acc,field,fn,_),rows in groups.items():
        rep=rows[0]
        classes[acc].append({
          "field":field,
          "functionStartVa":fn,
          "occurrenceCount":len(rows),
          "writeAddresses":[r["instruction"]["address"] for r in rows],
          "tail":rep.get("contextBefore",[])[-TAIL:],
          "write":rep["instruction"],
          "after":rep.get("contextAfter",[])[:2],
        })
    out_acc={}
    for acc,rows in sorted(classes.items()):
        rows.sort(key=lambda r:(r["functionStartVa"],r["field"],r["write"]["address"]))
        source=d["summary"][acc]
        out_acc[acc]={
          "enumValue":source["enumValue"],
          "writeCount":source["absoluteDestinationWriteCount"],
          "writerFunctionCount":source["writerFunctionCount"],
          "writerFunctions":source["writerFunctions"],
          "fields":source["fields"],
          "tailClassCount":len(rows),
          "tailClasses":rows,
        }
        req(sum(r["occurrenceCount"] for r in rows)==source["absoluteDestinationWriteCount"],f"{acc}: class denominator drift")
    out={
      "format":FORMAT,
      "authority":"denominator-preserving deduplication of exact absolute-writer source tails",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "summary":{acc:{
        "enumValue":v["enumValue"],"writeCount":v["writeCount"],
        "writerFunctionCount":v["writerFunctionCount"],"tailClassCount":v["tailClassCount"],
        "fields":v["fields"],
      } for acc,v in out_acc.items()},
      "accessors":out_acc,
      "proofBoundary":"Deduplication only. Every exact absolute write remains represented by a class count; source formulas, branch reachability and provider semantics are not promoted."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
