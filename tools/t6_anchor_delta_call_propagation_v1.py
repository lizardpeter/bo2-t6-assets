#!/usr/bin/env python3
"""Propagate T6 current-client/server identities through byte-identical anchor calls.

Inputs:
- strict exact-hash current-client <-> server/PDB join JSON
- current-client whole-image call Cypher chunks
- retained server/PDB exact-function-hash TSV shards

For each accepted exact-byte anchor, calls whose callsite lies inside the
server PDB exact-size interval are translated by the anchor VA delta:

    server_target_candidate = client_target + (server_anchor - client_anchor)

A translated target is retained only when it lands exactly on a UNIQUE known
server/PDB function start. The result is candidate structural evidence only.
No semantic correspondence is auto-accepted by this tool.

This intentionally does not use symbol-name similarity or raw address equality.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

FORMAT = "t6-current-client-anchor-delta-call-propagation-v1"

CALL_RE = re.compile(
    r'\{id:"(?P<id>[^"]+)",call_va:"(?P<call>0x[0-9A-Fa-f]+)",'
    r'target_va:"(?P<target>0x[0-9A-Fa-f]+)"'
)

def read_tsv(path: Path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, dialect="excel-tab"))

def iva(v: str) -> int:
    return int(v, 16)

def hva(v: int) -> str:
    return f"0x{v:08x}"

def current_id(v: int) -> str:
    return f"urn:ure:t6:occ:function:current-client:{v:08x}"

def evidence_id(client_target: str, server_variant: str, anchors: list[str]) -> str:
    key = client_target + "\0" + server_variant + "\0" + "\0".join(sorted(anchors))
    return "urn:ure:t6:re_Evidence:anchor-delta-call:" + hashlib.sha256(key.encode()).hexdigest()[:24]

def load_calls(call_dir: Path):
    calls = []
    files = sorted(call_dir.glob("calls_*.cypher"))
    for p in files:
        text = p.read_text(encoding="utf-8")
        for m in CALL_RE.finditer(text):
            calls.append({
                "id": m.group("id"),
                "call_va": iva(m.group("call")),
                "target_va": iva(m.group("target")),
                "source_file": p.name,
            })
    calls.sort(key=lambda x: x["call_va"])
    return calls, files

def load_server_rows(pdb_dir: Path):
    rows = []
    for p in sorted(pdb_dir.glob("server_pdb_exact_hashes_*.tsv")):
        rows.extend(read_tsv(p))
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict-join", type=Path, required=True)
    ap.add_argument("--call-dir", type=Path, required=True)
    ap.add_argument("--pdb-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-independent-anchors", type=int, default=2)
    args = ap.parse_args()

    strict = json.loads(args.strict_join.read_text(encoding="utf-8"))
    accepted = [
        x for x in strict["matches"]
        if x["state"] == "accepted-exact-byte-identity-witness"
    ]

    server_rows = load_server_rows(args.pdb_dir)
    server_by_start = defaultdict(list)
    for r in server_rows:
        s = (r.get("exact_address_start") or "").strip()
        if s:
            server_by_start[iva(s)].append(r)

    strict_by_client = defaultdict(list)
    for x in accepted:
        strict_by_client[iva(x["current_client_va"])].append(x)

    calls, call_files = load_calls(args.call_dir)

    # Sweep calls per anchor. 269 * 140k is still modest, but binary search keeps
    # this deterministic and cheap.
    call_vas = [x["call_va"] for x in calls]
    import bisect

    raw = []
    anchors_without_calls = 0
    for a in accepted:
        c0 = iva(a["current_client_va"])
        s0 = iva(a["server_address_start"])
        size = int(a["server_size_bytes"])
        if size <= 0:
            continue
        c1 = c0 + size
        lo = bisect.bisect_left(call_vas, c0)
        hi = bisect.bisect_left(call_vas, c1)
        inside = calls[lo:hi]
        if not inside:
            anchors_without_calls += 1
        delta = s0 - c0

        for call in inside:
            translated = call["target_va"] + delta
            hits = server_by_start.get(translated, [])
            if len(hits) != 1:
                continue
            sv = hits[0]
            raw.append({
                "anchor_client_va": hva(c0),
                "anchor_server_va": hva(s0),
                "anchor_server_variant_id": a["server_variant_id"],
                "anchor_server_symbol_name": a["server_symbol_name"],
                "anchor_server_object_name": a["server_object_name"],
                "anchor_exact_size_bytes": size,
                "anchor_delta": delta,
                "callsite_client_va": hva(call["call_va"]),
                "callsite_offset": call["call_va"] - c0,
                "client_target_va": hva(call["target_va"]),
                "client_target_id": current_id(call["target_va"]),
                "translated_server_target_va": hva(translated),
                "server_target_variant_id": sv["variant_id"],
                "server_target_family_id": sv.get("family_id") or "",
                "server_target_symbol_name": sv.get("symbol_name") or "",
                "server_target_object_name": sv.get("object_name") or "",
                "call_bytes_source": call["source_file"],
            })

    grouped = defaultdict(list)
    for x in raw:
        grouped[(x["client_target_id"], x["server_target_variant_id"])].append(x)

    # Detect conflicts: one current target mapping to >1 server variant, or one
    # server variant reached from >1 current target.
    client_variants = defaultdict(set)
    server_clients = defaultdict(set)
    for (cid, vid), xs in grouped.items():
        client_variants[cid].add(vid)
        server_clients[vid].add(cid)

    candidates = []
    rediscovered_strict = 0
    for (cid, vid), xs in sorted(grouped.items()):
        anchor_ids = sorted({x["anchor_server_variant_id"] for x in xs})
        callsites = sorted({x["callsite_client_va"] for x in xs})
        current_va = iva(xs[0]["client_target_va"])
        strict_hits = strict_by_client.get(current_va, [])
        strict_same = any(x["server_variant_id"] == vid for x in strict_hits)
        strict_conflict = bool(strict_hits) and not strict_same
        if strict_same:
            rediscovered_strict += 1

        conflict = (
            len(client_variants[cid]) > 1
            or len(server_clients[vid]) > 1
            or strict_conflict
        )
        independent_anchor_count = len(anchor_ids)
        state = "candidate-anchor-delta-call-propagation"
        if conflict:
            state = "candidate-conflicting-anchor-delta-call-propagation"
        elif strict_same:
            state = "corroborates-existing-strict-exact-hash"
        elif independent_anchor_count >= args.min_independent_anchors:
            state = "candidate-multi-anchor-corroborated"

        candidates.append({
            "evidence_id": evidence_id(cid, vid, anchor_ids),
            "client_target_id": cid,
            "client_target_va": xs[0]["client_target_va"],
            "server_target_variant_id": vid,
            "server_target_family_id": xs[0]["server_target_family_id"],
            "server_target_va": xs[0]["translated_server_target_va"],
            "server_target_symbol_name": xs[0]["server_target_symbol_name"],
            "server_target_object_name": xs[0]["server_target_object_name"],
            "independent_anchor_count": independent_anchor_count,
            "callsite_count": len(callsites),
            "anchor_variant_ids": anchor_ids,
            "callsites": callsites,
            "conflicting_server_variants_for_client": len(client_variants[cid]),
            "conflicting_client_targets_for_server": len(server_clients[vid]),
            "already_strict_exact_hash_same": strict_same,
            "already_strict_exact_hash_conflict": strict_conflict,
            "state": state,
            "observations": xs,
        })

    state_counts = Counter(x["state"] for x in candidates)
    new_multi = [
        x for x in candidates
        if x["state"] == "candidate-multi-anchor-corroborated"
    ]
    new_single = [
        x for x in candidates
        if x["state"] == "candidate-anchor-delta-call-propagation"
    ]

    doc = {
        "format": FORMAT,
        "strict_anchor_count": len(accepted),
        "server_pdb_rows": len(server_rows),
        "unique_server_pdb_starts": sum(1 for x in server_by_start.values() if len(x) == 1),
        "call_files": len(call_files),
        "current_client_direct_calls_parsed": len(calls),
        "anchors_without_interval_calls": anchors_without_calls,
        "raw_translated_call_hits": len(raw),
        "candidate_pairs": len(candidates),
        "rediscovered_existing_strict_pairs": rediscovered_strict,
        "new_multi_anchor_candidate_pairs": len(new_multi),
        "new_single_anchor_candidate_pairs": len(new_single),
        "state_counts": dict(sorted(state_counts.items())),
        "min_independent_anchors": args.min_independent_anchors,
        "proof_boundary": (
            "Candidates arise only from direct CALL rel32 observations lying within the "
            "PDB exact-size interval of a byte-identical cross-build anchor and whose "
            "translated target lands exactly on a unique known server/PDB function start. "
            "They are structural evidence, not accepted semantic identity. Multiple "
            "independent anchors strengthen a candidate but do not auto-promote it."
        ),
        "candidates": candidates,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        k: doc[k] for k in (
            "strict_anchor_count","server_pdb_rows","current_client_direct_calls_parsed",
            "raw_translated_call_hits","candidate_pairs",
            "rediscovered_existing_strict_pairs","new_multi_anchor_candidate_pairs",
            "new_single_anchor_candidate_pairs","state_counts"
        )
    }, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
