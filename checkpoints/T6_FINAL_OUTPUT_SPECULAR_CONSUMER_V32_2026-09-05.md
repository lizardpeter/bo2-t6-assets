# T6 final-output specular consumer checkpoint — production v32

Date: 2026-09-05 (America/New_York)
Repository: `lizardpeter/bo2-t6-assets`

This checkpoint supersedes the v31 specular/RGB checkpoint for downstream-consumer tracing.

## v31 exact shared generated layer scalar

Production: `tools/t6_oat_world_textured_export_pipeline_v31.py`

Source-closed final-output facts:

- generated RGB A/B/M/T recurrence is reconstructed from exact `colorMapSampler*` samples;
- every RGB layer exposes one exact scalar factor/condition shared across R/G/B;
- completed encoded RGB state must equal the v26 pre-square RGB anchor;
- generated specular XYZW recurrence is independently reconstructed inside the same exact slot-4 final-output DAG;
- every specular b/t step exposes one exact factor/condition shared across X/Y/Z/W;
- same retail material/layer specular-vs-RGB factor/condition SHA-256 must match exactly.

Tools:
- `tools/t6_generated_final_output_rgb_factor_anchor_v1.py`
- `tools/t6_generated_final_output_specular_state_anchor_v1.py`
- `tools/t6_generated_final_output_specular_rgb_factor_join_v1.py`

This independently re-establishes the retained "specular uses the same exact RGB factor" relation inside final o0 dataflow.

## v32 downstream specular consumer frontier

Tool: `tools/t6_generated_final_output_specular_consumer_frontier_v1.py`
Production: `tools/t6_oat_world_textured_export_pipeline_v32.py`

For every completed specular X/Y/Z/W root already proven to reach o0, v32 walks upward through exact final-output dataflow.

The four specular roots are treated as one owned state. Therefore:

- one specular channel is not considered an external dependency of another;
- arithmetic siblings outside the four-root state are recorded as external inputs;
- exact texture resources reachable through those external siblings are recorded;
- if the parent itself is a `textureSample` consuming a specular root as coordinate/LOD/gradient input, the parent's exact RDEF resource name is recorded even though it is not a sibling DAG.

Each channel records:

- nearest downstream mixing distance;
- nearest mixing nodes and operation/kind;
- nearest resource-bearing mixing distance;
- exact external resource names;
- output lanes reachable through each site;
- all downstream mixing sites for forensic follow-up.

Production v32 keeps v31 GLB/glTF bytes unchanged.

## Important proof boundary

Do NOT infer physical channel meanings merely because a specular state component is near:

- `reflectionProbeSampler`;
- `lightmapSampler` / `lightmapSamplerSecondary`;
- another named texture resource.

The frontier is dependency evidence, not a semantic promotion.

Still not closed:

- physical meanings of generated specular X/Y/Z/W;
- complete final material/lightmap/reflection equation;
- last 65 reflection fetches;
- retail-equivalent Blender final output;
- real Blender runtime validation in the current execution environment.

## Next task

Take exact v32 frontier sites whose external resource includes `reflectionProbeSampler` and cross-join them with the retained reflection-probe decode/LOD/material-parameter proofs by exact pixel-shader SHA and exact sample ancestry. Only promote a specular/reflection relationship when both sides identify the same sample/dataflow instance.
