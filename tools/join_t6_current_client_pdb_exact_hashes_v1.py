#!/usr/bin/env python3
"""Build a high-confidence current-client <-> MAP/PDB cross-build join plan.

Input 1: exact current-client Ghidra catalog TSV (entry + instruction byte SHA-256).
Input 2: server/PDB exact-hash export TSV generated from uregraph.

Exact byte-hash equality is emitted as an identity witness, not as an address/name merge.
"""
from __future__ import annotations
import argparse,csv,json
from collections import defaultdict
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--pdb-hashes",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    with a.catalog.open(encoding="utf-8",newline="") as f:
        cc=list(csv.DictReader(f,dialect="excel-tab"))
    with a.pdb_hashes.open(encoding="utf-8",newline="") as f:
        sv=list(csv.DictReader(f,dialect="excel-tab"))
    by=defaultdict(list)
    for r in sv:
        h=r["exact_bytes_sha256"].lower()
        if h: by[h].append(r)
    matches=[]
    ambiguous=0
    for c in cc:
        h=c["instruction_bytes_sha256"].lower()
        hits=by.get(h,[])
        if not hits: continue
        if len(hits)>1: ambiguous+=1
        for s in hits:
            matches.append({
              "current_client_va":"0x"+c["entry_va"].lower().removeprefix("0x"),
              "current_client_hash":h,
              "current_client_ghidra_name":c["name"],
              "server_variant_id":s["variant_id"],
              "server_family_id":s["family_id"],
              "server_symbol_name":s["symbol_name"],
              "server_object_name":s["object_name"],
              "server_address_start":s["exact_address_start"],
              "server_size_bytes":s["exact_size_bytes"],
              "server_hash_multiplicity":len(hits),
              "identity_basis":"exact-function-instruction-bytes-sha256-across-builds",
              "state":"accepted-exact-byte-identity-witness" if len(hits)==1 else "candidate-ambiguous-exact-byte-hash",
            })
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps({
      "format":"t6-current-client-pdb-exact-hash-join-v1",
      "current_client_catalog_functions":len(cc),
      "server_pdb_exact_hash_variants":len(sv),
      "match_rows":len(matches),
      "current_client_functions_with_match":len(set(x["current_client_va"] for x in matches)),
      "ambiguous_current_client_hashes":ambiguous,
      "matches":matches,
      "proof_boundary":"Exact instruction-byte hash equality is strong cross-build identity evidence. Duplicate hashes remain candidate/ambiguous and are not auto-merged. No address/name-only identity is admitted."
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print({"matches":len(matches),"current_client_functions":len(set(x["current_client_va"] for x in matches)),"ambiguous":ambiguous})
if __name__=="__main__": main()
