#!/usr/bin/env python3
"""Propagate current-client identities through exact-byte anchors into the full server MAP.

This widens v1 from the exact-hash PDB subset to every linker MAP function start.
It uses only:
  * strict byte-identical anchor correspondences,
  * current-client exact direct CALL rel32 observations,
  * server linker MAP function-start VAs.

For an exact-byte anchor with client entry C and server entry S:
    translated_server_target = current_call_target + (S - C)

Only callsites inside the anchor's exact PDB-sized interval are used.

MAP aliases sharing one VA are preserved as an address-level symbol group. No
single symbol alias is arbitrarily selected as accepted identity. All newly
propagated targets are candidate evidence; this tool never auto-promotes them.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

FORMAT = "t6-current-client-anchor-delta-map-propagation-v2"

CALL_RE = re.compile(
    r'\{id:"(?P<id>[^"]+)",call_va:"(?P<call>0x[0-9A-Fa-f]+)",'
    r'target_va:"(?P<target>0x[0-9A-Fa-f]+)"'
)

def iva(v: str) -> int:
    return int(v, 16)

def hva(v: int) -> str:
    return f"0x{v:08x}"

def current_id(v: int) -> str:
    return f"urn:ure:t6:occ:function:current-client:{v:08x}"

def ev_id(client_va: int, server_va: int, anchors: list[str]) -> str:
    s = f"{client_va:08x}\0{server_va:08x}\0" + "\0".join(sorted(anchors))
    return "urn:ure:t6:re_Evidence:anchor-delta-map:" + hashlib.sha256(s.encode()).hexdigest()[:24]

def truthy(v: str) -> bool:
    return (v or "").strip().lower() in {"1","true","yes","y"}

def load_calls(call_dir: Path):
    calls=[]
    files=sorted(call_dir.glob("calls_*.cypher"))
    for p in files:
        text=p.read_text(encoding="utf-8")
        for m in CALL_RE.finditer(text):
            calls.append({
                "id":m.group("id"),
                "call_va":iva(m.group("call")),
                "target_va":iva(m.group("target")),
                "source_file":p.name,
            })
    calls.sort(key=lambda x:x["call_va"])
    return calls,files

def load_map(path: Path):
    by_va=defaultdict(list)
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            if not truthy(row.get("is_function","")):
                continue
            va=int(row["va"])
            by_va[va].append({
                "table":row.get("table",""),
                "decorated_name":row.get("decorated_name",""),
                "origin":row.get("origin",""),
                "library":row.get("library",""),
                "object":row.get("object",""),
                "is_inline":truthy(row.get("is_inline","")),
                "map_line":int(row["map_line"]) if row.get("map_line") else None,
                "span_upper_bound":int(row["span_upper_bound"]) if row.get("span_upper_bound") else None,
            })
    return by_va

def preferred_context(symbols):
    origins=sorted({x["origin"] for x in symbols if x["origin"]})
    objects=sorted({x["object"] for x in symbols if x["object"]})
    libraries=sorted({x["library"] for x in symbols if x["library"]})
    names=sorted({x["decorated_name"] for x in symbols if x["decorated_name"]})
    tables=sorted({x["table"] for x in symbols if x["table"]})
    return {
        "symbol_count":len(symbols),
        "decorated_names":names,
        "origins":origins,
        "objects":objects,
        "libraries":libraries,
        "tables":tables,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--strict-join",type=Path,required=True)
    ap.add_argument("--call-dir",type=Path,required=True)
    ap.add_argument("--map-symbols-gz",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--min-independent-anchors",type=int,default=2)
    a=ap.parse_args()

    strict=json.loads(a.strict_join.read_text(encoding="utf-8"))
    accepted=[x for x in strict["matches"] if x["state"]=="accepted-exact-byte-identity-witness"]
    strict_by_client=defaultdict(list)
    for x in accepted:
        strict_by_client[iva(x["current_client_va"])].append(x)

    calls,call_files=load_calls(a.call_dir)
    call_vas=[x["call_va"] for x in calls]
    map_by_va=load_map(a.map_symbols_gz)

    raw=[]
    anchors_with_calls=0
    anchors_with_map_hits=0
    for an in accepted:
        c0=iva(an["current_client_va"])
        s0=iva(an["server_address_start"])
        size=int(an["server_size_bytes"])
        if size<=0:
            continue
        lo=bisect.bisect_left(call_vas,c0)
        hi=bisect.bisect_left(call_vas,c0+size)
        inside=calls[lo:hi]
        if inside: anchors_with_calls+=1
        delta=s0-c0
        hit=False
        for call in inside:
            sv=call["target_va"]+delta
            syms=map_by_va.get(sv)
            if not syms:
                continue
            hit=True
            ctx=preferred_context(syms)
            raw.append({
                "anchor_client_va":hva(c0),
                "anchor_server_va":hva(s0),
                "anchor_server_variant_id":an["server_variant_id"],
                "anchor_server_symbol_name":an["server_symbol_name"],
                "anchor_server_object_name":an["server_object_name"],
                "anchor_exact_size_bytes":size,
                "anchor_delta":delta,
                "callsite_client_va":hva(call["call_va"]),
                "callsite_offset":call["call_va"]-c0,
                "client_target_va":hva(call["target_va"]),
                "client_target_id":current_id(call["target_va"]),
                "translated_server_target_va":hva(sv),
                "map_context":ctx,
                "call_bytes_source":call["source_file"],
            })
        if hit: anchors_with_map_hits+=1

    grouped=defaultdict(list)
    for x in raw:
        grouped[(x["client_target_id"],x["translated_server_target_va"])].append(x)

    client_servers=defaultdict(set)
    server_clients=defaultdict(set)
    for (cid,sva),xs in grouped.items():
        client_servers[cid].add(sva)
        server_clients[sva].add(cid)

    candidates=[]
    for (cid,sva),xs in sorted(grouped.items()):
        current_va=iva(xs[0]["client_target_va"])
        server_va=iva(sva)
        anchor_ids=sorted({x["anchor_server_variant_id"] for x in xs})
        callsites=sorted({x["callsite_client_va"] for x in xs})
        strict_hits=strict_by_client.get(current_va,[])
        strict_same=any(iva(x["server_address_start"])==server_va for x in strict_hits)
        strict_conflict=bool(strict_hits) and not strict_same
        conflict=(len(client_servers[cid])>1 or len(server_clients[sva])>1 or strict_conflict)
        nanchors=len(anchor_ids)
        if strict_same:
            state="corroborates-existing-strict-exact-hash"
        elif conflict:
            state="candidate-conflicting-anchor-delta-map"
        elif nanchors>=a.min_independent_anchors:
            state="candidate-multi-anchor-corroborated-map"
        else:
            state="candidate-anchor-delta-map"
        candidates.append({
            "evidence_id":ev_id(current_va,server_va,anchor_ids),
            "client_target_id":cid,
            "client_target_va":xs[0]["client_target_va"],
            "server_target_va":sva,
            "map_context":xs[0]["map_context"],
            "independent_anchor_count":nanchors,
            "callsite_count":len(callsites),
            "anchor_variant_ids":anchor_ids,
            "callsites":callsites,
            "conflicting_server_targets_for_client":len(client_servers[cid]),
            "conflicting_client_targets_for_server":len(server_clients[sva]),
            "already_strict_exact_hash_same":strict_same,
            "already_strict_exact_hash_conflict":strict_conflict,
            "state":state,
            "observations":xs,
        })

    states=Counter(x["state"] for x in candidates)
    gameish=[]
    third_prefixes=("lib","LIBCMT:","bd","phys_pcr:","librt","libtom","lzo","zlib","libcurl","openssl","jpeg","png","ogg","vorbis","nvapi")
    for x in candidates:
        origins=x["map_context"]["origins"]
        if any(origins) and not all(o.startswith(third_prefixes) for o in origins):
            gameish.append(x)

    doc={
        "format":FORMAT,
        "strict_anchor_count":len(accepted),
        "map_function_start_addresses":len(map_by_va),
        "map_function_symbol_rows":sum(len(v) for v in map_by_va.values()),
        "call_files":len(call_files),
        "current_client_direct_calls_parsed":len(calls),
        "anchors_with_interval_calls":anchors_with_calls,
        "anchors_with_map_target_hits":anchors_with_map_hits,
        "raw_translated_call_hits":len(raw),
        "candidate_pairs":len(candidates),
        "state_counts":dict(sorted(states.items())),
        "new_candidate_pairs":sum(1 for x in candidates if not x["already_strict_exact_hash_same"]),
        "new_multi_anchor_candidate_pairs":sum(1 for x in candidates if x["state"]=="candidate-multi-anchor-corroborated-map"),
        "game_or_engine_context_candidate_pairs":len(gameish),
        "proof_boundary":(
            "Every row is structural candidate evidence derived from a byte-identical anchor, "
            "an exact direct CALL rel32 inside its PDB-sized interval, and an exact linker MAP "
            "function-start hit after anchor-delta translation. MAP aliases sharing a VA are "
            "preserved. No propagated target is automatically accepted as semantic identity."
        ),
        "candidates":candidates,
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
        k:doc[k] for k in (
            "strict_anchor_count","map_function_start_addresses","map_function_symbol_rows",
            "current_client_direct_calls_parsed","raw_translated_call_hits","candidate_pairs",
            "new_candidate_pairs","new_multi_anchor_candidate_pairs",
            "game_or_engine_context_candidate_pairs","state_counts"
        )
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
