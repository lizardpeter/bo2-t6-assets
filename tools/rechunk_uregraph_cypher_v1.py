#!/usr/bin/env python3
"""Rechunk existing graph-ready Cypher files into bounded transport-safe batches.

Does not change any semantic content. It only splits the rows arrays used by the
whole-image inventory into smaller idempotent Cypher transactions.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path

def split_rows(content:str):
    marker="WITH b,a,"
    p=content.find(marker)
    if p<0: raise ValueError("WITH b,a marker not found")
    start=p+len(marker)
    end=content.find(" AS rows\n",start)
    if end<0: raise ValueError("AS rows marker not found")
    arr=json.loads(content[start:end])
    return content[:start],arr,content[end:]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("src",type=Path)
    ap.add_argument("dst",type=Path)
    ap.add_argument("--functions",type=int,default=1000)
    ap.add_argument("--strings",type=int,default=1000)
    ap.add_argument("--calls",type=int,default=750)
    ap.add_argument("--default",type=int,default=500)
    a=ap.parse_args()
    a.dst.mkdir(parents=True,exist_ok=True)
    files=sorted(a.src.glob("*.cypher"))
    out=[]
    totals={}
    for f in files:
        prefix,rows,tail=split_rows(f.read_text(encoding="utf-8"))
        cat=f.name.split("_",1)[0]
        size={"functions":a.functions,"strings":a.strings,"calls":a.calls}.get(cat,a.default)
        totals[cat]=totals.get(cat,0)+len(rows)
        for i in range(0,len(rows),size):
            name=f"{f.stem}_part_{i//size:04d}.cypher"
            payload=json.dumps(rows[i:i+size],separators=(",",":"),ensure_ascii=False)
            (a.dst/name).write_text(prefix+payload+tail,encoding="utf-8")
            out.append({"category":cat,"source":f.name,"file":name,"rows":len(rows[i:i+size])})
    manifest={"format":"uregraph-transport-rechunk-v1","source":str(a.src),"files":out,"rowTotals":totals,
              "batchSizes":{"functions":a.functions,"strings":a.strings,"calls":a.calls,"default":a.default},
              "semanticChange":False}
    (a.dst.parent/"transport_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"files":len(out),"rowTotals":totals,"batchSizes":manifest["batchSizes"]},indent=2))
if __name__=="__main__": main()
