MATCH (b:KGNode {id:"urn:ure:t6:re_Build:current-client-sha77031817"})
MATCH (a:KGNode {id:"urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"})
MERGE (e:KGNode {id:"urn:ure:t6:re_Evidence:current-client-ghidra-low-hanging-v2"})
SET e.kind='re:Evidence', e.namespace='t6',
    e.name="T6 current-client Ghidra low-hanging corpus v2",
    e.status='generated-unreviewed-exact-client-evidence',
    e.client_sha256='770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf',
    e.ghidra_version='12.1.3',
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit="1a2de7c05b8fdffd55a3610bc817e09189f47e76",
    e.selection_path="proof/current_client/ghidra_low_hanging_v2/selection.tsv",
    e.results_path="proof/current_client/ghidra_low_hanging_v2/results.tsv",
    e.summary_path="proof/current_client/ghidra_low_hanging_v2/summary.json",
    e.bundle_path="proof/current_client/ghidra_low_hanging_v2/bundle.tar.zst.part-000",
    e.bundle_sha256="0e94403bd8c2db0f20c177403fdff2da0c5f0a4009d2fd14f2a16c4de9b412d9",
    e.selected_function_count=5000,
    e.decompile_completed_count=4997,
    e.decompile_failed_count=3,
    e.proof_boundary='Generated/unreviewed Ghidra evidence only. No decompiled body is reconstructed source or semantic completion until independently reviewed and promoted.'
MERGE (e)-[:TARGETS_BUILD]->(b)
MERGE (e)-[:EVIDENCE_FOR]->(a)
RETURN e.id
