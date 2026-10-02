MERGE (e:KGNode {id:"urn:ure:t6:evidence:whole-program-ghidra-xbuild-hints-36988725442:shard:6"})
SET e.kind='re:Evidence',
    e.namespace='t6',
    e.status='generated-unreviewed',
    e.build_id="urn:ure:t6:re_Build:current-client-sha77031817",
    e.artifact_id="urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa",
    e.client_sha256="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf",
    e.repo='lizardpeter/bo2-t6-assets',
    e.repo_commit="ecee4bc1642daccf52e1e6d8540158f0158b10b3",
    e.workflow_run_id=36988725442,
    e.ghidra_version='12.1.3',
    e.shard=6,
    e.full_shard_function_count=3078,
    e.xbuild_affected_representation_count=161,
    e.bundle_sha256="42b932a493179c26bbf75983f7a0596763157cede16fb6b7922db448e0b2eb06",
    e.proof_boundary='Exact current-client generated Ghidra evidence. Server MAP/PDB is cross-build hint evidence only; no server prototype, type, global, source layout, or address-delta fact is promoted.'
RETURN e.id
