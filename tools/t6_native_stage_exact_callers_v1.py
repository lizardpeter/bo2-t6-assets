#!/usr/bin/env python3
"""Recover original Ghidra bodies of immediate callers of key T6 source units.

Targets are grounded in exact current-client CALL edges and verified selection
hashes. They remain unreviewed pseudocode, NOT admitted native C++.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

import t6_native_decompile_availability_v1 as archive_tools

EXPECTED = {
    "0x0055f850": "7b177bc97079404ebf76be35b47400e52319a2a57ade22762dd3e68576fd398d",
    "0x009afee0": "59d07768f1ea7fe9069327db0fa009eba61b2843c3544442273619f301b2839c",
    "0x00467930": "64d55a29e3259bfbbc497fea233578dd9f0bae2bd824dd6a06fb7633bc70eb60",
}
TARGET_REASON = {
    "0x0055f850": "direct caller of 0x005F2550 native 350-entry glass allocator constructor",
    "0x009afee0": "direct caller of 0x009A7D00 and 0x009A7D60 stream-state units",
    "0x00467930": "direct caller of 0x00421740 Actor_ClearMoveHistory",
}

def prepare(root: Path) -> dict:
    hits = {}
    for base,parts in archive_tools.archive_groups(root):
        selection = base / "selection.tsv"
        if not selection.exists(): selection=base/"low_hanging.tsv"
        with selection.open("r",encoding="utf-8",newline="") as handle:
            selected=list(csv.DictReader(handle,dialect="excel-tab"))
        results_file=base/"results.tsv"
        if results_file.is_file():
            with results_file.open("r",encoding="utf-8",newline="") as handle:
                results={r["requested_va"].lower():r for r in csv.DictReader(handle,dialect="excel-tab")}
        else: results=None
        for row in selected:
            va=row["requested_va"].lower()
            if va not in EXPECTED: continue
            assert row["instruction_bytes_sha256"] == EXPECTED[va], ("exact function hash mismatch",va)
            assert va not in hits, ("duplicate exported function",va)
            if results:
                found=results.get(va)
                assert found is not None
                assert found["found_exact"]=="true"
                assert found["decompile_completed"]=="true"
            hits[va]={
                "current_client_va":va,
                "instruction_sha256":EXPECTED[va],
                "callgraph_role":TARGET_REASON[va],
                "archive_parts":[str(p.relative_to(root)) for p in parts],
                "generated_file_name":va[2:]+".c",
                "decompile_completed":True,
                "source_status":"generated-unreviewed-ghidra-C",
                "native_admitted":False
            }
    assert set(hits)==set(EXPECTED), ("missing archive source selection", sorted(set(EXPECTED)-set(hits)))
    return {"schema":"t6-exact-callers-staging-selection-v1", "entries":list(hits.values())}

def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    report=prepare(args.repo_root)
    manifest=archive_tools.stage(args.repo_root, report, args.out_dir)
    assert manifest["extracted_unreviewed_function_bodies"]==len(EXPECTED)
    assert not manifest["index_claims_missing_tar_member"],manifest
    print(json.dumps({
        "targets":sorted(EXPECTED),
        "extracted_unreviewed_function_bodies":manifest["extracted_unreviewed_function_bodies"],
        "missing":manifest["index_claims_missing_tar_member"],
        "source_promotion":False
    },sort_keys=True))

if __name__=="__main__":main()
