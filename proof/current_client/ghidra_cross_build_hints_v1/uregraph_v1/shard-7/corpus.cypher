MERGE (e:KGNode {id:"urn:ure:t6:evidence:whole-program-ghidra-xbuild-hints-36988725442:shard:7"})
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
    e.shard=7,
    e.full_shard_function_count=3071,
    e.xbuild_affected_representation_count=22,
    e.bundle_sha256="70e9e93fc113dc7d1b17d667ec5af2afef9869b0c3e6a7c974027efe8244348f",
    e.proof_boundary='Exact current-client generated Ghidra evidence. Server MAP/PDB is cross-build hint evidence only; no server prototype, type, global, source layout, or address-delta fact is promoted.'
RETURN e.id
