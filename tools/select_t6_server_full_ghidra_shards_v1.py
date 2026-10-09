#!/usr/bin/env python3
"""Every original PC Server executable Ghidra function -> 8 stable work shards.

Use Ghidra's whole-program function enumeration rather than limited prior
reconstruction claims. Full analysis is PDB-backed; this selection retains the
Ghidra function VA as build-scoped occurrence ID even without a canonical ID.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def plan(index: Path, out: Path, shards: int = 8, min_functions: int = 10000):
    if shards < 1 or shards > 256:
        raise ValueError("bad shards")
    with index.open(encoding="utf-8", newline="") as f:
        source = list(csv.DictReader(f, delimiter="\t"))
    executable = {}
    for row in source:
        if row.get("is_executable", "").casefold() != "true":
            continue
        va = row["analysis_va"].lower().removeprefix("0x").zfill(8)
        if not re.fullmatch(r"[0-9a-f]{8}", va):
            raise ValueError("bad original VA " + repr(row["analysis_va"]))
        if va in executable:
            raise ValueError("duplicate original Ghidra function 0x" + va)
        executable[va] = row
    if len(executable) < min_functions:
        raise ValueError(
            f"only {len(executable)} executable Ghidra functions; "
            f"expected >= {min_functions} from full original image"
        )
    out.mkdir(parents=True, exist_ok=True)
    groups = [[] for _ in range(shards)]
    for ordinal, (va, row) in enumerate(sorted(executable.items())):
        groups[ordinal % shards].append([
            "urn:ure:t6:occ:function:pc-server:" + va,
            "0x" + va, "full-original-pdb-backed", "",
        ])
    details = []
    for idx, group in enumerate(groups):
        name = f"shard-{idx:02d}.tsv"
        file = out / name
        with file.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(["function_id", "requested_va", "tier", "reserved"])
            w.writerows(group)
        details.append({
            "selection": name, "executable_functions": len(group),
            "selection_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        })
    result = {
        "schema": "t6-pc-server-full-original-image-ghidra-v1",
        "executable_functions": len(executable),
        "total_ghidra_functions_all_sections": len(source),
        "shards": details,
        "source": "Ghidra FunctionManager on exact SHA256-pinned original CoDMPServer_PC.exe with PDB",
        "compiled_reconstruction_accepted": 0,
        "scope": "Ghidra decompiler evidence for every discovered executable function, including vendor/runtime code. Missing functions not recognized by Ghidra must be audited separately.",
    }
    (out / "summary.json").write_text(json.dumps(result, indent=2)+"\n")
    assert sum(x["executable_functions"] for x in details) == len(executable)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--shards", type=int, default=8)
    p.add_argument("--min-functions", type=int, default=10000)
    args = p.parse_args()
    print(json.dumps(plan(args.index, args.output, args.shards, args.min_functions),indent=2))


if __name__ == "__main__":
    main()
