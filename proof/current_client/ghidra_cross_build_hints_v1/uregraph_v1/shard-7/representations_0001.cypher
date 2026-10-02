MATCH (e:KGNode {id:"urn:ure:t6:evidence:whole-program-ghidra-xbuild-hints-36988725442:shard:7"})
WITH e,[{subject_id:"urn:ure:t6:occ:function:current-client:00ae1d30",id:"urn:ure:t6:representation:pseudocode:c:ghidra-xbuild-hints:00ae1d30:728990f97dab4a29d1bd79125434edc106a28010d18d5dec58338bd59acb72bb",address_start:"0x00AE1D30",ghidra_name:"xbuild_fn_9bdSequenceNumber__00ae1d30",source_text:"/* GENERATED/UNREVIEWED GHIDRA OUTPUT -- NOT RECONSTRUCTED SOURCE\n * function_id: urn:ure:t6:occ:function:current-client:00ae1d30\n * requested_va: 0x00ae1d30\n * tier: xbuild-enriched-full\n * exact_current_client_sha256: 770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf\n * entry_point: 00ae1d30\n * ghidra_name: xbuild_fn_9bdSequenceNumber__00ae1d30\n * decompile_completed: true\n * decompiler_message: \n */\n\n\nundefined4 __thiscall xbuild_fn_9bdSequenceNumber__00ae1d30(int *param_1,int *param_2)\n\n{\n  return CONCAT31((int3)((uint)*param_1 >> 8),*param_1 != *param_2);\n}\n\n",content_sha256:"728990f97dab4a29d1bd79125434edc106a28010d18d5dec58338bd59acb72bb",decompiler_body_sha256:"c43a07a9fb6660c25742888cf6643a26961635493b4754b4cf2f0cc1685c53ab",size_bytes:585,bundle_member:"unreviewed/00ae1d30.c",semantic_name_state:"cross-build-hint-only"},{subject_id:"urn:ure:t6:occ:function:current-client:00ae1d80",id:"urn:ure:t6:representation:pseudocode:c:ghidra-xbuild-hints:00ae1d80:c4b4784675fb23bdf86b1d86a6854735f8643bb1e005c2f6e8cf4610e7eb0c4f",address_start:"0x00AE1D80",ghidra_name:"xbuild_ctor_bdSequenceNumberStore__00ae1d80",source_text:"/* GENERATED/UNREVIEWED GHIDRA OUTPUT -- NOT RECONSTRUCTED SOURCE\n * function_id: urn:ure:t6:occ:function:current-client:00ae1d80\n * requested_va: 0x00ae1d80\n * tier: xbuild-enriched-full\n * exact_current_client_sha256: 770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf\n * entry_point: 00ae1d80\n * ghidra_name: xbuild_ctor_bdSequenceNumberStore__00ae1d80\n * decompile_completed: true\n * decompiler_message: \n */\n\n\nvoid __thiscall xbuild_ctor_bdSequenceNumberStore__00ae1d80(undefined4 *param_1,undefined4 *param_2)\n\n{\n  *param_1 = 0;\n  param_1[1] = *param_2;\n  return;\n}\n\n",content_sha256:"c4b4784675fb23bdf86b1d86a6854735f8643bb1e005c2f6e8cf4610e7eb0c4f",decompiler_body_sha256:"a9f50aa4a44a0eab3d4900f0e3a2dedb661530624dfaecb197574c3859797a78",size_bytes:587,bundle_member:"unreviewed/00ae1d80.c",semantic_name_state:"cross-build-hint-only"}] AS rows
UNWIND rows AS row
MATCH (n:KGNode {id:row.subject_id})
MERGE (rep:KGNode {id:row.id})
SET rep.kind='core:Representation',
    rep.state='generated-unreviewed-xbuild-hints',
    rep.namespace='t6',
    rep.size_bytes=row.size_bytes,
    rep.build_id="urn:ure:t6:re_Build:current-client-sha77031817",
    rep.producer='Ghidra',
    rep.address_space='va',
    rep.address_start=row.address_start,
    rep.semantic_name_state=row.semantic_name_state,
    rep.evidence_id=e.id,
    rep.artifact_id="urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa",
    rep.representation_type='pseudocode:c:ghidra',
    rep.language='c-like',
    rep.revision=2,
    rep.content_sha256=row.content_sha256,
    rep.decompiler_body_sha256=row.decompiler_body_sha256,
    rep.source_text=row.source_text,
    rep.repo='lizardpeter/bo2-t6-assets',
    rep.repo_commit="ecee4bc1642daccf52e1e6d8540158f0158b10b3",
    rep.workflow_run_id=36988725442,
    rep.subject_id=row.subject_id,
    rep.producer_version='12.1.3',
    rep.bundle_sha256="70e9e93fc113dc7d1b17d667ec5af2afef9869b0c3e6a7c974027efe8244348f",
    rep.bundle_member=row.bundle_member,
    rep.ghidra_name=row.ghidra_name,
    rep.validation_gate='exact-retail-entry+provenance-safe-xbuild-hint'
MERGE (n)-[:`core:HAS_REPRESENTATION`]->(rep)
MERGE (e)-[:EVIDENCE_FOR]->(rep)
