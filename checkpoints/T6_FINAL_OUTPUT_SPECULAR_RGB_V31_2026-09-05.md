# T6 final-output specular/RGB checkpoint — production v31

Date: 2026-09-05 (America/New_York)
Repository: `lizardpeter/bo2-t6-assets`

This checkpoint supersedes the v29 final-output checkpoint for generated RGB/specular factor state.

## Production baseline

Current production wrapper: `tools/t6_oat_world_textured_export_pipeline_v31.py`

v31 preserves the complete v30 visual GLB/glTF byte-for-byte and adds forensic sidecars only.

## Final-output chain already source-closed before v30

- exact OAT slot-4 pixel-shader identity per generated recipe;
- complete symbolic `o0.xyzw` DAG with exact RDEF texture/sampler names;
- independent output resource ancestry;
- unique generated encoded-RGB -> squared-RGB anchors;
- exact secondary directional-lightmap equation anchors;
- exact ISGN input semantic binding;
- exact reconstructed layered normal joined to the directional equation that consumes it.

## v30: exact generated specular XYZW state inside o0

Tool: `tools/t6_generated_final_output_specular_state_anchor_v1.py`

Source state contract remains v21 `generatedSpecularStateV1`:

- explicit base specular sample or retained fallback RGB=(0.2,0.2,0.2);
- fallback W = base color alpha for x0 techniques, otherwise zero;
- blend recurrence: `prev + (layer-prev)*factor`;
- threshold recurrence: `select(condition, layer, prev)`;
- exact `specularMapSamplerN` ownership.

The v30 anchor reconstructs this state directly inside the complete final-output DAG.
For every layer:

- X/Y/Z/W must all resolve the recurrence independently;
- all four channels must share one canonical factor/condition DAG hash;
- the completed specular state must have exact ancestry to written `o0` in strict production mode.

This proves downstream use of the completed state. It does NOT assign physical meanings to X/Y/Z/W.

Production: `tools/t6_oat_world_textured_export_pipeline_v30.py`
Regression: `tools/test_t6_oat_world_textured_export_pipeline_v30.py`

## v31: exact RGB factor recovery and specular cross-proof

Tool: `tools/t6_generated_final_output_rgb_factor_anchor_v1.py`

The v26 RGB-square anchor gives the exact encoded color state immediately before squaring.
v31 reconstructs the canonical generated RGB layer program forward from exact `colorMapSampler*` samples:

- add: `prev + layer*factor`;
- blend: `prev + (layer-prev)*factor`;
- multiply: `prev * (1 + (layer-1)*factor)`;
- threshold: `select(condition, layer, prev)`.

Every RGB layer must expose exactly one factor/condition expression shared by R/G/B, and the completed state must equal the v26 pre-square anchor exactly.

Regression covers A/B/M/T:
`tools/test_t6_generated_final_output_rgb_factor_anchor_v1.py`

Cross-proof tool:
`tools/t6_generated_final_output_specular_rgb_factor_join_v1.py`

For every specular step:

- specular `b` must correspond to RGB `blend`;
- specular `t` must correspond to RGB `threshold`;
- exact shared factor/condition canonical SHA-256 must be identical for the same material/layer.

This independently re-establishes the retained "specular uses the same exact RGB scalar" statement inside final `o0` dataflow.

Production v31 sidecars:

- `generated_final_output_rgb_factor_anchor_v1.json`
- `generated_final_output_specular_rgb_factor_join_v1.json`

Production regression:
`tools/test_t6_oat_world_textured_export_pipeline_v31.py`

## Important proof boundary

Still DO NOT claim:

- specular X/Y/Z/W == metallic/roughness/F0/gloss or any standard PBR convention;
- final material/lightmap/reflection composition is fully closed;
- Blender final material output is retail-equivalent;
- last 65 reflection fetches are closed;
- Blender runtime has passed in this execution environment.

The correct next task is to trace the completed specular XYZW roots upward through final `o0` and classify their first downstream mixing sites and exact external resource ancestry. Only after that should channel meanings or final lighting equations be promoted.
