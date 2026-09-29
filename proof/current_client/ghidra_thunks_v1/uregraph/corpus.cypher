MATCH (b:KGNode {id:"urn:ure:t6:re_Build:current-client-sha77031817"})
MATCH (a:KGNode {id:"urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"})
MERGE (e:KGNode {id:"urn:ure:t6:re_Evidence:current-client-ghidra-thunks-v1"})
SET e.kind='re:Evidence', e.namespace='t6',
    e.name="T6 current-client Ghidra thunk corpus v1",
    e.status='generated-unreviewed-exact-client-evidence',
    e.client_sha256='770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf',
    e.ghidra_version='12.1.3',
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit="ae56f3519a9c55895d0efdb3c00d5f6aee4062bb",
    e.selection_path="proof/current_client/ghidra_thunks_v1/selection.tsv",
    e.results_path="proof/current_client/ghidra_thunks_v1/results.tsv",
    e.summary_path="proof/current_client/ghidra_thunks_v1/summary.json",
    e.bundle_path="proof/current_client/ghidra_thunks_v1/bundle.tar.zst",
    e.bundle_sha256="0a6d913400b723d2324d692ee28acf4639470df21e6eb3d24372059cac67610f",
    e.selected_function_count=169,
    e.decompile_completed_count=169,
    e.decompile_failed_count=0,
    e.proof_boundary='Generated/unreviewed Ghidra evidence only. No decompiled body is reconstructed source or semantic completion until independently reviewed and promoted.'
MERGE (e)-[:TARGETS_BUILD]->(b)
MERGE (e)-[:EVIDENCE_FOR]->(a)
RETURN e.id
