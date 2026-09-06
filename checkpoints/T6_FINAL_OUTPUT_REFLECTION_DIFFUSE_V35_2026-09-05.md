# T6 final-output reflection/diffuse checkpoint — production v35

Date: 2026-09-05 (America/New_York)
Repository: `lizardpeter/bo2-t6-assets`

This checkpoint supersedes the v32 consumer checkpoint for final-output generated-material work.

## v33 exact generated reflection sample instances

Tool: `tools/t6_generated_final_output_reflection_sample_index_v1.py`
Production: `tools/t6_oat_world_textured_export_pipeline_v33.py`

For each exact generated slot-4 `reflectionProbeSampler` instruction:

- exact sample instruction DWORD and output sample nodes are retained;
- coordinate operand nodes and LOD/bias operand nodes are kept separately;
- completed specular X/Y/Z/W ancestry into coordinates and LOD/bias is reported;
- reflection LOD/bias must match the retained exact finite grammar:
  - SAMPLE_B bias -3 (`c0400000`);
  - SAMPLE_L literal LOD 0 / 0.8 / 2.4 / 4;
  - SAMPLE_L affine LOD: -4*x+4, 0.475*x, 0.25*x+0.75, or compiled 0*x+0.

No physical meaning is assigned to affine source x or any specular channel.

## v34 exact same-sample specular/reflection join

Tool: `tools/t6_generated_final_output_specular_reflection_join_v1.py`
Production: `tools/t6_oat_world_textured_export_pipeline_v34.py`

Cross-joins:

- completed specular roots;
- v32 downstream mixing sites;
- exact v33 reflection sample instances.

Promoted relationships require exact node identity, not resource-name proximity.
Reported exact facts include:

- direct `completedSpecularChannel * reflectionSampleChannel` product;
- completed specular root used directly as a reflection sample coordinate operand;
- completed specular root used directly as the exact affine reflection LOD source x.

Still no roughness/gloss/F0 naming.

## v35 squared generated RGB × directional-lightmap diagnostic

Tool: `tools/t6_generated_final_output_diffuse_directional_product_probe_v1.py`
Production: `tools/t6_oat_world_textured_export_pipeline_v35.py`

Inputs:

- v26 exact squared generated RGB anchor;
- v28 exact directional secondary-lightmap RGB equations;
- v29 exact layered-normal -> directional-equation identity.

The probe accepts only an actual reachable two-input DAG node:

`mul(squareRgbNode, directionalRgbNode)`

with arguments in either direct order. It does not flatten multiplication trees or perform associative rewrites.

The v29 identity allows the probe to distinguish the exact layered-normal directional equation from any second directional equation.

v35 is diagnostic: zero direct products is valid evidence and does not force a guessed final-lighting equation.

## Visual non-regression

v33, v34 and v35 are forensic sidecar stages only. They preserve prior production GLB/glTF bytes exactly.

## Still not closed

- complete final `o0.rgb` material/lightmap/reflection equation;
- physical meanings of generated specular X/Y/Z/W;
- last 65 reflection fetches;
- retail-equivalent final Blender material output;
- real Blender runtime validation in this environment.

## Next target

Serialize the exact top-level `o0.rgb` expression topology and classify syntactic additive/multiplicative leaves by already-proven anchors (squared generated RGB, directional lightmap equations, completed specular state, exact reflection fetches). Use that topology to decide which final-composition matcher to promote next instead of assuming a renderer formula.
