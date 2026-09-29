#!/usr/bin/env python3
"""Build exact-byte current-client <-> server/PDB correspondence evidence.

This is the graph-producing successor to join_t6_current_client_pdb_exact_hashes_v1.py.

Proof boundary:
- Exact equality of complete Ghidra function instruction-byte SHA-256 values is a
  strong cross-build implementation-identity witness.
- A hash that resolves to more than one server/PDB variant is ambiguous and is
  retained as candidate evidence only.
- No address, symbol-name, object-name, or family-name similarity is sufficient
  for acceptance by this tool.
- Accepted correspondence does not assert that every server type/global/source
  property transfers unchanged to the client. Those remain separate evidence gates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

FORMAT = "t6-current-client-pdb-exact-hash-join-v2"
CLIENT_BUILD_ID = "urn:ure:t6:re_Build:current-client-sha77031817"
CLIENT_ARTIFACT_ID = "urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"
CLIENT_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SERVER_PDB_SHA256 = "7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc"


def cypher_value(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict):
        return "{" + ",".join(f"{k}:{cypher_value(x)}" for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ",".join(cypher_value(x) for x in v) + "]"
    raise TypeError(type(v))


def read_tsv(path: Path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, dialect="excel-tab"))


def normalized_va(v: str) -> str:
    return v.lower().removeprefix("0x").zfill(8)


def client_occurrence_id(va: str) -> str:
    return "urn:ure:t6:occ:function:current-client:" + normalized_va(va)


def evidence_id(client_id: str, variant_id: str, digest: str) -> str:
    key = (client_id + "\0" + variant_id + "\0" + digest).encode()
    return "urn:ure:t6:re_Evidence:current-client-server-exact-hash:" + hashlib.sha256(key).hexdigest()[:24]


def build_matches(client_rows, server_rows):
    by_hash = defaultdict(list)
    for row in server_rows:
        digest = (row.get("exact_bytes_sha256") or "").strip().lower()
        if digest:
            by_hash[digest].append(row)

    matches = []
    current_functions_with_match = set()
    ambiguous_client_hashes = 0
    accepted_unique = 0

    for c in client_rows:
        digest = (c.get("instruction_bytes_sha256") or "").strip().lower()
        if not digest:
            continue
        hits = by_hash.get(digest, [])
        if not hits:
            continue

        current_id = client_occurrence_id(c["entry_va"])
        current_functions_with_match.add(current_id)
        if len(hits) > 1:
            ambiguous_client_hashes += 1

        for s in hits:
            state = (
                "accepted-exact-byte-identity-witness"
                if len(hits) == 1
                else "candidate-ambiguous-exact-byte-hash"
            )
            if len(hits) == 1:
                accepted_unique += 1

            variant_id = s["variant_id"]
            matches.append(
                {
                    "evidence_id": evidence_id(current_id, variant_id, digest),
                    "current_client_id": current_id,
                    "current_client_va": "0x" + normalized_va(c["entry_va"]),
                    "current_client_hash": digest,
                    "current_client_ghidra_name": c.get("name") or "",
                    "server_variant_id": variant_id,
                    "server_family_id": s.get("family_id") or "",
                    "server_symbol_name": s.get("symbol_name") or "",
                    "server_object_name": s.get("object_name") or "",
                    "server_address_start": s.get("exact_address_start") or "",
                    "server_size_bytes": int(s["exact_size_bytes"]) if s.get("exact_size_bytes") else None,
                    "server_hash_multiplicity": len(hits),
                    "identity_basis": "exact-function-instruction-bytes-sha256-across-builds",
                    "state": state,
                }
            )

    return matches, {
        "match_rows": len(matches),
        "current_client_functions_with_match": len(current_functions_with_match),
        "ambiguous_current_client_hashes": ambiguous_client_hashes,
        "accepted_unique_match_rows": accepted_unique,
    }


def write_graph_projection(out_dir: Path, matches, chunk_size: int):
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []

    for offset in range(0, len(matches), chunk_size):
        batch = matches[offset : offset + chunk_size]
        payload = cypher_value(batch)
        q = f"""WITH {payload} AS rows
UNWIND rows AS row
MATCH (c:KGNode {{id:row.current_client_id}})
MATCH (v:KGNode {{id:row.server_variant_id}})
MERGE (e:KGNode {{id:row.evidence_id}})
SET e.kind='re:Evidence',
    e.namespace='t6',
    e.evidence_kind='cross-build-exact-instruction-byte-hash',
    e.state=row.state,
    e.identity_basis=row.identity_basis,
    e.client_build_id='{CLIENT_BUILD_ID}',
    e.client_artifact_id='{CLIENT_ARTIFACT_ID}',
    e.client_sha256='{CLIENT_SHA256}',
    e.server_pdb_sha256='{SERVER_PDB_SHA256}',
    e.current_client_va=row.current_client_va,
    e.current_client_hash=row.current_client_hash,
    e.server_variant_id=row.server_variant_id,
    e.server_family_id=row.server_family_id,
    e.server_symbol_name=row.server_symbol_name,
    e.server_object_name=row.server_object_name,
    e.server_address_start=row.server_address_start,
    e.server_size_bytes=row.server_size_bytes,
    e.server_hash_multiplicity=row.server_hash_multiplicity,
    e.producer='{FORMAT}',
    e.proof_boundary='Exact complete instruction-byte hash equality is an implementation identity witness. Duplicate server hashes stay candidate-only. This evidence does not automatically transfer all server types/globals/source semantics to the client.'
MERGE (e)-[:EVIDENCE_FOR]->(c)
MERGE (e)-[:EVIDENCE_FOR]->(v)
FOREACH (_ IN CASE WHEN row.state='accepted-exact-byte-identity-witness' THEN [1] ELSE [] END |
  MERGE (c)-[r:CROSSBUILD_CORRESPONDS_TO]->(v)
  SET r.state=row.state,
      r.basis=row.identity_basis,
      r.evidence_id=row.evidence_id,
      r.client_hash=row.current_client_hash,
      r.server_pdb_sha256='{SERVER_PDB_SHA256}',
      r.producer='{FORMAT}'
)
"""
        path = out_dir / f"exact_hash_correspondence_{offset // chunk_size:04d}.cypher"
        path.write_text(q, encoding="utf-8")
        files.append(path.name)

    manifest = {
        "format": "uregraph-cypher-chunk-manifest-v1",
        "source_format": FORMAT,
        "graph": "uregraph",
        "client_build_id": CLIENT_BUILD_ID,
        "client_artifact_id": CLIENT_ARTIFACT_ID,
        "client_sha256": CLIENT_SHA256,
        "server_pdb_sha256": SERVER_PDB_SHA256,
        "chunk_size": chunk_size,
        "rows": len(matches),
        "files": files,
        "proof_boundary": (
            "Unique exact complete instruction-byte hash matches create accepted "
            "CROSSBUILD_CORRESPONDS_TO witnesses. Ambiguous duplicate-hash rows create "
            "Evidence only and are not accepted correspondences."
        ),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--pdb-hashes", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--uregraph-out-dir", type=Path)
    ap.add_argument("--chunk-size", type=int, default=250)
    args = ap.parse_args()

    client_rows = read_tsv(args.catalog)
    server_rows = read_tsv(args.pdb_hashes)
    matches, stats = build_matches(client_rows, server_rows)

    doc = {
        "format": FORMAT,
        "authority": (
            "SHA-pinned current-client Ghidra instruction bytes joined to exact "
            "PDB-sized server function bytes"
        ),
        "current_client_catalog_functions": len(client_rows),
        "server_pdb_exact_hash_variants": len(server_rows),
        **stats,
        "client_sha256": CLIENT_SHA256,
        "server_pdb_sha256": SERVER_PDB_SHA256,
        "matches": matches,
        "proof_boundary": (
            "Exact complete instruction-byte SHA-256 equality is strong cross-build "
            "implementation identity evidence. Duplicate hashes remain candidate-only. "
            "No address/name-only identity is admitted and server semantics do not "
            "automatically transfer without their own evidence."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.uregraph_out_dir:
        doc["uregraph_projection"] = write_graph_projection(
            args.uregraph_out_dir, matches, args.chunk_size
        )

    print(json.dumps(stats, sort_keys=True))


if __name__ == "__main__":
    main()
