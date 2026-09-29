MATCH (b:KGNode {id:"urn:ure:t6:re_Build:current-client-sha77031817"})
MATCH (a:KGNode {id:"urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"})
MERGE (e:KGNode {id:"urn:ure:t6:re_Evidence:current-client-ghidra-low-hanging-v1"})
SET e.kind='re:Evidence', e.namespace='t6',
    e.name='T6 current-client Ghidra low-hanging corpus v1',
    e.status='generated-unreviewed-exact-client-evidence',
    e.client_sha256='770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf',
    e.ghidra_version='12.1.3',
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit='9eef5bf4636980a581faf3e93e0b4f8e0f06f9f5',
    e.catalog_path='proof/current_client/ghidra_low_hanging_v1/catalog.tsv',
    e.selection_path='proof/current_client/ghidra_low_hanging_v1/low_hanging.tsv',
    e.summary_path='proof/current_client/ghidra_low_hanging_v1/summary.json',
    e.bundle_path='proof/current_client/ghidra_low_hanging_v1/bundle.tar.zst.part-000',
    e.bundle_sha256='1d2678b7c1d9cdcff93e81b83cea2d674cfcc169c058cf792d2358b87987f8e2',
    e.catalog_function_count=24617,
    e.selected_function_count=3000,
    e.decompile_completed_count=3000,
    e.proof_boundary='Generated/unreviewed Ghidra evidence only. No decompiled body is reconstructed source or semantic completion until independently reviewed and promoted as an immutable Representation.'
MERGE (e)-[:TARGETS_BUILD]->(b)
MERGE (e)-[:EVIDENCE_FOR]->(a)
RETURN e.id
