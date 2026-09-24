#!/usr/bin/env python3
"""Deduplicate exact postFxControl0..3 backward value slices into formula candidates."""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path

FORMAT="t6-current-client-postfx-control0-3-slice-classes-v1"
SOURCE_FORMAT="t6-current-client-postfx-control0-3-backward-slices-v1"

def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c:raise SystemExit(m)
def norm_ins(x):
    return (x.get("mnemonic",""),x.get("opStr",""))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text());req(d.get("format")==SOURCE_FORMAT,"source format drift")
    groups={}
    total=0
    for f in d.get("functions",[]):
      for row in f.get("slices",[]):
        total+=1
        s=row["slice"]
        sig=json.dumps({
          "write":norm_ins(row["write"]),
          "instructions":[norm_ins(x) for x in s.get("instructions",[])],
          "memoryLeaves":s.get("memoryLeaves",[]),
          "neededAtBoundary":s.get("neededAtBoundary",[]),
        },sort_keys=True,separators=(",",":"))
        h=hashlib.sha256(sig.encode()).hexdigest()[:16]
        key=(f["startVa"],row["accessor"],row["field"],h)
        g=groups.setdefault(key,{
          "functionStartVa":f["startVa"],"accessor":row["accessor"],"enumValue":row["enumValue"],"field":row["field"],
          "classId":h,"count":0,"writeAddresses":[],"write":row["write"],
          "instructions":s.get("instructions",[]),"memoryLeaves":s.get("memoryLeaves",[]),
          "neededAtBoundary":s.get("neededAtBoundary",[]),"control":s.get("control",[])})
        g["count"]+=1;g["writeAddresses"].append(row["write"]["address"])
    classes=list(groups.values())
    classes.sort(key=lambda x:(x["accessor"],x["field"],x["functionStartVa"],x["classId"]))
    by=defaultdict(int)
    for g in classes:by[g["accessor"]]+=1
    out={"format":FORMAT,"authority":"exact deduplicated classes of mechanical backward slices",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "summary":{"sourceSliceCount":total,"uniqueSliceClassCount":len(classes),"classesByAccessor":dict(sorted(by.items()))},
      "classes":classes,
      "proofBoundary":"Deduplication only. Classes preserve exact value-producing instructions and memory leaves but do not by themselves prove branch reachability, source semantic names, historical-retail equivalence or provider closure."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
