MERGE (e:KGNode {id:"urn:ure:t6:evidence:whole-program-ghidra-xbuild-hints-36988725442:shard:5"})
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
    e.shard=5,
    e.full_shard_function_count=3078,
    e.xbuild_affected_representation_count=24,
    e.bundle_sha256="4e3c7428b9827f27afa0fc33bc29e0a6c6e1fa025fb3b00659637d5f8c6513a3",
    e.proof_boundary='Exact current-client generated Ghidra evidence. Server MAP/PDB is cross-build hint evidence only; no server prototype, type, global, source layout, or address-delta fact is promoted.'
RETURN e.id
