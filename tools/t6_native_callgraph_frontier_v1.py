#!/usr/bin/env python3
"""Exact-build direct-call frontier for source-admitted T6 functions.

Never interpret missing CALL references as lack of runtime use: dynamic,
pointer-table and virtual dispatch are outside this Ghidra direct-call census.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

CALLS = Path("proof/current_client/ghidra_callgraph_compact_v1/edges.tsv.zst")
SUMMARY = Path("proof/current_client/ghidra_callgraph_compact_v1/summary.json")
JOIN = Path("proof/current_client/pdb_exact_hash_join_v1_strict/join.json")
MANIFEST = Path("reconstruction/native/manifest.json")
EXPECTED_BIN = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"


def normalize(v: str) -> str:
    s = v.strip().lower().removeprefix("0x")
    assert len(s) == 8 and all(c in "0123456789abcdef" for c in s), v
    return "0x" + s


def audit(root: Path) -> dict:
    path = root / CALLS
    sha_path = path.with_suffix(path.suffix + ".sha256")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    recorded = sha_path.read_text(encoding="utf-8").split()[0].lower()
    assert actual == recorded, "exact callgraph archive SHA-256 mismatch"
    summary = json.loads((root / SUMMARY).read_text(encoding="utf-8"))
    assert summary["client_sha256"] == EXPECTED_BIN
    join = json.loads((root / JOIN).read_text(encoding="utf-8"))
    pdb = {
        normalize(x["current_client_va"]): {
            "server_symbol_name": x["server_symbol_name"],
            "server_object_name": x["server_object_name"],
            "identity_basis": x["state"],
        }
        for x in join["matches"]
        if x["state"] == "accepted-exact-byte-identity-witness"
    }
    roots = {
        normalize(f["entry_va"]): f for f in
        json.loads((root / MANIFEST).read_text(encoding="utf-8"))["functions"]
    }

    decoded = subprocess.run(
        ["zstd", "-dc", str(path)], capture_output=True, check=True
    ).stdout.decode("utf-8")
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    all_edges = 0
    for line in csv.DictReader(io.StringIO(decoded), dialect="excel-tab"):
        src, dst = normalize(line["source_entry"]), normalize(line["target_entry"])
        all_edges += 1
        count = int(line["callsite_count"])
        assert count >= 1
        edge = {
            "source_entry": src,
            "target_entry": dst,
            "callsite_count": count,
            "callsites": line["callsites"].split(";"),
            "source_ghidra_name": line["source_name"],
            "target_ghidra_name": line["target_name"],
        }
        assert len(edge["callsites"]) == count
        if dst in roots:
            edge["source_pdb_match"] = pdb.get(src)
            incoming[dst].append(edge)
        if src in roots:
            edge["target_pdb_match"] = pdb.get(dst)
            outgoing[src].append(edge)
    assert all_edges == summary["unique_function_edges"], (all_edges, summary)
    table = []
    for va, candidate in sorted(roots.items()):
        callers = sorted(incoming[va], key=lambda x:(-x["callsite_count"],x["source_entry"]))
        callees = sorted(outgoing[va], key=lambda x:(-x["callsite_count"],x["target_entry"]))
        table.append({
            "entry_va": va,
            "candidate_symbol": candidate["symbol"],
            "original_pdb_identity": pdb.get(va),
            "incoming_direct_function_count": len(callers),
            "outgoing_direct_function_count": len(callees),
            "incoming_direct_callsites": sum(x["callsite_count"] for x in callers),
            "outgoing_direct_callsites": sum(x["callsite_count"] for x in callees),
            "incoming_edges": callers,
            "outgoing_edges": callees,
        })
    result = {
        "schema": "t6-native-exact-callgraph-frontier-v1",
        "source_binary_sha256": EXPECTED_BIN,
        "callgraph_archive_sha256": actual,
        "source": str(CALLS),
        "proof_boundary": (
            "Exact Ghidra direct CALL reference evidence only. Virtual/indirect/address-taken "
            "references are not inventoried; neither symbol matching nor direct CALL "
            "reachability proves correct source-level behavior."
        ),
        "exact_edges_checked": all_edges,
        "roots_count": len(roots),
        "roots_with_incoming_direct_calls": sum(bool(x["incoming_edges"]) for x in table),
        "roots_with_outgoing_direct_calls": sum(bool(x["outgoing_edges"]) for x in table),
        "roots": table
    }
    return result


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    result=audit(args.repo_root)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="roots"},sort_keys=True))
    for r in result["roots"]:
        print(f"{r['entry_va']}: incoming={r['incoming_direct_function_count']}, outgoing={r['outgoing_direct_function_count']}")

if __name__=="__main__":
    main()
