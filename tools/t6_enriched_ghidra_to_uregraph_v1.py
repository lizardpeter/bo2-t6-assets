#!/usr/bin/env python3
"""Build graph-ready revision-2 T6 Ghidra pseudocode projections from an enriched shard.

The full enriched run is an audit over every exact current-client Ghidra function.
To avoid duplicating unchanged C in uregraph, this projector emits new
core:Representation nodes only for decompiler-visible cross-build impact:
  * functions whose own Ghidra name is xbuild_*, or
  * functions with an exact Ghidra reference whose target symbol is xbuild_*.

Server-derived prototypes/types/globals/layouts are never promoted here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

BUILD="urn:ure:t6:re_Build:current-client-sha77031817"
ART="urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def qs(v):
    return json.dumps("" if v is None else str(v),ensure_ascii=False)

def read_tsv(path: Path):
    with path.open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f,dialect="excel-tab"))

def body_text(full: str) -> str:
    marker="*/\n\n"
    i=full.find(marker)
    return full[i+len(marker):] if i>=0 else full

def cmap(r):
    out=[]
    for k,v in r.items():
        if isinstance(v,bool):
            x="true" if v else "false"
        elif isinstance(v,int):
            x=str(v)
        else:
            x=qs(v)
        out.append(f"{k}:{x}")
    return "{"+",".join(out)+"}"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--batch-dir",type=Path,required=True,
                    help="Extracted ExportT6CurrentClientBatch output directory")
    ap.add_argument("--shard",type=int,required=True)
    ap.add_argument("--workflow-run-id",type=int,required=True)
    ap.add_argument("--repo-commit",required=True)
    ap.add_argument("--bundle-sha256",default="")
    ap.add_argument("--out-dir",type=Path,required=True)
    ap.add_argument("--chunk-size",type=int,default=20)
    a=ap.parse_args()

    results=read_tsv(a.batch_dir/"results.tsv")
    refs=read_tsv(a.batch_dir/"references.tsv")
    affected={r["function_id"] for r in results if r["ghidra_name"].startswith("xbuild_")}
    affected.update(r["function_id"] for r in refs if r["target_symbol"].startswith("xbuild_"))

    rows=[]
    for r in results:
        if r["function_id"] not in affected or r["decompile_completed"].lower()!="true":
            continue
        va=int(r["requested_va"],16)
        member=f"unreviewed/{va:08x}.c"
        p=a.batch_dir/member
        if not p.exists():
            raise SystemExit(f"missing generated C: {p}")
        full=p.read_text(encoding="utf-8")
        body=body_text(full)
        full_sha=hashlib.sha256(full.encode("utf-8")).hexdigest()
        body_sha=hashlib.sha256(body.encode("utf-8")).hexdigest()
        rep_id=f"urn:ure:t6:representation:pseudocode:c:ghidra-xbuild-hints:{va:08x}:{full_sha}"
        rows.append({
            "subject_id":r["function_id"],
            "id":rep_id,
            "address_start":f"0x{va:08X}",
            "ghidra_name":r["ghidra_name"],
            "source_text":full,
            "content_sha256":full_sha,
            "decompiler_body_sha256":body_sha,
            "size_bytes":len(full.encode("utf-8")),
            "bundle_member":member,
            "semantic_name_state":"cross-build-hint-only" if r["ghidra_name"].startswith("xbuild_")
                                  else "retail-analysis-affected-by-cross-build-hint",
        })

    a.out_dir.mkdir(parents=True,exist_ok=True)
    evidence_id=f"urn:ure:t6:evidence:whole-program-ghidra-xbuild-hints-{a.workflow_run_id}:shard:{a.shard}"
    corpus=f"""MERGE (e:KGNode {{id:{qs(evidence_id)}}})
SET e.kind='re:Evidence',
    e.namespace='t6',
    e.status='generated-unreviewed',
    e.build_id={qs(BUILD)},
    e.artifact_id={qs(ART)},
    e.client_sha256={qs(CLIENT_SHA)},
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit={qs(a.repo_commit)},
    e.workflow_run_id={a.workflow_run_id},
    e.ghidra_version='12.1.3',
    e.shard={a.shard},
    e.full_shard_function_count={len(results)},
    e.xbuild_affected_representation_count={len(rows)},
    e.bundle_sha256={qs(a.bundle_sha256)},
    e.proof_boundary='Exact current-client generated Ghidra evidence. Server MAP/PDB is cross-build hint evidence only; no server prototype, type, global, source layout, or address-delta fact is promoted.'
RETURN e.id
"""
    (a.out_dir/"corpus.cypher").write_text(corpus,encoding="utf-8")

    files=[]
    for i in range(0,len(rows),a.chunk_size):
        batch=rows[i:i+a.chunk_size]
        payload="["+ ",".join(cmap(r) for r in batch) +"]"
        q=f"""MATCH (e:KGNode {{id:{qs(evidence_id)}}})
WITH e,{payload} AS rows
UNWIND rows AS row
MATCH (n:KGNode {{id:row.subject_id}})
MERGE (rep:KGNode {{id:row.id}})
SET rep.kind='core:Representation',
    rep.state='generated-unreviewed-xbuild-hints',
    rep.namespace='t6',
    rep.size_bytes=row.size_bytes,
    rep.build_id={qs(BUILD)},
    rep.producer='Ghidra',
    rep.address_space='va',
    rep.address_start=row.address_start,
    rep.semantic_name_state=row.semantic_name_state,
    rep.evidence_id=e.id,
    rep.artifact_id={qs(ART)},
    rep.representation_type='pseudocode:c:ghidra',
    rep.language='c-like',
    rep.revision=2,
    rep.content_sha256=row.content_sha256,
    rep.decompiler_body_sha256=row.decompiler_body_sha256,
    rep.source_text=row.source_text,
    rep.repo='lizardpeter/bo2-t6-assets',
    rep.repo_commit={qs(a.repo_commit)},
    rep.workflow_run_id={a.workflow_run_id},
    rep.subject_id=row.subject_id,
    rep.producer_version='12.1.3',
    rep.bundle_sha256={qs(a.bundle_sha256)},
    rep.bundle_member=row.bundle_member,
    rep.ghidra_name=row.ghidra_name,
    rep.validation_gate='exact-retail-entry+provenance-safe-xbuild-hint'
MERGE (n)-[:`core:HAS_REPRESENTATION`]->(rep)
MERGE (e)-[:EVIDENCE_FOR]->(rep)
"""
        p=a.out_dir/f"representations_{i//a.chunk_size:04d}.cypher"
        p.write_text(q,encoding="utf-8")
        files.append(p.name)

    manifest={
        "format":"t6-enriched-ghidra-uregraph-projection-v1",
        "workflow_run_id":a.workflow_run_id,
        "shard":a.shard,
        "full_shard_functions":len(results),
        "xbuild_affected_functions":len(affected),
        "revision2_representations":len(rows),
        "chunk_size":a.chunk_size,
        "corpus_file":"corpus.cypher",
        "representation_files":files,
        "proof_boundary":"Revision-2 source text is emitted only for decompiler-visible xbuild impact; the complete full-shard rerun remains retained as external generated evidence.",
    }
    (a.out_dir/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
