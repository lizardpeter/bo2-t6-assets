MATCH (b:KGNode {id:"urn:ure:t6:re_Build:current-client-sha77031817"})
MATCH (a:KGNode {id:"urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"})
MERGE (e:KGNode {id:"urn:ure:t6:re_Evidence:current-client-pdb-exact-hash-join-v1"})
SET e.kind='re:Evidence',
    e.namespace='t6',
    e.name='T6 current-client <-> server PDB exact instruction-byte hash join v1',
    e.evidence_type='cross-build-exact-function-instruction-byte-hash-corpus',
    e.state='generated-exact-evidence',
    e.format='t6-current-client-pdb-exact-hash-join-v1',
    e.current_client_catalog_functions=24617,
    e.server_pdb_exact_hash_variants=7180,
    e.match_rows=849,
    e.current_client_functions_with_match=321,
    e.ambiguous_current_client_hashes=41,
    e.ambiguous_current_client_functions=52,
    e.proof_boundary='Exact instruction-byte hash equality is strong cross-build identity evidence. Hashes duplicated on either side remain candidates and are not auto-corresponded. No address/name-only identity is admitted.'
MERGE (e)-[:TARGETS_BUILD]->(b)
MERGE (e)-[:EVIDENCE_FOR]->(a)
RETURN e.id
