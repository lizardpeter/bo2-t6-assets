#!/usr/bin/env python3
"""Compact postFxControl0..3 direct xrefs into function-level writer clusters."""
from __future__ import annotations
import argparse,json
from collections import defaultdict
from pathlib import Path

FMT_IN="t6-current-client-postfx-control0-5-xrefs-v1"
FMT_OUT="t6-current-client-postfx-control0-3-writer-clusters-v1"

def addr(x):return int(x["address"],16)
def derive_extent(h):
    seq=h["contextBefore"]+[h["instruction"]]+h["contextAfter"]
    center=len(h["contextBefore"])
    # nearest preceding INT3 is a boundary; function begins at next decoded insn.
    p=-1
    for i in range(center-1,-1,-1):
        if seq[i]["mnemonic"]=="int3":
            p=i;break
    q=len(seq)
    for i in range(center+1,len(seq)):
        if seq[i]["mnemonic"]=="int3":
            q=i;break
    body=seq[p+1:q]
    if not body:return None
    # trim duplicate/data-ish tail after first ret only when followed by INT3 boundary;
    # keep multi-return functions intact because q is the actual pad boundary.
    return body[0]["address"],f"0x{addr(body[-1])+len(bytes.fromhex(body[-1]['bytes'])):08x}",body

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--xrefs",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.xrefs.read_text())
    if d.get("format")!=FMT_IN:raise SystemExit(f"input format drift {d.get('format')}")
    clusters={}
    unresolved=[]
    for r in d["rows"]:
        if r["accessor"] not in {f"postFxControl{i}" for i in range(4)}:continue
        for h in r["xrefs"]:
            ext=derive_extent(h)
            if ext is None:
                unresolved.append({"accessor":r["accessor"],"instruction":h["instruction"]});continue
            start,end,body=ext;k=(start,end)
            c=clusters.setdefault(k,{"startVa":start,"endVaExclusive":end,"instructions":body,"writers":[]})
            c["writers"].append({"accessor":r["accessor"],"enumValue":r["enumValue"],"instruction":h["instruction"],
                "references":[x for x in h["references"] if x["accessor"]==r["accessor"]]})
    rows=[]
    for k,c in sorted(clusters.items(),key=lambda kv:int(kv[0][0],16)):
        by=defaultdict(lambda:{"instructionCount":0,"fields":defaultdict(int),"destinationOrRmwReferenceCount":0})
        for w in c["writers"]:
            x=by[w["accessor"]];x["instructionCount"]+=1
            for ref in w["references"]:
                x["fields"][ref["field"]]+=1
                if ref["positionClass"]=="destination-or-rmw":x["destinationOrRmwReferenceCount"]+=1
        c["accessors"]={name:{"instructionCount":v["instructionCount"],"fields":dict(sorted(v["fields"].items())),
                               "destinationOrRmwReferenceCount":v["destinationOrRmwReferenceCount"]} for name,v in sorted(by.items())}
        c["returnCount"]=sum(i["mnemonic"]=="ret" for i in c["instructions"])
        rows.append(c)
    acc_summary={}
    for acc in [f"postFxControl{i}" for i in range(4)]:
        rr=[c for c in rows if acc in c["accessors"]]
        acc_summary[acc]={"functionClusterCount":len(rr),"clusters":[c["startVa"] for c in rr],
                          "clustersWritingAllFourValuesAndVersion":sum(
                            set(c["accessors"][acc]["fields"])=={"value[0]","value[1]","value[2]","value[3]","version"} for c in rr)}
    doc={"format":FMT_OUT,"authority":"exact focused postFx slot xrefs compacted only by local INT3 function boundaries",
         "source":{"path":str(a.xrefs),"format":d["format"]},
         "summary":{"functionClusterCount":len(rows),"unboundedXrefCount":len(unresolved),"accessors":acc_summary},
         "functions":rows,"unboundedXrefs":unresolved,
         "proofBoundary":"Function clustering only. INT3 pads are used as exact local code-boundary evidence where present. No function semantic name, input ownership, formula, producer cadence, or historical-retail equivalence is promoted. Dedicated semantics projectors must validate exact lanes/source dataflow before provider closure."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
