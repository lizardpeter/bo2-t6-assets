#!/usr/bin/env python3
import argparse,csv,glob,json,math,pathlib

EXCLUDES = [
    "smg/rmge01/decompile_batch_low_hanging_v1.jsonl",
    "smg/rmge01/decompile_batch2_v1.tsv",
    "smg/rmge01/decompile_batch3_v1.tsv",
    "smg/rmge01/decompile_batch4_v1.tsv",
    "smg/rmge01/decompile_batch5_v1.tsv",
    "smg/rmge01/decompile_batch6_v1.tsv",
]
FIELDS=["id","address","size","name","subsystem","expected_sha256"]

def read_tsv(path):
    with open(path,newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f,delimiter="\t"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out-dir",required=True)
    ap.add_argument("--shards",type=int,default=12)
    args=ap.parse_args()
    rows=[]
    seen=set()
    for path in sorted(glob.glob("smg/rmge01/inventory/exact_functions_*.tsv")):
        for r in read_tsv(path):
            if r["id"] in seen: raise SystemExit(f"duplicate inventory id {r['id']}")
            seen.add(r["id"]); rows.append(r)
    if len(rows)!=23345: raise SystemExit(f"expected 23345 inventory rows, got {len(rows)}")
    used=set()
    for path in EXCLUDES:
        if path.endswith(".jsonl"):
            for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
                if line.strip(): used.add(json.loads(line)["id"])
        else:
            used.update(r["id"] for r in read_tsv(path))
    remaining=[dict(r,size_num=int(r["size"])) for r in rows if r["id"] not in used]
    if len(used)!=7600: raise SystemExit(f"expected 7600 used ids through batch6, got {len(used)}")
    if len(remaining)!=15745: raise SystemExit(f"expected 15745 remaining ids, got {len(remaining)}")
    bins=[{"i":i,"rows":[],"bytes":0,"cost":0.0} for i in range(args.shards)]
    for r in sorted(remaining,key=lambda x:(-x["size_num"],int(x["address"],16))):
        b=min(bins,key=lambda x:(x["cost"],len(x["rows"]),x["i"]))
        b["rows"].append(r)
        b["bytes"]+=r["size_num"]
        b["cost"]+=r["size_num"]*math.log2(max(4,r["size_num"]))
    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    summary=[]
    for b in sorted(bins,key=lambda x:x["i"]):
        b["rows"].sort(key=lambda x:int(x["address"],16))
        p=out/f"decompile_wave1_{b['i']:02d}.tsv"
        with p.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=FIELDS,delimiter="\t",lineterminator="\n")
            w.writeheader()
            for r in b["rows"]: w.writerow({k:r[k] for k in FIELDS})
        summary.append({"shard":f"{b['i']:02d}","rows":len(b["rows"]),"bytes":b["bytes"],"min_size":min(r["size_num"] for r in b["rows"]),"max_size":max(r["size_num"] for r in b["rows"]),"estimated_cost":round(b["cost"])})
    (out/"wave1_summary.json").write_text(json.dumps({"inventory":len(rows),"used":len(used),"remaining":len(remaining),"shards":summary},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary))
if __name__=="__main__": main()
