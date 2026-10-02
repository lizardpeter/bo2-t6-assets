MATCH (e:KGNode {id:"urn:ure:t6:evidence:whole-program-ghidra-xbuild-hints-36988725442:shard:6"})
WITH e,[{subject_id:"urn:ure:t6:occ:function:current-client:00a5d870",id:"urn:ure:t6:representation:pseudocode:c:ghidra-xbuild-hints:00a5d870:975aa3b3f3f23a6f91f60b79f6f6924985514267955aa333367a992cf719876e",address_start:"0x00A5D870",ghidra_name:"FUN_00a5d870",source_text:"/* GENERATED/UNREVIEWED GHIDRA OUTPUT -- NOT RECONSTRUCTED SOURCE\n * function_id: urn:ure:t6:occ:function:current-client:00a5d870\n * requested_va: 0x00a5d870\n * tier: xbuild-enriched-full\n * exact_current_client_sha256: 770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf\n * entry_point: 00a5d870\n * ghidra_name: FUN_00a5d870\n * decompile_completed: true\n * decompiler_message: \n */\n\n\n/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */\n\nundefined4 * __thiscall\nFUN_00a5d870(undefined4 *param_1,undefined4 *param_2,undefined4 *param_3,undefined4 param_4)\n\n{\n  uint uVar1;\n  LONG LVar2;\n  int *unaff_FS_OFFSET;\n  int iStack_10;\n  undefined1 *puStack_c;\n  int iStack_8;\n  \n  puStack_c = &LAB_00b4cd86;\n  iStack_10 = *unaff_FS_OFFSET;\n  uVar1 = _DAT_010528f0 ^ (uint)&stack0xfffffffc;\n  *unaff_FS_OFFSET = (int)&iStack_10;\n  iStack_8 = 0;\n  *param_1 = 1;\n  param_1[1] = param_2;\n  if (param_2 != (undefined4 *)0x0) {\n    InterlockedIncrement(param_2 + 1);\n  }\n  param_1[2] = param_3;\n  if (param_3 != (undefined4 *)0x0) {\n    InterlockedIncrement(param_3 + 1);\n  }\n  iStack_8._0_1_ = 3;\n  param_1[3] = param_4;\n  param_1[4] = 0;\n  param_1[5] = 0;\n  xbuild_ctor_bdStopwatch__00ae0fc0(uVar1);\n  *(undefined1 *)(param_1 + 8) = 0;\n  xbuild_ctor_bdStopwatch__00ae0fc0();\n  iStack_8 = (uint)iStack_8._1_3_ << 8;\n  if (((param_2 != (undefined4 *)0x0) && (LVar2 = InterlockedDecrement(param_2 + 1), LVar2 == 0)) &&\n     (param_2 != (undefined4 *)0x0)) {\n    (**(code **)*param_2)(1);\n  }\n  iStack_8 = 0xffffffff;\n  if (((param_3 != (undefined4 *)0x0) && (LVar2 = InterlockedDecrement(param_3 + 1), LVar2 == 0)) &&\n     (param_3 != (undefined4 *)0x0)) {\n    (**(code **)*param_3)(1);\n  }\n  *unaff_FS_OFFSET = iStack_10;\n  return param_1;\n}\n\n",content_sha256:"975aa3b3f3f23a6f91f60b79f6f6924985514267955aa333367a992cf719876e",decompiler_body_sha256:"890e06f7db86aca0b2c3b7d10182b9f0218233f2a915c1f87f5ced13b7a82a6b",size_bytes:1775,bundle_member:"unreviewed/00a5d870.c",semantic_name_state:"retail-analysis-affected-by-cross-build-hint"}] AS rows
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
    rep.bundle_sha256="42b932a493179c26bbf75983f7a0596763157cede16fb6b7922db448e0b2eb06",
    rep.bundle_member=row.bundle_member,
    rep.ghidra_name=row.ghidra_name,
    rep.validation_gate='exact-retail-entry+provenance-safe-xbuild-hint'
MERGE (n)-[:`core:HAS_REPRESENTATION`]->(rep)
MERGE (e)-[:EVIDENCE_FOR]->(rep)
