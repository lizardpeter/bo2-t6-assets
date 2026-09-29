#!/usr/bin/env python3
"""Rechunk existing graph-ready Cypher files into bounded transport-safe batches.

Does not change semantic content. It splits the raw Cypher map rows inside the
whole-image inventory UNWIND arrays without attempting to parse those maps as JSON.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

def split_cypher_rows(content:str):
    marker="WITH b,a,"
    p=content.find(marker)
    if p<0: raise ValueError("WITH b,a marker not found")
    start=p+len(marker)
    end=content.find(" AS rows\n",start)
    if end<0: raise ValueError("AS rows marker not found")
    arr=content[start:end].strip()
    if not (arr.startswith("[") and arr.endswith("]")):
        raise ValueError("row payload is not a Cypher list")
    body=arr[1:-1]
    rows=[]
    row_start=0
    depth=0
    in_string=False
    escape=False
    for i,ch in enumerate(body):
        if in_string:
            if escape:
                escape=False
            elif ch=="\\":
                escape=True
            elif ch=='"':
                in_string=False
            continue
        if ch=='"':
            in_string=True
            continue
        if ch in "{[":
            depth+=1
        elif ch in "}]":
            depth-=1
            if depth<0: raise ValueError("negative nesting depth")
        elif ch=="," and depth==0:
            row=body[row_start:i].strip()
            if row: rows.append(row)
            row_start=i+1
    tail=body[row_start:].strip()
    if tail: rows.append(tail)
    if depth!=0 or in_string:
        raise ValueError("unterminated Cypher payload")
    return content[:start],rows,content[end:]

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
        prefix,rows,tail=split_cypher_rows(f.read_text(encoding="utf-8"))
        cat=f.name.split("_",1)[0]
        size={"functions":a.functions,"strings":a.strings,"calls":a.calls}.get(cat,a.default)
        totals[cat]=totals.get(cat,0)+len(rows)
        for i in range(0,len(rows),size):
            batch=rows[i:i+size]
            name=f"{f.stem}_part_{i//size:04d}.cypher"
            payload="["+ ",".join(batch) +"]"
            (a.dst/name).write_text(prefix+payload+tail,encoding="utf-8")
            out.append({"category":cat,"source":f.name,"file":name,"rows":len(batch)})
    manifest={"format":"uregraph-transport-rechunk-v2","source":str(a.src),"files":out,"rowTotals":totals,
              "batchSizes":{"functions":a.functions,"strings":a.strings,"calls":a.calls,"default":a.default},
              "semanticChange":False}
    (a.dst.parent/"transport_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"files":len(out),"rowTotals":totals,"batchSizes":manifest["batchSizes"]},indent=2))
if __name__=="__main__": main()
