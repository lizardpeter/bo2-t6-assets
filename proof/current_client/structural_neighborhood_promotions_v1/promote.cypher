
MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va="0x00761200" AND struct.server_va="0x00a8b000"
MATCH (struct)-[:EVIDENCE_FOR]->(server:KGNode)
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:"urn:ure:t6:occ:function:current-client:00761200"})
MERGE (ev:KGNode {id:"urn:ure:t6:re_Evidence:structural-neighborhood-accepted:6f23126a2f3b973d33ed0494"})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va="0x00761200",
    ev.server_va="0x00a8b000",
    ev.server_symbol="?R_RegisterSunDvars@@YAXXZ",
    ev.server_object="gfx_d3d:r_sky.obj",
    ev.basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    ev.structural_schemes="coarse_flow;coarse_profile;fine_flow;fine_profile;mnemonic_flow",
    ev.exact_anchor_callee_matches=0,
    ev.shared_unique_strings=22,
    ev.call_count=21,
    ev.data_ref_offset_count=102,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit="c48086ffa9ebae04d083aabda6e43f7ab29474e5",
    ev.workflow_run_id=36998585457,
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    client.cross_build_identity_evidence_id=ev.id


MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va="0x00573290" AND struct.server_va="0x0079ebd0"
MATCH (struct)-[:EVIDENCE_FOR]->(server:KGNode)
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:"urn:ure:t6:occ:function:current-client:00573290"})
MERGE (ev:KGNode {id:"urn:ure:t6:re_Evidence:structural-neighborhood-accepted:976ee5fc4025db6f5fe106af"})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va="0x00573290",
    ev.server_va="0x0079ebd0",
    ev.server_symbol="?Voice_Init@@YA_NXZ",
    ev.server_object="win_voice.obj",
    ev.basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    ev.structural_schemes="coarse_flow;coarse_profile;fine_flow;fine_profile;mnemonic_flow",
    ev.exact_anchor_callee_matches=0,
    ev.shared_unique_strings=6,
    ev.call_count=19,
    ev.data_ref_offset_count=35,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit="c48086ffa9ebae04d083aabda6e43f7ab29474e5",
    ev.workflow_run_id=36998585457,
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    client.cross_build_identity_evidence_id=ev.id


MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va="0x00440c10" AND struct.server_va="0x00561a80"
MATCH (struct)-[:EVIDENCE_FOR]->(server:KGNode)
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:"urn:ure:t6:occ:function:current-client:00440c10"})
MERGE (ev:KGNode {id:"urn:ure:t6:re_Evidence:structural-neighborhood-accepted:8bf0c706a0cb7d8ff954a08b"})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va="0x00440c10",
    ev.server_va="0x00561a80",
    ev.server_symbol="??0dwQoSMultiProbeListener@@QAE@XZ",
    ev.server_object="dwQoS.obj",
    ev.basis="five-calibrated-structural-schemes+exact-anchor-callees",
    ev.structural_schemes="coarse_flow;coarse_profile;fine_flow;fine_profile;mnemonic_flow",
    ev.exact_anchor_callee_matches=3,
    ev.shared_unique_strings=0,
    ev.call_count=6,
    ev.data_ref_offset_count=1,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit="c48086ffa9ebae04d083aabda6e43f7ab29474e5",
    ev.workflow_run_id=36998585457,
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis="five-calibrated-structural-schemes+exact-anchor-callees",
    client.cross_build_identity_evidence_id=ev.id


MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va="0x004e3f70" AND struct.server_va="0x007e4b80"
MATCH (struct)-[:EVIDENCE_FOR]->(server:KGNode)
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:"urn:ure:t6:occ:function:current-client:004e3f70"})
MERGE (ev:KGNode {id:"urn:ure:t6:re_Evidence:structural-neighborhood-accepted:661eea438ec6c40952850faf"})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va="0x004e3f70",
    ev.server_va="0x007e4b80",
    ev.server_symbol="?Phys_EffectsInit@@YAXXZ",
    ev.server_object="phys_effects.obj",
    ev.basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    ev.structural_schemes="coarse_flow;coarse_profile;fine_flow;fine_profile;mnemonic_flow",
    ev.exact_anchor_callee_matches=0,
    ev.shared_unique_strings=3,
    ev.call_count=3,
    ev.data_ref_offset_count=13,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit="c48086ffa9ebae04d083aabda6e43f7ab29474e5",
    ev.workflow_run_id=36998585457,
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    client.cross_build_identity_evidence_id=ev.id


MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va="0x004863a0" AND struct.server_va="0x0070d600"
MATCH (struct)-[:EVIDENCE_FOR]->(server:KGNode)
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:"urn:ure:t6:occ:function:current-client:004863a0"})
MERGE (ev:KGNode {id:"urn:ure:t6:re_Evidence:structural-neighborhood-accepted:5a171b1563f743de14b4fb27"})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va="0x004863a0",
    ev.server_va="0x0070d600",
    ev.server_symbol="?UI_FriendsRegisterDvars@@YAXXZ",
    ev.server_object="ui_friends.obj",
    ev.basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    ev.structural_schemes="coarse_flow;coarse_profile;fine_flow;fine_profile;mnemonic_flow",
    ev.exact_anchor_callee_matches=0,
    ev.shared_unique_strings=3,
    ev.call_count=3,
    ev.data_ref_offset_count=9,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit="c48086ffa9ebae04d083aabda6e43f7ab29474e5",
    ev.workflow_run_id=36998585457,
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    client.cross_build_identity_evidence_id=ev.id


MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va="0x005380d0" AND struct.server_va="0x00795a70"
MATCH (struct)-[:EVIDENCE_FOR]->(server:KGNode)
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:"urn:ure:t6:occ:function:current-client:005380d0"})
MERGE (ev:KGNode {id:"urn:ure:t6:re_Evidence:structural-neighborhood-accepted:7249626164555d4cd1d82004"})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va="0x005380d0",
    ev.server_va="0x00795a70",
    ev.server_symbol="?VCS_Init@@YAXXZ",
    ev.server_object="vcs_hooks.obj",
    ev.basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    ev.structural_schemes="coarse_flow;coarse_profile;fine_flow;fine_profile;mnemonic_flow",
    ev.exact_anchor_callee_matches=0,
    ev.shared_unique_strings=3,
    ev.call_count=3,
    ev.data_ref_offset_count=10,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit="c48086ffa9ebae04d083aabda6e43f7ab29474e5",
    ev.workflow_run_id=36998585457,
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis="five-calibrated-structural-schemes+complete-distinctive-retail-string-set",
    client.cross_build_identity_evidence_id=ev.id


MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va="0x004c1160" AND struct.server_va="0x005b4520"
MATCH (struct)-[:EVIDENCE_FOR]->(server:KGNode)
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:"urn:ure:t6:occ:function:current-client:004c1160"})
MERGE (ev:KGNode {id:"urn:ure:t6:re_Evidence:structural-neighborhood-accepted:af1862aa86dff38d3ef71436"})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va="0x004c1160",
    ev.server_va="0x005b4520",
    ev.server_symbol="??0FriendInfo@@QAE@XZ",
    ev.server_object="bot.obj",
    ev.basis="five-calibrated-structural-schemes+exact-anchor-callees",
    ev.structural_schemes="coarse_flow;coarse_profile;fine_flow;fine_profile;mnemonic_flow",
    ev.exact_anchor_callee_matches=2,
    ev.shared_unique_strings=0,
    ev.call_count=2,
    ev.data_ref_offset_count=0,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit="c48086ffa9ebae04d083aabda6e43f7ab29474e5",
    ev.workflow_run_id=36998585457,
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis="five-calibrated-structural-schemes+exact-anchor-callees",
    client.cross_build_identity_evidence_id=ev.id


MATCH (struct:KGNode)
WHERE struct.evidence_kind='cross-build-structural-fingerprint-candidate'
  AND struct.client_va="0x00534f20" AND struct.server_va="0x00564cc0"
MATCH (struct)-[:EVIDENCE_FOR]->(server:KGNode)
WHERE server.kind='re:FunctionVariant'
MATCH (client:KGNode {id:"urn:ure:t6:occ:function:current-client:00534f20"})
MERGE (ev:KGNode {id:"urn:ure:t6:re_Evidence:structural-neighborhood-accepted:e09d1869a1e869733b4e4d77"})
SET ev.kind='re:Evidence',
    ev.namespace='t6',
    ev.evidence_kind='cross-build-structural-neighborhood-corroboration',
    ev.state='accepted-evidence-awaiting-semantic-promotion',
    ev.client_va="0x00534f20",
    ev.server_va="0x00564cc0",
    ev.server_symbol="?dwGetAddressMap@@YAPAVbdAddressMap@@XZ",
    ev.server_object="dwUtils.obj",
    ev.basis="five-calibrated-structural-schemes+exact-anchor-callees",
    ev.structural_schemes="coarse_flow;coarse_profile;fine_flow;fine_profile;mnemonic_flow",
    ev.exact_anchor_callee_matches=2,
    ev.shared_unique_strings=0,
    ev.call_count=3,
    ev.data_ref_offset_count=0,
    ev.repo='lizardpeter/bo2-t6-assets',
    ev.repo_commit="c48086ffa9ebae04d083aabda6e43f7ab29474e5",
    ev.workflow_run_id=36998585457,
    ev.proof_boundary='Accepted cross-build identity evidence only. Server PDB prototypes, types, globals, layouts, and source claims remain server-build facts until separately proven for retail.'
MERGE (ev)-[:CORROBORATES]->(struct)
MERGE (ev)-[:EVIDENCE_FOR]->(client)
MERGE (ev)-[:EVIDENCE_FOR]->(server)
SET struct.state='accepted-evidence-awaiting-semantic-promotion',
    struct.corroboration_evidence_id=ev.id,
    client.cross_build_identity_state='accepted-evidence-awaiting-semantic-promotion',
    client.cross_build_identity_candidate_variant_id=server.id,
    client.cross_build_identity_candidate_family_id=server.family_id,
    client.cross_build_identity_basis="five-calibrated-structural-schemes+exact-anchor-callees",
    client.cross_build_identity_evidence_id=ev.id

