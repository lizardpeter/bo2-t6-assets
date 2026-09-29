#!/usr/bin/env python3
"""Project exact current-client Ghidra catalog/decompile evidence into graph-ready Cypher.

Generated Ghidra C remains evidence, not reconstructed source. The graph stores exact
catalog metadata, immutable corpus provenance, and decompile status; the compressed
generated C/ASM bundle remains in GitHub/R2 until reviewed source is promoted as a
literal immutable Representation.source_text.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

BUILD="urn:ure:t6:re_Build:current-client-sha77031817"
ART="urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"
CORPUS="urn:ure:t6:re_Evidence:current-client-ghidra-low-hanging-v1"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
BUNDLE_SHA="1d2678b7c1d9cdcff93e81b83cea2d674cfcc169c058cf792d2358b87987f8e2"
REPO_COMMIT="9eef5bf4636980a581faf3e93e0b4f8e0f06f9f5"

def cypher_string(v):
    return json.dumps("" if v is None else str(v),ensure_ascii=False)

def cypher_map(row):
    parts=[]
    for k,v in row.items():
        if isinstance(v,bool): val="true" if v else "false"
        elif isinstance(v,int): val=str(v)
        else: val=cypher_string(v)
        parts.append(f"{k}:{val}")
    return "{"+",".join(parts)+"}"

def chunks(rows,n):
    for i in range(0,len(rows),n):
        yield i//n,rows[i:i+n]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--selection",type=Path,required=True)
    ap.add_argument("--summary",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    ap.add_argument("--chunk-size",type=int,default=500)
    a=ap.parse_args()
    a.out_dir.mkdir(parents=True,exist_ok=True)

    with a.catalog.open(encoding="utf-8",newline="") as f:
        cat=list(csv.DictReader(f,dialect="excel-tab"))
    with a.selection.open(encoding="utf-8",newline="") as f:
        sel=list(csv.DictReader(f,dialect="excel-tab"))
    summary=json.loads(a.summary.read_text(encoding="utf-8"))
    selected_ids={r["function_id"]:r for r in sel}

    catalog_rows=[]
    for r in cat:
        va=r["entry_va"].lower().removeprefix("0x").zfill(8)
        fid=f"urn:ure:t6:occ:function:current-client:{va}"
        catalog_rows.append({
            "id":fid,
            "va":"0x"+va.upper(),
            "ghidra_name":r["name"],
            "prototype":r["prototype"],
            "calling_convention":r["calling_convention"],
            "parameter_count":int(r["parameter_count"]),
            "local_count":int(r["local_count"]),
            "body_address_count":int(r["body_address_count"]),
            "instruction_count":int(r["instruction_count"]),
            "call_reference_count":int(r["call_reference_count"]),
            "reference_count":int(r["reference_count"]),
            "is_thunk":r["is_thunk"].lower()=="true",
            "instruction_bytes_sha256":r["instruction_bytes_sha256"],
            "ghidra_max_address":r["max_address"],
        })

    selected_rows=[]
    for fid,r in selected_ids.items():
        selected_rows.append({
            "id":fid,
            "tier":r["tier"],
            "requested_va":r["requested_va"],
        })

    header=f'MATCH (b:KGNode {{id:{cypher_string(BUILD)}}}) MATCH (a:KGNode {{id:{cypher_string(ART)}}})'
    cat_files=[]
    for idx,batch in chunks(catalog_rows,a.chunk_size):
        payload="["+ ",".join(cypher_map(r) for r in batch) +"]"
        q=header+"\nWITH b,a,"+payload+""" AS rows
UNWIND rows AS row
MERGE (n:KGNode {id:row.id})
ON CREATE SET n.kind='re:FunctionOccurrence', n.namespace='t6', n.build_id=b.id, n.artifact_id=a.id,
    n.address_space='va', n.address_start=row.va, n.display_name='sub_'+substring(row.va,2)
SET n.ghidra_cataloged=true,
    n.ghidra_version='12.1.3',
    n.ghidra_name=row.ghidra_name,
    n.ghidra_prototype=row.prototype,
    n.ghidra_calling_convention=row.calling_convention,
    n.ghidra_parameter_count=row.parameter_count,
    n.ghidra_local_count=row.local_count,
    n.ghidra_body_address_count=row.body_address_count,
    n.ghidra_instruction_count=row.instruction_count,
    n.ghidra_call_reference_count=row.call_reference_count,
    n.ghidra_reference_count=row.reference_count,
    n.ghidra_is_thunk=row.is_thunk,
    n.ghidra_instruction_bytes_sha256=row.instruction_bytes_sha256,
    n.ghidra_max_address=row.ghidra_max_address,
    n.ghidra_analysis_state='generated-unreviewed-catalog',
    n.boundary_state=CASE WHEN coalesce(n.boundary_state,'') STARTS WITH 'exact-' THEN n.boundary_state ELSE 'ghidra-auto-analysis-candidate-body' END
MERGE (b)-[:HAS_OCCURRENCE]->(n)
MERGE (n)-[:DEFINED_IN]->(a)
"""
        p=a.out_dir/f"catalog_{idx:04d}.cypher"; p.write_text(q,encoding="utf-8"); cat_files.append(p.name)

    sel_files=[]
    for idx,batch in chunks(selected_rows,a.chunk_size):
        payload="["+ ",".join(cypher_map(r) for r in batch) +"]"
        q=f'MATCH (e:KGNode {{id:{cypher_string(CORPUS)}}})\nWITH e,'+payload+""" AS rows
UNWIND rows AS row
MATCH (n:KGNode {id:row.id})
SET n.ghidra_low_hanging_v1=true,
    n.ghidra_low_hanging_tier=row.tier,
    n.ghidra_decompile_state='generated-unreviewed-completed',
    n.ghidra_decompile_bundle_sha256='"""+BUNDLE_SHA+"""',
    n.ghidra_decompile_repo_commit='"""+REPO_COMMIT+"""'
MERGE (e)-[:EVIDENCE_FOR]->(n)
"""
        p=a.out_dir/f"selected_{idx:04d}.cypher"; p.write_text(q,encoding="utf-8"); sel_files.append(p.name)

    corpus=f'''MATCH (b:KGNode {{id:{cypher_string(BUILD)}}})
MATCH (a:KGNode {{id:{cypher_string(ART)}}})
MERGE (e:KGNode {{id:{cypher_string(CORPUS)}}})
SET e.kind='re:Evidence', e.namespace='t6',
    e.name='T6 current-client Ghidra low-hanging corpus v1',
    e.status='generated-unreviewed-exact-client-evidence',
    e.client_sha256='{CLIENT_SHA}',
    e.ghidra_version='12.1.3',
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit='{REPO_COMMIT}',
    e.catalog_path='proof/current_client/ghidra_low_hanging_v1/catalog.tsv',
    e.selection_path='proof/current_client/ghidra_low_hanging_v1/low_hanging.tsv',
    e.summary_path='proof/current_client/ghidra_low_hanging_v1/summary.json',
    e.bundle_path='proof/current_client/ghidra_low_hanging_v1/bundle.tar.zst.part-000',
    e.bundle_sha256='{BUNDLE_SHA}',
    e.catalog_function_count={int(summary["catalog_functions"])},
    e.selected_function_count={int(summary["selected_functions"])},
    e.decompile_completed_count={int(summary["decompile_completed"])},
    e.proof_boundary='Generated/unreviewed Ghidra evidence only. No decompiled body is reconstructed source or semantic completion until independently reviewed and promoted as an immutable Representation.'
MERGE (e)-[:TARGETS_BUILD]->(b)
MERGE (e)-[:EVIDENCE_FOR]->(a)
RETURN e.id
'''
    (a.out_dir/"corpus.cypher").write_text(corpus,encoding="utf-8")

    manifest={
      "format":"t6-current-client-ghidra-uregraph-projection-v1",
      "client_sha256":CLIENT_SHA,
      "catalog_rows":len(catalog_rows),
      "selected_rows":len(selected_rows),
      "chunk_size":a.chunk_size,
      "catalog_files":cat_files,
      "selected_files":sel_files,
      "corpus_file":"corpus.cypher",
      "bundle_sha256":BUNDLE_SHA,
      "repo_commit":REPO_COMMIT,
      "proof_boundary":"Graph-ready generated evidence projection; no semantic family identity or reconstructed source promotion."
    }
    (a.out_dir/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:manifest[k] for k in ["catalog_rows","selected_rows","chunk_size"]},indent=2))

if __name__=="__main__": main()
