#!/usr/bin/env python3
"""Compact unresolved retained-special absolute writer proof for semantic reduction.

Consumes the exact absolute-writer census and keeps the full denominator while
shrinking each row to a bounded source/value window. No provider semantics are
promoted here.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path

FORMAT="t6-current-client-unresolved-constant-absolute-writers-compact-v1"
SOURCE_FORMAT="t6-current-client-unresolved-constant-absolute-writers-v1"
TARGETS={
 37:"shadowmapSwitchPartition",
 38:"sunShadowmapPixelSize",
 60:"spotShadowmapPixelAdjust",
 61:"dlightSpotShadowmapPixelAdjust",
 107:"postFxControl0",
 108:"postFxControl1",
 109:"postFxControl2",
 110:"postFxControl3",
 111:"postFxControl4",
 112:"postFxControl5",
}
PRE=18
POST=10

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c: raise SystemExit(m)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    d=json.loads(a.source.read_text())
    req(d.get("format")==SOURCE_FORMAT,"source format drift")
    by=defaultdict(list)
    for w in d.get("writes",[]):
        acc=w["accessor"]
        req(acc in TARGETS.values(),f"unexpected accessor {acc}")
        by[acc].append({
          "field":w["field"],"targetVa":w["targetVa"],
          "functionStartVa":w["functionStartVa"],
          "functionEndVaExclusive":w["functionEndVaExclusive"],
          "instruction":w["instruction"],
          "contextBefore":w.get("contextBefore",[])[-PRE:],
          "contextAfter":w.get("contextAfter",[])[:POST],
        })
    accessors={}
    for enum,acc in TARGETS.items():
        rows=by.get(acc,[])
        functions=sorted({r["functionStartVa"] for r in rows})
        fields=sorted({r["field"] for r in rows})
        accessors[acc]={
          "enumValue":enum,
          "writeCount":len(rows),
          "writerFunctionCount":len(functions),
          "writerFunctions":functions,
          "fields":fields,
          "writes":rows,
        }
        src=d.get("summary",{}).get(acc,{})
        req(len(rows)==int(src.get("absoluteDestinationWriteCount",-1)),f"{acc}: write denominator drift")
        req(functions==sorted(src.get("writerFunctions",[])),f"{acc}: function denominator drift")
        req(fields==sorted(src.get("fields",[])),f"{acc}: field denominator drift")
    out={
      "format":FORMAT,
      "authority":"lossless denominator-preserving compact projection of exact absolute destination writer census",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "summary":{acc:{
        "enumValue":v["enumValue"],"writeCount":v["writeCount"],
        "writerFunctionCount":v["writerFunctionCount"],
        "writerFunctions":v["writerFunctions"],"fields":v["fields"],
      } for acc,v in accessors.items()},
      "accessors":accessors,
      "proofBoundary":"Projection only. Absolute destination identity and the complete writer denominator are retained, but source formulas, branch reachability, semantic names, historical-retail equivalence and framebuffer effects remain unpromoted."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))

if __name__=="__main__":main()
