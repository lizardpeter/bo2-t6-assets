#!/usr/bin/env python3
"""Compact T6 current-client Ghidra CALL references into source->target edges."""
from __future__ import annotations
import argparse,csv,json
from collections import defaultdict
from pathlib import Path

def norm(v:str)->str:
    v=(v or "").strip().lower().removeprefix("0x")
    return ("0x"+v.zfill(8)) if v else ""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("raw",type=Path)
    ap.add_argument("--out-dir",type=Path,required=True)
    a=ap.parse_args()
    with a.raw.open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f,dialect="excel-tab"))

    edges=defaultdict(lambda:{"callsites":[],"source_name":"","target_name":"","target_is_thunk":False})
    stats=defaultdict(lambda:{"total_direct_calls":0,"exact_target_calls":0,"unique_targets":set()})
    exact_rows=0
    for r in rows:
        s=norm(r["source_entry"])
        st=stats[s]
        st["total_direct_calls"]+=1
        if (r.get("target_exact_function") or "").lower()!="true":
            continue
        exact_rows+=1
        t=norm(r["target_entry"])
        st["exact_target_calls"]+=1
        st["unique_targets"].add(t)
        e=edges[(s,t)]
        e["callsites"].append(norm(r["callsite"]))
        e["source_name"]=r.get("source_name") or ""
        e["target_name"]=r.get("target_name") or ""
        e["target_is_thunk"]=(r.get("target_is_thunk") or "").lower()=="true"

    a.out_dir.mkdir(parents=True,exist_ok=True)
    with (a.out_dir/"edges.tsv").open("w",encoding="utf-8",newline="") as f:
        fields=["source_entry","target_entry","callsite_count","callsites","source_name","target_name","target_is_thunk"]
        w=csv.DictWriter(f,fieldnames=fields,dialect="excel-tab",lineterminator="\n"); w.writeheader()
        for (s,t),e in sorted(edges.items()):
            w.writerow({"source_entry":s,"target_entry":t,"callsite_count":len(e["callsites"]),
                        "callsites":";".join(sorted(e["callsites"])),"source_name":e["source_name"],
                        "target_name":e["target_name"],"target_is_thunk":str(e["target_is_thunk"]).lower()})
    with (a.out_dir/"function_stats.tsv").open("w",encoding="utf-8",newline="") as f:
        fields=["source_entry","total_direct_calls","exact_target_calls","unique_exact_targets"]
        w=csv.DictWriter(f,fieldnames=fields,dialect="excel-tab",lineterminator="\n"); w.writeheader()
        for s,st in sorted(stats.items()):
            w.writerow({"source_entry":s,"total_direct_calls":st["total_direct_calls"],
                        "exact_target_calls":st["exact_target_calls"],
                        "unique_exact_targets":len(st["unique_targets"])})
    summary={
      "format":"t6-current-client-ghidra-callgraph-compact-v1",
      "raw_call_reference_rows":len(rows),
      "exact_target_call_rows":exact_rows,
      "unresolved_or_nonentry_call_rows":len(rows)-exact_rows,
      "unique_function_edges":len(edges),
      "source_functions_with_call_refs":len(stats),
      "source_functions_with_exact_targets":sum(bool(x["unique_targets"]) for x in stats.values()),
      "unique_target_functions":len({t for _,t in edges}),
      "client_sha256":"770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf",
      "ghidra_version":"12.1.3",
      "proof_boundary":"Generated current-client Ghidra direct-call evidence. An edge means an exact CALL reference to a Ghidra-recognized function entry; no cross-build semantic identity is inferred."
    }
    (a.out_dir/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__": main()
