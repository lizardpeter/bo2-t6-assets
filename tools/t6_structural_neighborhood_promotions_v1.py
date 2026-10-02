#!/usr/bin/env python3
"""Select rigorously corroborated T6 changed-byte cross-build identities.

Promotion here means accepted *evidence* awaiting semantic promotion, matching
the state used for exact-byte cross-build witnesses. It does not make server
PDB types/globals/layouts authoritative for retail.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

FORMAT="t6-structural-neighborhood-promotions-v1"
SAFE={"mnemonic_flow","coarse_flow","fine_flow","coarse_profile","fine_profile"}

def read_tsv(p):
    with p.open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f,dialect="excel-tab"))

def q(v):
    return json.dumps("" if v is None else str(v),ensure_ascii=False)

def cv(v):
    if v is None:
        return "null"
    if isinstance(v,bool):
        return "true" if v else "false"
    if isinstance(v,(int,float)):
        return str(v)
    if isinstance(v,str):
        return q(v)
    if isinstance(v,list):
        return "["+",".join(cv(x) for x in v)+"]"
    if isinstance(v,dict):
        return "{"+",".join(f"{k}:{cv(x)}" for k,x in v.items())+"}"
    raise TypeError(type(v))

def eid(c,s):
    return "urn:ure:t6:re_Evidence:structural-neighborhood-accepted:"+hashlib.sha256((c+"\0"+s).encode()).hexdigest()[:24]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--candidates",type=Path,required=True)
    ap.add_argument("--neighborhood",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    ap.add_argument("--repo-commit",required=True)
    ap.add_argument("--workflow-run-id",type=int,default=0)
    a=ap.parse_args()

    candidates={(r["client_va"].lower(),r["server_va"].lower()):r for r in read_tsv(a.candidates)}
    n=json.loads(a.neighborhood.read_text(encoding="utf-8"))
    accepted=[]
    rejected=[]
    for x in n["pairs"]:
        key=(x["client_va"].lower(),x["server_va"].lower())
        c=candidates[key]
        schemes=set(x["matched_schemes"])
        structural_complete=(
            x["scheme_vote_count"]==5 and schemes==SAFE and
            int(c["client_instruction_count"])==int(c["server_instruction_count"]) and
            int(c["client_body_address_count"])==int(c["server_body_address_count"])
        )
        calls_complete=(
            x["client_call_count"]==x["server_call_count"]==x["common_call_offsets"]
        )
        data_complete=(
            x["client_data_ref_offsets"]==x["server_data_ref_offsets"]==x["shared_data_ref_offsets"]
        )
        no_conflict=x["exact_anchor_callee_conflicts"]==0
        anchor_basis=x["exact_anchor_callee_matches"]>=2
        string_basis=(
            x["client_unique_strings"]>=3 and
            x["shared_unique_strings"]==x["client_unique_strings"] and
            len(x["client_only_strings"])==0
        )
        variant_ids=[v for v in c["server_variant_ids"].split(";") if v]
        single_variant=len(variant_ids)==1
        ok=structural_complete and calls_complete and data_complete and no_conflict and single_variant and (anchor_basis or string_basis)
        row={
            "client_va":x["client_va"],
            "server_va":x["server_va"],
            "server_symbol":x["server_symbols"][0] if len(x["server_symbols"])==1 else ";".join(x["server_symbols"]),
            "server_object":x["server_objects"][0] if len(x["server_objects"])==1 else ";".join(x["server_objects"]),
            "server_variant_id":variant_ids[0] if single_variant else "",
            "structural_schemes":";".join(sorted(schemes)),
            "exact_anchor_callee_matches":x["exact_anchor_callee_matches"],
            "shared_unique_strings":x["shared_unique_strings"],
            "call_count":x["client_call_count"],
            "data_ref_offset_count":x["client_data_ref_offsets"],
            "basis":"five-calibrated-structural-schemes+exact-anchor-callees" if anchor_basis else
                    "five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
            "evidence_id":eid(x["client_va"],x["server_va"]),
        }
        (accepted if ok else rejected).append(row)

    if len(accepted)!=8:
        raise SystemExit(f"promotion gate expected 8 accepted rows, got {len(accepted)}")

    a.out_dir.mkdir(parents=True,exist_ok=True)
    fields=list(accepted[0].keys())
    with (a.out_dir/"accepted.tsv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
        w.writeheader();w.writerows(accepted)

    # Resolve each accepted row in one atomic UNWIND transaction. The
    # server variant is pinned by the candidate ledger so aliases cannot
    # silently change which semantic family is selected.
    payload=[]
    for r in accepted:
        cva=r["client_va"].lower()
        sva=r["server_va"].lower()
        payload.append({
            "client_va":cva,
            "server_va":sva,
            "client_id":"urn:ure:t6:occ:function:current-client:"+cva.removeprefix("0x"),
            "server_variant_id":r["server_variant_id"],
            "evidence_id":r["evidence_id"],
            "server_symbol":r["server_symbol"],
            "server_object":r["server_object"],
            "basis":r["basis"],
            "structural_schemes":r["structural_schemes"],
            "exact_anchor_callee_matches":int(r["exact_anchor_callee_matches"]),
            "shared_unique_strings":int(r["shared_unique_strings"]),
            "call_count":int(r["call_count"]),
            "data_ref_offset_count":int(r["data_ref_offset_count"]),
        })

    cypher=f"""WITH {cv(payload)} AS rows
UNWIND rows AS row
MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va=row.client_va AND struct.server_va=row.server_va
MATCH (server:KGNode {id:row.server_variant_id})
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:row.client_id})
MERGE (ev:KGNode {id:row.evidence_id})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va=row.client_va,
    ev.server_va=row.server_va,
    ev.server_symbol=row.server_symbol,
    ev.server_object=row.server_object,
    ev.basis=row.basis,
    ev.structural_schemes=row.structural_schemes,
    ev.exact_anchor_callee_matches=row.exact_anchor_callee_matches,
    ev.shared_unique_strings=row.shared_unique_strings,
    ev.call_count=row.call_count,
    ev.data_ref_offset_count=row.data_ref_offset_count,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit={q(a.repo_commit)},
    ev.workflow_run_id={a.workflow_run_id},
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis=row.basis,
    client.cross_build_identity_evidence_id=ev.id
RETURN count(DISTINCT ev) AS accepted_evidence_rows
"""
    (a.out_dir/"promote.cypher").write_text(cypher,encoding="utf-8")
    summary={
        "format":FORMAT,
        "accepted_evidence_rows":len(accepted),
        "exact_anchor_callee_basis":sum("exact-anchor-callees" in r["basis"] for r in accepted),
        "distinctive_string_basis":sum("string-set" in r["basis"] for r in accepted),
        "repo_commit":a.repo_commit,
        "workflow_run_id":a.workflow_run_id,
        "proof_boundary":"Accepted evidence awaiting semantic promotion; no server type/global/layout transfer."
    }
    (a.out_dir/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
