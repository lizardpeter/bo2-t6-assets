#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

FIELDS=["id","address","size","name","subsystem","expected_sha256"]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out-dir",required=True)
    ap.add_argument("--shards",type=int,default=12)
    args=ap.parse_args()
    rows=[]
    for b in [2,3,4,5,6]:
        p=Path(f"smg/rmge01/decompile_batch{b}_v1.tsv")
        if not p.exists():
            raise SystemExit(f"missing {p}")
        with p.open(newline="",encoding="utf-8") as f:
            rows.extend(csv.DictReader(f,delimiter="\t"))
    if len(rows)!=7440:
        raise SystemExit(f"expected 7440 prior-batch rows, got {len(rows)}")
    ids=[r["id"] for r in rows]
    if len(set(ids))!=len(ids):
        raise SystemExit("duplicate IDs across batches 2-6")
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    shards=[[] for _ in range(args.shards)]
    for i,r in enumerate(rows):
        shards[i % args.shards].append(r)
    for i,shard in enumerate(shards):
        p=out/f"prior_force_{i:02d}.tsv"
        with p.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=FIELDS,delimiter="\t",lineterminator="\n")
            w.writeheader(); w.writerows(shard)
    print({"rows":len(rows),"shards":args.shards,"counts":[len(s) for s in shards]})

if __name__=="__main__":
    main()
