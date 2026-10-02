#!/usr/bin/env python3
"""Project calibrated T6 structural cross-build matches into uregraph as candidates.

This importer is intentionally non-promoting:
  * it creates re:Evidence candidate nodes,
  * links each candidate to the exact retail occurrence and every same-VA server
    FunctionVariant carried by the proof row,
  * never creates CROSSBUILD_CORRESPONDS_TO,
  * never renames retail functions,
  * never transfers PDB prototypes, types, globals, layouts, or source claims.

The structural proof remains useful because its schemes were calibrated against
accepted exact-byte cross-build anchors before generating changed-byte matches.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

FORMAT="t6-structural-cross-build-uregraph-v1"
CLIENT_BUILD="urn:ure:t6:re_Build:current-client-sha77031817"
CLIENT_ARTIFACT="urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SERVER_BUILD="urn:ure:t6:re_Build:urn_ure_t6_core_Project_black-ops-2_fd2705692f16c05f_pc-server-2013-03-11:4ee9a1fac7aa9195"
SERVER_PDB_SHA="7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc"

def qs(v):
    return json.dumps("" if v is None else str(v),ensure_ascii=False)

def cv(v):
    if v is None:
        return "null"
    if isinstance(v,bool):
        return "true" if v else "false"
    if isinstance(v,int):
        return str(v)
    if isinstance(v,float):
        return repr(v)
    if isinstance(v,str):
        return qs(v)
    if isinstance(v,list):
        return "["+",".join(cv(x) for x in v)+"]"
    if isinstance(v,dict):
        return "{"+",".join(f"{k}:{cv(x)}" for k,x in v.items())+"}"
    raise TypeError(type(v))

def read_tsv(path:Path):
    with path.open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f,dialect="excel-tab"))

def norm_va(v:str)->str:
    s=(v or "").strip().lower().removeprefix("0x")
    return f"0x{int(s,16):08x}"

def client_id(v:str)->str:
    return "urn:ure:t6:occ:function:current-client:"+norm_va(v).removeprefix("0x")

def evidence_id(client_va:str,server_va:str,schemes:list[str])->str:
    key="\0".join([norm_va(client_va),norm_va(server_va),*sorted(schemes)])
    return "urn:ure:t6:re_Evidence:structural-xbuild:"+hashlib.sha256(key.encode()).hexdigest()[:24]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--summary",type=Path,required=True)
    ap.add_argument("--candidates",type=Path,required=True)
    ap.add_argument("--repo-commit",required=True)
    ap.add_argument("--workflow-run-id",type=int,default=0)
    ap.add_argument("--out-dir",type=Path,required=True)
    ap.add_argument("--chunk-size",type=int,default=35)
    a=ap.parse_args()

    summary=json.loads(a.summary.read_text(encoding="utf-8"))
    rows=read_tsv(a.candidates)
    if len(rows)!=int(summary["candidate_count"]):
        raise SystemExit(f"candidate row mismatch: {len(rows)} != {summary['candidate_count']}")

    safe=list(summary["safe_zero_error_schemes"])
    calibration=summary["calibration"]
    proof=[]
    for r in rows:
        schemes=[x for x in r["matched_schemes"].split(";") if x]
        variants=[x for x in r["server_variant_ids"].split(";") if x]
        if len(schemes)<2:
            raise SystemExit(f"unsafe single-scheme candidate: {r['client_va']}")
        if not set(schemes).issubset(set(safe)):
            raise SystemExit(f"candidate uses uncalibrated scheme: {r['client_va']}")
        if not variants:
            raise SystemExit(f"candidate without server variant: {r['client_va']}")
        proof.append({
            "id":evidence_id(r["client_va"],r["server_va"],schemes),
            "client_id":client_id(r["client_va"]),
            "client_va":norm_va(r["client_va"]),
            "client_ghidra_name":r["client_ghidra_name"],
            "server_va":norm_va(r["server_va"]),
            "server_ghidra_name":r["server_ghidra_name"],
            "server_variant_ids":variants,
            "server_symbols":[x for x in r["server_symbols"].split(";") if x],
            "server_objects":[x for x in r["server_objects"].split(";") if x],
            "matched_schemes":schemes,
            "scheme_vote_count":int(r["scheme_vote_count"]),
            "client_instruction_count":int(r["client_instruction_count"]),
            "server_instruction_count":int(r["server_instruction_count"]),
            "client_body_address_count":int(r["client_body_address_count"]),
            "server_body_address_count":int(r["server_body_address_count"]),
            "client_call_ref_count":int(r["client_call_ref_count"]),
            "server_call_ref_count":int(r["server_call_ref_count"]),
            "client_string_ref_count":int(r["client_string_ref_count"]),
            "server_string_ref_count":int(r["server_string_ref_count"]),
            "game_or_engine_context":r["game_or_engine_context"].strip().lower()=="true",
            "state":"candidate-structural-fingerprint",
        })

    a.out_dir.mkdir(parents=True,exist_ok=True)
    corpus_id="urn:ure:t6:re_Evidence:structural-cross-build-match-v1"
    cal_json=json.dumps(calibration,sort_keys=True,separators=(",",":"))
    corpus=f"""MERGE (e:KGNode {{id:{qs(corpus_id)}}})
SET e.kind='re:Evidence',
    e.namespace='t6',
    e.evidence_kind='cross-build-structural-fingerprint-corpus',
    e.state='candidate-only',
    e.format={qs(FORMAT)},
    e.client_build_id={qs(CLIENT_BUILD)},
    e.client_artifact_id={qs(CLIENT_ARTIFACT)},
    e.client_sha256={qs(CLIENT_SHA)},
    e.server_build_id={qs(SERVER_BUILD)},
    e.server_pdb_sha256={qs(SERVER_PDB_SHA)},
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit={qs(a.repo_commit)},
    e.workflow_run_id={a.workflow_run_id},
    e.candidate_count={len(proof)},
    e.game_or_engine_candidate_count={sum(x["game_or_engine_context"] for x in proof)},
    e.conflicting_structural_vote_count={int(summary["conflicting_structural_vote_count"])},
    e.safe_zero_error_schemes={cv(safe)},
    e.calibration_json={qs(cal_json)},
    e.proof_boundary='Calibrated changed-byte structural similarity is candidate evidence only. No retail semantic identity, name, prototype, type, global, layout, source attribution, or server address fact is promoted.'
RETURN e.id
"""
    (a.out_dir/"corpus.cypher").write_text(corpus,encoding="utf-8")

    files=[]
    for off in range(0,len(proof),a.chunk_size):
        batch=proof[off:off+a.chunk_size]
        q=f"""MATCH (corpus:KGNode {{id:{qs(corpus_id)}}})
WITH corpus,{cv(batch)} AS rows
UNWIND rows AS row
MATCH (client:KGNode {{id:row.client_id}})
MERGE (ev:KGNode {{id:row.id}})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-fingerprint-candidate',
    ev.state=row.state,
    ev.client_build_id={qs(CLIENT_BUILD)},
    ev.client_artifact_id={qs(CLIENT_ARTIFACT)},
    ev.client_sha256={qs(CLIENT_SHA)},
    ev.server_build_id={qs(SERVER_BUILD)},
    ev.server_pdb_sha256={qs(SERVER_PDB_SHA)},
    ev.client_va=row.client_va,
    ev.client_ghidra_name=row.client_ghidra_name,
    ev.server_va=row.server_va,
    ev.server_ghidra_name=row.server_ghidra_name,
    ev.server_symbols=row.server_symbols,
    ev.server_objects=row.server_objects,
    ev.matched_schemes=row.matched_schemes,
    ev.scheme_vote_count=row.scheme_vote_count,
    ev.client_instruction_count=row.client_instruction_count,
    ev.server_instruction_count=row.server_instruction_count,
    ev.client_body_address_count=row.client_body_address_count,
    ev.server_body_address_count=row.server_body_address_count,
    ev.client_call_ref_count=row.client_call_ref_count,
    ev.server_call_ref_count=row.server_call_ref_count,
    ev.client_string_ref_count=row.client_string_ref_count,
    ev.server_string_ref_count=row.server_string_ref_count,
    ev.game_or_engine_context=row.game_or_engine_context,
    ev.producer={qs(FORMAT)},
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit={qs(a.repo_commit)},
    ev.workflow_run_id={a.workflow_run_id},
    ev.proof_boundary='Candidate-only changed-byte structural match calibrated against exact anchors; no semantic promotion or PDB type/global transfer.'
MERGE (corpus)-[:CONTAINS_EVIDENCE]->(ev)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
WITH ev,row
UNWIND row.server_variant_ids AS variant_id
MATCH (server:KGNode {{id:variant_id}})
MERGE (ev)-[:EVIDENCE_FOR]->(server)
"""
        p=a.out_dir/f"candidates_{off//a.chunk_size:04d}.cypher"
        p.write_text(q,encoding="utf-8")
        files.append(p.name)

    manifest={
        "format":FORMAT,
        "graph":"uregraph",
        "candidate_rows":len(proof),
        "game_or_engine_candidate_rows":sum(x["game_or_engine_context"] for x in proof),
        "chunk_size":a.chunk_size,
        "corpus_file":"corpus.cypher",
        "candidate_files":files,
        "safe_zero_error_schemes":safe,
        "repo_commit":a.repo_commit,
        "workflow_run_id":a.workflow_run_id,
        "proof_boundary":"All graph rows remain candidate-only. The projection deliberately creates no accepted cross-build correspondence relation.",
    }
    (a.out_dir/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
