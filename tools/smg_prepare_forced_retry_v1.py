#!/usr/bin/env python3
import argparse
import csv
import glob
import json
from pathlib import Path

FIELDS = ["id", "address", "size", "name", "subsystem", "expected_sha256"]

def write_tsv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--shards", type=int, default=8)
    ap.add_argument("--inventory-glob", default="smg/rmge01/inventory/exact_functions_*.tsv")
    ap.add_argument("--batch1-jsonl", default="smg/rmge01/decompile_batch_low_hanging_v1.jsonl")
    args = ap.parse_args()

    if args.shards < 1:
        raise SystemExit("--shards must be >= 1")

    rows = []
    for path in sorted(glob.glob(args.inventory_glob)):
        with open(path, newline="", encoding="utf-8") as f:
            rows.extend(csv.DictReader(f, delimiter="\t"))

    if len(rows) != 23345:
        raise SystemExit(f"expected 23345 exact inventory rows, got {len(rows)}")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("exact inventory contains duplicate ids")

    batch1 = []
    with open(args.batch1_jsonl, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                batch1.append({
                    "id": r["id"],
                    "address": r["address"],
                    "size": str(r["size"]),
                    "name": r.get("name") or "",
                    "subsystem": r.get("subsystem") or "",
                    "expected_sha256": r["expected_sha256"],
                })
    if len(batch1) != 160:
        raise SystemExit(f"expected 160 batch1 rows, got {len(batch1)}")
    batch1_ids = {r["id"] for r in batch1}

    by_id = {r["id"]: r for r in rows}
    missing_batch1 = sorted(batch1_ids - set(by_id))
    if missing_batch1:
        raise SystemExit(f"batch1 ids missing from exact inventory: {missing_batch1[:5]}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_tsv(out / "batch1_force_all.tsv", [by_id[r["id"]] for r in batch1])

    remaining = [r for r in rows if r["id"] not in batch1_ids]
    shards = [[] for _ in range(args.shards)]
    for i, r in enumerate(remaining):
        shards[i % args.shards].append(r)

    for i, shard in enumerate(shards):
        write_tsv(out / f"missing_scan_{i:02d}.tsv", shard)

    summary = {
        "exact_inventory": len(rows),
        "batch1_force_all": len(batch1_ids),
        "missing_scan_universe": len(remaining),
        "shards": args.shards,
        "shard_counts": [len(s) for s in shards],
        "policy": "Exact RMGE01 inventory only; batch1 force-all plus missing-entry scan for all other exact variants.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))

if __name__ == "__main__":
    main()
