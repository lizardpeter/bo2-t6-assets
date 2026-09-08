#!/usr/bin/env python3
"""Census exact alias-name targets in native OAT T6 SoundBank CSV output.

This tool consumes only post-loader OAT `soundbank/*.aliases.csv` files and checks the
`Name` column. It does not infer target ownership from Secondary references, hashes,
filenames, or historical aliases. An absence result is meaningful only when the caller
separately proves the native OAT SoundBank dump succeeded for the supplied FastFile.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def scan(root: Path, source_fastfile: str, targets: list[str]) -> dict:
    norm_targets = {t.lower(): t for t in targets}
    if len(norm_targets) != len(targets):
        raise ValueError("targets must be unique case-insensitively")
    csvs = sorted(root.glob("soundbank/*.aliases.csv"))
    matches = []
    total_rows = 0
    bank_rows = []
    for path in csvs:
        raw = path.read_bytes()
        reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
        if reader.fieldnames is None or "Name" not in reader.fieldnames:
            raise ValueError(f"{path}: native OAT alias CSV missing Name column")
        row_count = 0
        for row_index, row in enumerate(reader):
            row_count += 1; total_rows += 1
            name = row.get("Name", "")
            target = norm_targets.get(name.lower()) if name else None
            if target is not None:
                matches.append({
                    "target": target,
                    "nativeAliasName": name,
                    "bankName": path.name[:-len('.aliases.csv')],
                    "sourceFastFile": source_fastfile,
                    "csvRowIndex": row_index,
                    "csvSha256": hashlib.sha256(raw).hexdigest(),
                })
        bank_rows.append({
            "bankName": path.name[:-len('.aliases.csv')],
            "aliasRowCount": row_count,
            "csvSha256": hashlib.sha256(raw).hexdigest(),
        })
    return {
        "format": "t6-oat-alias-csv-target-census-v1",
        "sourceFastFile": source_fastfile,
        "targets": targets,
        "summary": {
            "nativeSoundBankCsvCount": len(csvs),
            "nativeAliasRowCount": total_rows,
            "targetMatchCount": len(matches),
        },
        "soundBanks": bank_rows,
        "matches": matches,
        "proofBoundary": (
            "Exact target-name census over native OAT T6 SoundBank alias CSV files for one successfully dumped FastFile. "
            "Only the post-loader CSV Name column is matched case-insensitively against explicit target strings. "
            "No Secondary reference, alias hash, historical lineage, or runtime behavior is used to manufacture an owner."
        ),
    }


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--source-fastfile",required=True)
    p.add_argument("--target",action="append",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=scan(a.root,a.source_fastfile,a.target)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(result['summary'],indent=2,sort_keys=True))
    for row in result['matches']:
        print('MATCH',row['target'],row['bankName'],row['sourceFastFile'],row['csvRowIndex'])
    return 0

if __name__=='__main__':
    raise SystemExit(main())
