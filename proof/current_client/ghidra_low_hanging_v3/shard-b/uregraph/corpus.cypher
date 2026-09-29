MATCH (b:KGNode {id:"urn:ure:t6:re_Build:current-client-sha77031817"})
MATCH (a:KGNode {id:"urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"})
MERGE (e:KGNode {id:"urn:ure:t6:re_Evidence:current-client-ghidra-low-hanging-v3-shard-b"})
SET e.kind='re:Evidence', e.namespace='t6',
    e.name="T6 current-client Ghidra low-hanging corpus v3 shard b",
    e.status='generated-unreviewed-exact-client-evidence',
    e.client_sha256='770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf',
    e.ghidra_version='12.1.3',
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit="4e9e2cb2ad28c08e000de2b8742654522f48ab9c",
    e.selection_path="proof/current_client/ghidra_low_hanging_v3/shard-b/selection.tsv",
    e.results_path="proof/current_client/ghidra_low_hanging_v3/shard-b/results.tsv",
    e.summary_path="proof/current_client/ghidra_low_hanging_v3/shard-b/summary.json",
    e.bundle_path="proof/current_client/ghidra_low_hanging_v3/shard-b/bundle.tar.zst",
    e.bundle_sha256="b589dd4b04599b9680787f57d2f33137a57be21f1309ed51def91fd25fd58881",
    e.selected_function_count=4500,
    e.decompile_completed_count=4500,
    e.decompile_failed_count=0,
    e.proof_boundary='Generated/unreviewed Ghidra evidence only. No decompiled body is reconstructed source or semantic completion until independently reviewed and promoted.'
MERGE (e)-[:TARGETS_BUILD]->(b)
MERGE (e)-[:EVIDENCE_FOR]->(a)
RETURN e.id
