#!/usr/bin/env python3
"""Conservative T6 current-client <-> server structural fingerprint matcher.

The server build is historical cross-build evidence, never retail truth.
This script calibrates exact structural fingerprints against accepted exact-byte
anchors before permitting them to nominate changed-byte candidates. It never
promotes semantic identity, names, prototypes, types, globals, or layouts.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

FORMAT = "t6-structural-cross-build-match-v1"

def norm_va(v: str) -> str:
    s = (v or "").strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    return f"0x{int(s,16):08x}" if s else ""

def load_tsv_dir(root: Path, prefix: str) -> list[dict[str,str]]:
    rows: list[dict[str,str]] = []
    for p in sorted(root.glob(f"{prefix}*.tsv")):
        with p.open(encoding="utf-8", newline="") as f:
            rows.extend(csv.DictReader(f, dialect="excel-tab"))
    if not rows:
        raise SystemExit(f"no TSV rows under {root} matching {prefix}*.tsv")
    return rows

def load_ranges(root: Path) -> tuple[dict[str,list[dict]], int]:
    """Load exact PDB-backed server ranges.

    Prefer the retained server_pdb_exact_hashes_v1 corpus. A legacy ranges_*.tsv
    layout is still accepted for reproducibility of older experiments.
    """
    by_va: dict[str,list[dict]] = defaultdict(list)
    total = 0
    paths = sorted(root.glob("server_pdb_exact_hashes_*.tsv"))
    if not paths:
        paths = sorted(root.glob("ranges_*.tsv"))
    for p in paths:
        with p.open(encoding="utf-8", newline="") as f:
            for raw in csv.DictReader(f, dialect="excel-tab"):
                server_va = raw.get("server_va") or raw.get("exact_address_start") or ""
                variant_id = raw.get("server_variant_id") or raw.get("variant_id") or ""
                if not server_va or not variant_id:
                    raise SystemExit(f"malformed exact server range row in {p}: {raw}")
                r = dict(raw)
                r["server_va"] = norm_va(server_va)
                r["server_variant_id"] = variant_id
                total += 1
                by_va[r["server_va"]].append(r)
    if not total:
        raise SystemExit(f"no exact PDB-backed server range rows under {root}")
    return by_va, total

def nonempty_hash(row: dict, field: str, count_field: str) -> str:
    try:
        n = int(row.get(count_field) or 0)
    except ValueError:
        n = 0
    return row.get(field,"") if n > 0 else ""

def scheme_key(name: str, r: dict) -> tuple:
    if name == "mnemonic_flow":
        return (
            r["instruction_count"], r["mnemonic_sha256"], r["flow_sha256"],
        )
    if name == "coarse_flow":
        return (
            r["instruction_count"], r["mnemonic_sha256"],
            r["operand_coarse_sha256"], r["flow_sha256"],
        )
    if name == "fine_flow":
        return (
            r["instruction_count"], r["mnemonic_sha256"],
            r["operand_fine_sha256"], r["flow_sha256"],
        )
    if name == "fine_profile":
        return (
            r["instruction_count"], r["body_address_count"],
            r["call_ref_count"], r["data_ref_count"], r["branch_count"],
            r["mnemonic_sha256"], r["operand_fine_sha256"], r["flow_sha256"],
            r["small_scalar_sha256"],
        )
    if name == "coarse_profile":
        return (
            r["instruction_count"], r["body_address_count"],
            r["call_ref_count"], r["data_ref_count"], r["branch_count"],
            r["mnemonic_sha256"], r["operand_coarse_sha256"], r["flow_sha256"],
            r["small_scalar_sha256"],
        )
    if name == "string_profile":
        sh = nonempty_hash(r, "string_sha256", "string_ref_count")
        if not sh:
            return ()
        return (
            r["instruction_count"], r["mnemonic_sha256"],
            r["operand_coarse_sha256"], r["flow_sha256"], sh,
        )
    raise KeyError(name)

def index_scheme(rows: list[dict], name: str) -> tuple[dict[tuple,list[dict]], Counter]:
    out: dict[tuple,list[dict]] = defaultdict(list)
    for r in rows:
        k = scheme_key(name,r)
        if k:
            out[k].append(r)
    return out, Counter({k:len(v) for k,v in out.items()})

def is_gameish(objects: list[str]) -> bool:
    if not objects:
        return False
    third_prefixes = (
        "lib", "bd", "bn_", "crt", "cvt", "exsup", "ismb", "inflate", "deflate",
        "unzip", "zip", "zlib", "lzo", "minilzo", "speex", "curl", "ssl", "crypto",
        "jpeg", "png", "ogg", "vorbis", "nvapi",
    )
    for obj in objects:
        base = obj.split(":")[-1].lower()
        if not base.startswith(third_prefixes):
            return True
    return False

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--client-dir",type=Path,required=True)
    ap.add_argument("--server-dir",type=Path,required=True)
    ap.add_argument("--server-ranges-dir",type=Path,required=True)
    ap.add_argument("--anchors",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    ap.add_argument("--min-anchor-tests",type=int,default=20)
    ap.add_argument("--min-instructions",type=int,default=8)
    a=ap.parse_args()

    client=load_tsv_dir(a.client_dir,"fingerprints_")
    server_all=load_tsv_dir(a.server_dir,"fingerprints_")
    ranges_by_va,range_rows=load_ranges(a.server_ranges_dir)
    # Only server functions with explicit exact PDB procedure-range provenance
    # are eligible identity targets in v1.
    server=[r for r in server_all if norm_va(r["entry_va"]) in ranges_by_va]

    by_client_va={norm_va(r["entry_va"]):r for r in client}
    by_server_va={norm_va(r["entry_va"]):r for r in server}

    adoc=json.loads(a.anchors.read_text(encoding="utf-8"))
    anchors=adoc["matches"]
    anchor_by_client={norm_va(x["current_client_va"]):norm_va(x["server_address_start"]) for x in anchors}
    anchor_server_vas=set(anchor_by_client.values())

    schemes=[
        "mnemonic_flow","coarse_flow","fine_flow",
        "coarse_profile","fine_profile","string_profile",
    ]
    client_idx={}; server_idx={}
    for name in schemes:
        client_idx[name],_=index_scheme(client,name)
        server_idx[name],_=index_scheme(server,name)

    calibration={}
    safe=[]
    for name in schemes:
        tested=correct=wrong=not_unique=missing=0
        wrong_examples=[]
        for cva,sva in anchor_by_client.items():
            cr=by_client_va.get(cva); sr=by_server_va.get(sva)
            if cr is None or sr is None:
                missing += 1
                continue
            ck=scheme_key(name,cr)
            sk=scheme_key(name,sr)
            if not ck or ck != sk:
                missing += 1
                continue
            cs=client_idx[name].get(ck,[])
            ss=server_idx[name].get(sk,[])
            if len(cs)!=1 or len(ss)!=1:
                not_unique += 1
                continue
            tested += 1
            pred=norm_va(ss[0]["entry_va"])
            if pred == sva:
                correct += 1
            else:
                wrong += 1
                if len(wrong_examples)<10:
                    wrong_examples.append({"client_va":cva,"expected_server_va":sva,"predicted_server_va":pred})
        precision=(correct/tested) if tested else None
        calibration[name]={
            "tested_unique_anchors":tested,
            "correct":correct,
            "wrong":wrong,
            "not_unique":not_unique,
            "missing_or_shape_changed":missing,
            "precision":precision,
            "wrong_examples":wrong_examples,
        }
        if tested>=a.min_anchor_tests and wrong==0:
            safe.append(name)

    candidates=[]
    conflicts=[]
    for cr in client:
        cva=norm_va(cr["entry_va"])
        if cva in anchor_by_client:
            continue
        try:
            if int(cr["instruction_count"]) < a.min_instructions:
                continue
        except ValueError:
            continue

        votes: dict[str,list[str]] = defaultdict(list)
        for name in safe:
            k=scheme_key(name,cr)
            if not k:
                continue
            if len(client_idx[name].get(k,[])) != 1:
                continue
            ss=server_idx[name].get(k,[])
            if len(ss) != 1:
                continue
            sva=norm_va(ss[0]["entry_va"])
            votes[sva].append(name)

        if not votes:
            continue
        ranked=sorted(votes.items(), key=lambda kv:(-len(kv[1]),kv[0]))
        best_va,best_schemes=ranked[0]
        if len(ranked)>1 and len(ranked[1][1])==len(best_schemes):
            conflicts.append({"client_va":cva,"votes":dict(votes)})
            continue
        # A server function already consumed by an accepted exact anchor may not
        # be reassigned by structural similarity.
        if best_va in anchor_server_vas:
            continue
        sr=by_server_va[best_va]
        if cr["exact_bytes_sha256"] == sr["exact_bytes_sha256"]:
            # Exact-byte identity belongs to the exact-hash census, including its
            # ambiguity rules. Structural matching must not side-step that gate.
            continue

        # Require two calibrated dimensions agreeing. Nested fingerprints are
        # still candidate evidence, not independent semantic proof.
        if len(best_schemes) < 2:
            continue

        rr=ranges_by_va[best_va]
        variants=sorted({x["server_variant_id"] for x in rr})
        symbols=sorted({x["symbol_name"] for x in rr if x.get("symbol_name")})
        objects=sorted({x["object_name"] for x in rr if x.get("object_name")})
        candidates.append({
            "client_va":cva,
            "client_ghidra_name":cr["name"],
            "server_va":best_va,
            "server_ghidra_name":sr["name"],
            "matched_schemes":sorted(best_schemes),
            "scheme_vote_count":len(best_schemes),
            "client_instruction_count":int(cr["instruction_count"]),
            "server_instruction_count":int(sr["instruction_count"]),
            "client_body_address_count":int(cr["body_address_count"]),
            "server_body_address_count":int(sr["body_address_count"]),
            "client_call_ref_count":int(cr["call_ref_count"]),
            "server_call_ref_count":int(sr["call_ref_count"]),
            "client_string_ref_count":int(cr["string_ref_count"]),
            "server_string_ref_count":int(sr["string_ref_count"]),
            "server_variant_ids":variants,
            "server_symbols":symbols,
            "server_objects":objects,
            "game_or_engine_context":is_gameish(objects),
            "state":"candidate-structural-fingerprint",
            "proof_boundary":"Changed-byte cross-build structural candidate only; no semantic identity, name, type, prototype, global, layout, source, or address-delta transfer is accepted.",
        })

    candidates.sort(key=lambda x:(
        not x["game_or_engine_context"],
        -x["scheme_vote_count"],
        -x["client_instruction_count"],
        x["client_va"],
    ))

    a.out_dir.mkdir(parents=True,exist_ok=True)
    result={
        "format":FORMAT,
        "client_function_rows":len(client),
        "server_function_rows_all":len(server_all),
        "server_function_rows_with_exact_pdb_range":len(server),
        "server_range_rows":range_rows,
        "accepted_exact_anchor_count":len(anchor_by_client),
        "safe_zero_error_schemes":safe,
        "calibration":calibration,
        "candidate_count":len(candidates),
        "game_or_engine_candidate_count":sum(x["game_or_engine_context"] for x in candidates),
        "conflicting_structural_vote_count":len(conflicts),
        "min_instructions":a.min_instructions,
        "candidates":candidates,
        "conflicts":conflicts[:200],
        "proof_boundary":"Structural fingerprints are calibrated against exact-byte anchors and generate candidate evidence only. Server build facts are never promoted into retail without separate retail-native corroboration.",
    }
    (a.out_dir/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    fields=[
        "client_va","client_ghidra_name","server_va","server_ghidra_name",
        "scheme_vote_count","matched_schemes","client_instruction_count",
        "server_instruction_count","client_body_address_count","server_body_address_count",
        "client_call_ref_count","server_call_ref_count","client_string_ref_count",
        "server_string_ref_count","server_symbols","server_objects","server_variant_ids",
        "game_or_engine_context","state","proof_boundary",
    ]
    with (a.out_dir/"candidates.tsv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
        w.writeheader()
        for x in candidates:
            row=dict(x)
            for k in ("matched_schemes","server_symbols","server_objects","server_variant_ids"):
                row[k]=";".join(row[k])
            w.writerow({k:row[k] for k in fields})

    summary={k:result[k] for k in (
        "format","client_function_rows","server_function_rows_all",
        "server_function_rows_with_exact_pdb_range","server_range_rows",
        "accepted_exact_anchor_count","safe_zero_error_schemes","calibration",
        "candidate_count","game_or_engine_candidate_count",
        "conflicting_structural_vote_count","min_instructions","proof_boundary",
    )}
    (a.out_dir/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
