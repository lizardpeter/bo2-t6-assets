#!/usr/bin/env python3
"""Rank exact current-client Ghidra functions for high-throughput decompilation.

Generated Ghidra output is evidence only. Selection never promotes semantic completion.
"""
from __future__ import annotations
import argparse,csv
from pathlib import Path

def tier(r):
    ins=int(r["instruction_count"])
    calls=int(r["call_reference_count"])
    body=int(r["body_address_count"])
    thunk=r["is_thunk"].lower()=="true"
    if thunk:
        return "thunk"
    if calls==0 and ins<=80 and body<=320:
        return "leaf"
    if calls<=3 and ins<=140 and body<=640:
        return "simple"
    if calls<=8 and ins<=240 and body<=1200:
        return "moderate"
    return "defer"

def score(r,t):
    ins=int(r["instruction_count"])
    calls=int(r["call_reference_count"])
    body=int(r["body_address_count"])
    rank={"thunk":0,"leaf":1,"simple":2,"moderate":3,"defer":9}[t]
    return (rank,calls,ins,body,int(r["entry_va"],16))

def load_excluded(paths):
    ids=set()
    for p in paths:
        with p.open(encoding="utf-8",newline="") as f:
            for r in csv.DictReader(f,dialect="excel-tab"):
                if r.get("function_id"): ids.add(r["function_id"])
    return ids

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("catalog",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--limit",type=int,default=3000)
    ap.add_argument("--skip",type=int,default=0)
    ap.add_argument("--include-thunks",action="store_true")
    ap.add_argument("--exclude",type=Path,action="append",default=[])
    ap.add_argument("--tier",action="append",choices=["thunk","leaf","simple","moderate","defer"],default=[])
    a=ap.parse_args()

    excluded=load_excluded(a.exclude)
    allowed=set(a.tier) if a.tier else {"leaf","simple","moderate"}
    if a.include_thunks: allowed.add("thunk")

    with a.catalog.open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f,dialect="excel-tab"))
    chosen=[]
    counts={}
    eligible_counts={}
    for r in rows:
        t=tier(r)
        counts[t]=counts.get(t,0)+1
        va="0x"+r["entry_va"].lower().removeprefix("0x")
        fid="urn:ure:t6:occ:function:current-client:"+r["entry_va"].lower().removeprefix("0x").zfill(8)
        if fid in excluded or t not in allowed: continue
        eligible_counts[t]=eligible_counts.get(t,0)+1
        chosen.append((score(r,t),t,r,fid,va))
    chosen.sort(key=lambda x:x[0])
    if a.skip>0: chosen=chosen[a.skip:]
    if a.limit>0: chosen=chosen[:a.limit]

    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("w",encoding="utf-8",newline="") as f:
        fields=["function_id","requested_va","tier","ghidra_name","instruction_count","call_reference_count","body_address_count","instruction_bytes_sha256"]
        w=csv.DictWriter(f,fieldnames=fields,dialect="excel-tab",lineterminator="\n")
        w.writeheader()
        for _,t,r,fid,va in chosen:
            w.writerow({
                "function_id":fid,
                "requested_va":va,
                "tier":t,
                "ghidra_name":r["name"],
                "instruction_count":r["instruction_count"],
                "call_reference_count":r["call_reference_count"],
                "body_address_count":r["body_address_count"],
                "instruction_bytes_sha256":r["instruction_bytes_sha256"],
            })
    print({"catalog":len(rows),"tier_counts":counts,"excluded":len(excluded),"eligible_counts":eligible_counts,"skip":a.skip,"selected":len(chosen),"output":str(a.out)})

if __name__=="__main__": main()
