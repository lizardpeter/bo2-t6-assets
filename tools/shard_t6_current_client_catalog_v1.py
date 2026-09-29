#!/usr/bin/env python3
"""Partition a T6 current-client Ghidra catalog into deterministic decompile shards.

Every cataloged function is eligible. Shards preserve a cheap-first order but include
the harder/defer tier as well. Output remains generated/unreviewed evidence.
"""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

def tier(r):
    ins=int(r["instruction_count"]); calls=int(r["call_reference_count"]); body=int(r["body_address_count"])
    if r["is_thunk"].lower()=="true": return "thunk"
    if calls==0 and ins<=80 and body<=320: return "leaf"
    if calls<=3 and ins<=140 and body<=640: return "simple"
    if calls<=8 and ins<=240 and body<=1200: return "moderate"
    return "complex"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("catalog",type=Path)
    ap.add_argument("--out-dir",type=Path,required=True)
    ap.add_argument("--shard-size",type=int,default=750)
    a=ap.parse_args()
    with a.catalog.open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f,dialect="excel-tab"))
    rank={"thunk":0,"leaf":1,"simple":2,"moderate":3,"complex":4}
    enriched=[]
    counts={}
    for r in rows:
        t=tier(r); counts[t]=counts.get(t,0)+1
        enriched.append((rank[t],int(r["call_reference_count"]),int(r["instruction_count"]),
                         int(r["body_address_count"]),int(r["entry_va"],16),t,r))
    enriched.sort(key=lambda x:x[:5])
    a.out_dir.mkdir(parents=True,exist_ok=True)
    fields=["function_id","requested_va","tier","ghidra_name","instruction_count","call_reference_count",
            "body_address_count","instruction_bytes_sha256"]
    shards=[]
    for si,start in enumerate(range(0,len(enriched),a.shard_size)):
        batch=enriched[start:start+a.shard_size]
        p=a.out_dir/f"shard_{si:03d}.tsv"
        with p.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields,dialect="excel-tab",lineterminator="\n"); w.writeheader()
            for *_,t,r in batch:
                va=r["entry_va"].lower().removeprefix("0x")
                w.writerow({
                    "function_id":"urn:ure:t6:occ:function:current-client:"+va.zfill(8),
                    "requested_va":"0x"+va,"tier":t,"ghidra_name":r["name"],
                    "instruction_count":r["instruction_count"],"call_reference_count":r["call_reference_count"],
                    "body_address_count":r["body_address_count"],"instruction_bytes_sha256":r["instruction_bytes_sha256"],
                })
        shards.append({"index":si,"file":p.name,"rows":len(batch),
                       "first_va":"0x"+batch[0][-1]["entry_va"].lower().removeprefix("0x"),
                       "last_va":"0x"+batch[-1][-1]["entry_va"].lower().removeprefix("0x")})
    m={"format":"t6-current-client-ghidra-decompile-shards-v1","catalog_functions":len(rows),
       "shard_size":a.shard_size,"shard_count":len(shards),"tier_counts":counts,"shards":shards,
       "proof_boundary":"Selection/partition only; no semantic completion is implied."}
    (a.out_dir/"manifest.json").write_text(json.dumps(m,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:m[k] for k in ("catalog_functions","shard_size","shard_count","tier_counts")},indent=2))
if __name__=="__main__": main()
