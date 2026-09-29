#!/usr/bin/env python3
"""Build a high-confidence current-client <-> MAP/PDB cross-build join plan.

Input 1: exact current-client Ghidra catalog TSV (entry + instruction byte SHA-256).
Input 2: server/PDB exact-hash export TSV generated from uregraph.

Exact byte-hash equality is emitted as an identity witness, not as an address/name merge.

Optional graph projection:
- every exact-hash hit becomes a deterministic re:Evidence node linked to the
  current-client FunctionOccurrence and server FunctionVariant;
- only a server hash with multiplicity 1 creates CROSSBUILD_CORRESPONDS_TO;
- duplicate server hashes remain candidate evidence and are never auto-promoted.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import defaultdict
from pathlib import Path

FORMAT="t6-current-client-pdb-exact-hash-join-v1"
BUILD_ID="urn:ure:t6:re_Build:current-client-sha77031817"
ARTIFACT_ID="urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"
CORPUS_ID="urn:ure:t6:re_Evidence:current-client-pdb-exact-hash-join-v1"

def cypher_literal(v):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v,(int,float)):
        return str(v)
    if isinstance(v,str):
        return json.dumps(v,ensure_ascii=False)
    if isinstance(v,list):
        return "["+",".join(cypher_literal(x) for x in v)+"]"
    if isinstance(v,dict):
        return "{"+",".join(f"{k}:{cypher_literal(val)}" for k,val in v.items())+"}"
    raise TypeError(type(v))

def current_id(va):
    s=va.lower().removeprefix("0x").zfill(8)
    return f"urn:ure:t6:occ:function:current-client:{s}"

def evidence_id(client_id,variant_id,h):
    d=hashlib.sha256((client_id+"\0"+variant_id+"\0"+h).encode()).hexdigest()[:20]
    return f"urn:ure:t6:re_Evidence:current-client-pdb-exact-hash:{d}"

def write_cypher(out_dir:Path,matches:list[dict],catalog_count:int,server_count:int,chunk_size:int):
    out_dir.mkdir(parents=True,exist_ok=True)
    corpus=f"""MATCH (b:KGNode {{id:{cypher_literal(BUILD_ID)}}})
MATCH (a:KGNode {{id:{cypher_literal(ARTIFACT_ID)}}})
MERGE (e:KGNode {{id:{cypher_literal(CORPUS_ID)}}})
SET e.kind='re:Evidence',
    e.namespace='t6',
    e.name='T6 current-client <-> server PDB exact instruction-byte hash join v1',
    e.evidence_type='cross-build-exact-function-instruction-byte-hash-corpus',
    e.state='generated-exact-evidence',
    e.format='{FORMAT}',
    e.current_client_catalog_functions={catalog_count},
    e.server_pdb_exact_hash_variants={server_count},
    e.match_rows={len(matches)},
    e.current_client_functions_with_match={len(set(x["current_client_va"] for x in matches))},
    e.ambiguous_current_client_hashes={len(set(x["current_client_va"] for x in matches if x["server_hash_multiplicity"]>1))},
    e.proof_boundary='Exact instruction-byte hash equality is strong cross-build identity evidence. Duplicate server hashes remain candidates and are not auto-corresponded. No address/name-only identity is admitted.'
MERGE (e)-[:TARGETS_BUILD]->(b)
MERGE (e)-[:EVIDENCE_FOR]->(a)
RETURN e.id
"""
    (out_dir/"corpus.cypher").write_text(corpus,encoding="utf-8")

    rows=[]
    for m in matches:
        cid=current_id(m["current_client_va"])
        rows.append({
          "evidence_id":evidence_id(cid,m["server_variant_id"],m["current_client_hash"]),
          "client_id":cid,
          "server_variant_id":m["server_variant_id"],
          "server_family_id":m["server_family_id"],
          "hash":m["current_client_hash"],
          "ghidra_name":m["current_client_ghidra_name"],
          "server_symbol_name":m["server_symbol_name"],
          "server_object_name":m["server_object_name"],
          "server_address_start":m["server_address_start"],
          "server_size_bytes":int(m["server_size_bytes"]) if str(m["server_size_bytes"]).strip() else None,
          "multiplicity":int(m["server_hash_multiplicity"]),
          "state":m["state"],
          "accepted":int(m["server_hash_multiplicity"])==1,
        })
    files=[]
    for start in range(0,len(rows),chunk_size):
        batch=rows[start:start+chunk_size]
        payload=cypher_literal(batch)
        q=f"""MATCH (corpus:KGNode {{id:{cypher_literal(CORPUS_ID)}}})
WITH corpus,{payload} AS rows
UNWIND rows AS row
MATCH (c:KGNode {{id:row.client_id}})
MATCH (v:KGNode {{id:row.server_variant_id}})
MERGE (e:KGNode {{id:row.evidence_id}})
SET e.kind='re:Evidence',
    e.namespace='t6',
    e.evidence_type='cross-build-exact-function-instruction-byte-hash',
    e.state=row.state,
    e.current_client_id=row.client_id,
    e.server_variant_id=row.server_variant_id,
    e.server_family_id=row.server_family_id,
    e.instruction_bytes_sha256=row.hash,
    e.current_client_ghidra_name=row.ghidra_name,
    e.server_symbol_name=row.server_symbol_name,
    e.server_object_name=row.server_object_name,
    e.server_address_start=row.server_address_start,
    e.server_size_bytes=row.server_size_bytes,
    e.server_hash_multiplicity=row.multiplicity,
    e.identity_basis='exact-function-instruction-bytes-sha256-across-builds',
    e.proof_boundary=CASE WHEN row.accepted THEN 'Unique exact server-function instruction-byte hash witness; correspondence is accepted at the machine-body level but does not by itself prove all source-level type or ABI details.' ELSE 'Exact byte hash is duplicated among server variants; candidate evidence only and no correspondence edge is created.' END
MERGE (corpus)-[:CONTAINS_EVIDENCE]->(e)
MERGE (e)-[:EVIDENCE_FOR]->(c)
MERGE (e)-[:EVIDENCE_FOR]->(v)
FOREACH (_ IN CASE WHEN row.accepted THEN [1] ELSE [] END |
  MERGE (c)-[r:CROSSBUILD_CORRESPONDS_TO]->(v)
  SET r.state='accepted-exact-byte-identity-witness',
      r.identity_basis='exact-function-instruction-bytes-sha256-across-builds',
      r.instruction_bytes_sha256=row.hash,
      r.evidence_id=row.evidence_id,
      r.server_symbol_name=row.server_symbol_name,
      r.server_object_name=row.server_object_name
)
"""
        p=out_dir/f"matches_{start//chunk_size:04d}.cypher"
        p.write_text(q,encoding="utf-8")
        files.append(p.name)
    manifest={
      "format":"uregraph-cypher-chunk-manifest-v1",
      "sourceFormat":FORMAT,
      "graph":"uregraph",
      "corpusFile":"corpus.cypher",
      "matchFiles":files,
      "chunkSize":chunk_size,
      "matchRows":len(rows),
      "acceptedRows":sum(1 for x in rows if x["accepted"]),
      "candidateAmbiguousRows":sum(1 for x in rows if not x["accepted"]),
      "proofBoundary":"Every exact hit is retained as evidence. CROSSBUILD_CORRESPONDS_TO is emitted only for a unique server-side exact instruction-byte hash."
    }
    (out_dir/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--pdb-hashes",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--cypher-out-dir",type=Path)
    ap.add_argument("--chunk-size",type=int,default=250)
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
    doc={
      "format":FORMAT,
      "current_client_catalog_functions":len(cc),
      "server_pdb_exact_hash_variants":len(sv),
      "match_rows":len(matches),
      "current_client_functions_with_match":len(set(x["current_client_va"] for x in matches)),
      "ambiguous_current_client_hashes":ambiguous,
      "matches":matches,
      "proof_boundary":"Exact instruction-byte hash equality is strong cross-build identity evidence. Duplicate hashes remain candidate/ambiguous and are not auto-merged. No address/name-only identity is admitted."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if a.cypher_out_dir:
        write_cypher(a.cypher_out_dir,matches,len(cc),len(sv),a.chunk_size)
    print({
      "matches":len(matches),
      "current_client_functions":len(set(x["current_client_va"] for x in matches)),
      "ambiguous":ambiguous,
      "cypher_out_dir":str(a.cypher_out_dir) if a.cypher_out_dir else None,
    })
if __name__=="__main__": main()
