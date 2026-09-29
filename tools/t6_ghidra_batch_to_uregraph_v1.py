#!/usr/bin/env python3
"""Build graph-ready Cypher for one exact-client generated Ghidra decompile batch.

This records generated/unreviewed evidence only. It never promotes Ghidra C to
reconstructed source and never assigns cross-build semantic identity.
"""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

BUILD="urn:ure:t6:re_Build:current-client-sha77031817"
ART="urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def qs(v): return json.dumps("" if v is None else str(v),ensure_ascii=False)
def cmap(r):
    out=[]
    for k,v in r.items():
        if isinstance(v,bool): x="true" if v else "false"
        elif isinstance(v,int): x=str(v)
        else: x=qs(v)
        out.append(f"{k}:{x}")
    return "{"+",".join(out)+"}"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selection",type=Path,required=True)
    ap.add_argument("--results",type=Path,required=True)
    ap.add_argument("--summary",type=Path,required=True)
    ap.add_argument("--corpus-id",required=True)
    ap.add_argument("--corpus-name",required=True)
    ap.add_argument("--repo-commit",required=True)
    ap.add_argument("--bundle-sha256",required=True)
    ap.add_argument("--bundle-path",required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    ap.add_argument("--chunk-size",type=int,default=500)
    a=ap.parse_args()
    a.out_dir.mkdir(parents=True,exist_ok=True)

    with a.selection.open(encoding="utf-8",newline="") as f:
        sel=list(csv.DictReader(f,dialect="excel-tab"))
    with a.results.open(encoding="utf-8",newline="") as f:
        res=list(csv.DictReader(f,dialect="excel-tab"))
    summary=json.loads(a.summary.read_text(encoding="utf-8"))
    byid={r["function_id"]:r for r in res}
    if set(byid)!={r["function_id"] for r in sel}:
        raise SystemExit("selection/results function sets differ")

    rows=[]
    for s in sel:
        r=byid[s["function_id"]]
        rows.append({
          "id":s["function_id"],
          "tier":s["tier"],
          "requested_va":s["requested_va"],
          "found_exact":r["found_exact"].lower()=="true",
          "resolved_entry":r["resolved_entry"],
          "ghidra_name":r["ghidra_name"],
          "prototype":r["prototype"],
          "calling_convention":r["calling_convention"],
          "parameter_count":int(r["parameter_count"] or 0),
          "local_count":int(r["local_count"] or 0),
          "decompile_completed":r["decompile_completed"].lower()=="true",
          "decompiler_message":r["decompiler_message"],
          "elapsed_ms":int(r["elapsed_ms"] or 0),
          "c_bytes":int(r["c_bytes"] or 0),
          "instruction_count":int(r["instruction_count"] or 0),
          "reference_count":int(r["reference_count"] or 0),
          "asm_bytes":int(r["asm_bytes"] or 0),
        })

    corpus=f'''MATCH (b:KGNode {{id:{qs(BUILD)}}})
MATCH (a:KGNode {{id:{qs(ART)}}})
MERGE (e:KGNode {{id:{qs(a.corpus_id)}}})
SET e.kind='re:Evidence', e.namespace='t6',
    e.name={qs(a.corpus_name)},
    e.status='generated-unreviewed-exact-client-evidence',
    e.client_sha256='{CLIENT_SHA}',
    e.ghidra_version='12.1.3',
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit={qs(a.repo_commit)},
    e.selection_path={qs(str(a.selection))},
    e.results_path={qs(str(a.results))},
    e.summary_path={qs(str(a.summary))},
    e.bundle_path={qs(a.bundle_path)},
    e.bundle_sha256={qs(a.bundle_sha256)},
    e.selected_function_count={len(rows)},
    e.decompile_completed_count={sum(1 for r in rows if r["decompile_completed"])},
    e.decompile_failed_count={sum(1 for r in rows if not r["decompile_completed"])},
    e.proof_boundary='Generated/unreviewed Ghidra evidence only. No decompiled body is reconstructed source or semantic completion until independently reviewed and promoted.'
MERGE (e)-[:TARGETS_BUILD]->(b)
MERGE (e)-[:EVIDENCE_FOR]->(a)
RETURN e.id
'''
    (a.out_dir/"corpus.cypher").write_text(corpus,encoding="utf-8")

    files=[]
    for i in range(0,len(rows),a.chunk_size):
        batch=rows[i:i+a.chunk_size]
        payload="["+ ",".join(cmap(r) for r in batch) +"]"
        q=f'MATCH (e:KGNode {{id:{qs(a.corpus_id)}}})\nWITH e,'+payload+""" AS rows
UNWIND rows AS row
MERGE (n:KGNode {id:row.id})
ON CREATE SET n.kind='re:FunctionOccurrence', n.namespace='t6',
    n.build_id='"""+BUILD+"""', n.artifact_id='"""+ART+"""',
    n.address_space='va', n.address_start=row.requested_va,
    n.display_name='sub_'+substring(row.requested_va,2)
SET n.ghidra_decompile_evidence=true,
    n.ghidra_decompile_tier=row.tier,
    n.ghidra_found_exact=row.found_exact,
    n.ghidra_resolved_entry=row.resolved_entry,
    n.ghidra_name=row.ghidra_name,
    n.ghidra_prototype=row.prototype,
    n.ghidra_calling_convention=row.calling_convention,
    n.ghidra_parameter_count=row.parameter_count,
    n.ghidra_local_count=row.local_count,
    n.ghidra_decompile_completed=row.decompile_completed,
    n.ghidra_decompiler_message=row.decompiler_message,
    n.ghidra_decompile_elapsed_ms=row.elapsed_ms,
    n.ghidra_generated_c_bytes=row.c_bytes,
    n.ghidra_instruction_count=row.instruction_count,
    n.ghidra_reference_count=row.reference_count,
    n.ghidra_generated_asm_bytes=row.asm_bytes,
    n.ghidra_evidence_corpus=e.id,
    n.ghidra_evidence_state=CASE WHEN row.decompile_completed THEN 'generated-unreviewed-completed' ELSE 'generated-unreviewed-failed' END
MERGE (e)-[:EVIDENCE_FOR]->(n)
"""
        p=a.out_dir/f"functions_{i//a.chunk_size:04d}.cypher"
        p.write_text(q,encoding="utf-8"); files.append(p.name)

    manifest={
      "format":"t6-current-client-ghidra-batch-uregraph-projection-v1",
      "corpus_id":a.corpus_id,
      "client_sha256":CLIENT_SHA,
      "rows":len(rows),
      "completed":sum(1 for r in rows if r["decompile_completed"]),
      "failed":sum(1 for r in rows if not r["decompile_completed"]),
      "chunk_size":a.chunk_size,
      "files":files,
      "corpus_file":"corpus.cypher",
      "proof_boundary":"Generated evidence projection only; no reconstructed source or cross-build identity promotion."
    }
    (a.out_dir/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:manifest[k] for k in ["rows","completed","failed","chunk_size"]},indent=2))

if __name__=="__main__": main()
