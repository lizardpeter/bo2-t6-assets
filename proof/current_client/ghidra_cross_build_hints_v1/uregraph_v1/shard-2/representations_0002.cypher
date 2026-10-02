MATCH (e:KGNode {id:"urn:ure:t6:evidence:whole-program-ghidra-xbuild-hints-36988725442:shard:2"})
WITH e,[{subject_id:"urn:ure:t6:occ:function:current-client:0064a670",id:"urn:ure:t6:representation:pseudocode:c:ghidra-xbuild-hints:0064a670:f3a41dc63d098ea8e956b8cad600a5d0cd472f9c8af35136b2d76ef6fad2a99b",address_start:"0x0064A670",ghidra_name:"FUN_0064a670",source_text:"/* GENERATED/UNREVIEWED GHIDRA OUTPUT -- NOT RECONSTRUCTED SOURCE\n * function_id: urn:ure:t6:occ:function:current-client:0064a670\n * requested_va: 0x0064a670\n * tier: xbuild-enriched-full\n * exact_current_client_sha256: 770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf\n * entry_point: 0064a670\n * ghidra_name: FUN_0064a670\n * decompile_completed: true\n * decompiler_message: \n */\n\n\nvoid __fastcall FUN_0064a670(undefined4 *param_1)\n\n{\n  int iVar1;\n  \n  for (iVar1 = param_1[2]; iVar1 != 0; iVar1 = iVar1 + -1) {\n    xbuild_dtor_bdString__00a2ea20();\n  }\n  FUN_00a2cb50(*param_1);\n  *param_1 = 0;\n  param_1[2] = 0;\n  param_1[1] = 0;\n  return;\n}\n\n",content_sha256:"f3a41dc63d098ea8e956b8cad600a5d0cd472f9c8af35136b2d76ef6fad2a99b",decompiler_body_sha256:"43fc4c975c819608e9990b77c4b4fad9cd8d1eaeaeb8986ba8747b1f07df4fb6",size_bytes:661,bundle_member:"unreviewed/0064a670.c",semantic_name_state:"retail-analysis-affected-by-cross-build-hint"}] AS rows
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
    rep.bundle_sha256="51b9bcd496f2fb98ef274c306e17372380eab65623b1c9cfe8b37229de240532",
    rep.bundle_member=row.bundle_member,
    rep.ghidra_name=row.ghidra_name,
    rep.validation_gate='exact-retail-entry+provenance-safe-xbuild-hint'
MERGE (n)-[:`core:HAS_REPRESENTATION`]->(rep)
MERGE (e)-[:EVIDENCE_FOR]->(rep)
