#!/usr/bin/env python3
import argparse, csv, json
from pathlib import Path

def read_tsv(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--root", default=".")
    args=ap.parse_args()
    if args.batch < 2 or args.count < 1:
        raise SystemExit("invalid batch/count")
    root=Path(args.root)
    base=root/"smg"/"rmge01"
    inv=[]
    for p in sorted((base/"inventory").glob("exact_functions_*.tsv")):
        inv.extend(read_tsv(p))
    if not inv:
        raise SystemExit("no exact RMGE01 inventory found")
    ids=[r["id"] for r in inv]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate IDs in exact inventory")
    used=set()
    low=base/"decompile_batch_low_hanging_v1.jsonl"
    if low.exists():
        for line in low.read_text(encoding="utf-8").splitlines():
            if line.strip():
                used.add(json.loads(line)["id"])
    for n in range(2,args.batch):
        for r in read_tsv(base/f"decompile_batch{n}_v1.tsv"):
            used.add(r["id"])
    fresh=[r for r in inv if r["id"] not in used]
    fresh.sort(key=lambda r:(int(r["size"]),int(r["address"],16),r["id"]))
    pick=fresh[:args.count]
    if len(pick) != args.count:
        raise SystemExit(f"requested {args.count}, only {len(pick)} fresh functions remain")
    out=base/f"decompile_batch{args.batch}_v1.tsv"
    fields=["id","address","size","name","subsystem","expected_sha256"]
    with out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
        w.writeheader()
        for r in pick:
            w.writerow({k:r.get(k,"") for k in fields})
    if len({r["id"] for r in pick}) != len(pick):
        raise SystemExit("duplicate selected IDs")
    if any(not r.get("expected_sha256") for r in pick):
        raise SystemExit("missing expected SHA-256")
    print(json.dumps({
        "batch":args.batch,"selected":len(pick),"used_before":len(used),
        "remaining_after":len(fresh)-len(pick),
        "min_size":int(pick[0]["size"]),"max_size":int(pick[-1]["size"]),
        "first":pick[0]["address"],"last":pick[-1]["address"],
        "output":str(out)
    },sort_keys=True))

if __name__=="__main__":
    main()
