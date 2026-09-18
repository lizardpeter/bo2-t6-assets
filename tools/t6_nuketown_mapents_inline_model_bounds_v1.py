#!/usr/bin/env python3
"""Join exact Nuketown MapEnt *N model tokens to exact ClipMap submodel bounds.

This deliberately does not promote the *N -> cmodel[N] semantic rule. It closes
only the lexical token population and numeric bounds against the retail ClipMap.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

RX=re.compile(r"^\*([0-9]+)$")

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mapents",type=Path,required=True)
    ap.add_argument("--clipmap",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    m=json.loads(a.mapents.read_text()); c=json.loads(a.clipmap.read_text())
    if m.get("format")!="t6-mapents-model-animation-census-v1": raise SystemExit("mapents format drift")
    if c.get("format")!="t6-clipmap-normalized-proof-v1" or not c.get("allChecksPass"): raise SystemExit("clipmap proof drift")
    count=int(c["counts"]["numSubModels"])
    decoded=int(c["decoded"]["subModels"])
    if count!=decoded: raise SystemExit("clipmap submodel count/decoded mismatch")
    uses={}
    external=set()
    for e in m.get("relevantEntities",[]):
        name=e.get("model")
        if not name: continue
        mm=RX.fullmatch(name)
        if not mm:
            external.add(name); continue
        idx=int(mm.group(1))
        uses.setdefault(idx,[]).append(e["entityIndex"])
    ids=sorted(uses)
    rows=[{"token":f"*{i}","numericIndex":i,"entityIndices":sorted(set(uses[i])),"inClipMapSubmodelBounds":0<=i<count} for i in ids]
    out={
      "format":"t6-nuketown-mapents-inline-model-bounds-v1",
      "sources":{
        "mapents":{"path":str(a.mapents),"sha256":sha(a.mapents)},
        "clipmap":{"path":str(a.clipmap),"sha256":sha(a.clipmap),"expandedSha256":c["input"]["expandedSha256"]},
      },
      "summary":{
        "clipMapSubmodelCount":count,
        "uniqueInlineModelTokenCount":len(rows),
        "minimumInlineNumericIndex":ids[0] if ids else None,
        "maximumInlineNumericIndex":ids[-1] if ids else None,
        "outOfBoundsTokenCount":sum(not x["inClipMapSubmodelBounds"] for x in rows),
        "coversEveryNonzeroClipMapSubmodelIndex":ids==list(range(1,count)),
        "externalModelIdentityCount":len(external),
      },
      "rows":rows,
      "proofBoundary":"This proves the exact retail MapEnt lexical *<decimal> population and that every numeric value lies within the exact ClipMap numSubModels=184 range. It does not by itself prove the engine semantic rule that token *N addresses clipMap subModels[N]; that runtime/source semantic link remains a separate hard gate."
    }
    s=out["summary"]
    if count!=184 or len(rows)!=183 or ids!=list(range(1,184)) or s["outOfBoundsTokenCount"]!=0:
        raise SystemExit(f"unexpected inline/submodel census: {s}")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(s,indent=2,sort_keys=True))
if __name__=="__main__": main()
