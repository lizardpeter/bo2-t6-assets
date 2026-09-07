# T6 Blender Full-Export Readiness — 2026-09-07

This checkpoint defines two separate targets and prevents them from being
conflated:

1. **Complete Blender export**: all canonical Nuketown geometry/placements and
   every used retail material are present in one `.blend`; each material is
   either lowered through an exact solved T6 shader family or is explicitly
   marked as an unresolved shader family. Silent generic-PBR fallback is
   forbidden.
2. **Retail-render parity**: the complete T6 pixel output, global lighting,
   reflection, fog, shadow and blend/depth behavior is reproduced with no
   unresolved renderer term.

A complete Blender export may be produced before retail-render parity, but it
must remain fail-visible: unresolved shader/global terms cannot be hidden behind
invented roughness/metallic/specular values.

## Closed foundations

- Exact retail FastFile expansion and GfxWorld/XModel extraction are already
  source-derived and regression-gated.
- Canonical visible static placement/material identity work is retained.
- Generated-world shader population is exact for Nuketown:
  - 120 generated materials;
  - 34 exact TechniqueSets;
  - 34 unique slot-4 pixel shaders;
  - zero cross-TechniqueSet shader reuse;
  - worldVertFormat histogram 1:95, 2:7, 3:17, 6:1.
- The 34 generated slot-4 shaders have complete exact final-output symbolic DAGs
  with exact OAT shader identity gates and no reachable undefined output state.
- Generated diffuse, height-weight, layered-normal, layered-specular,
  directional-secondary-lightmap and reflection proof branches are retained.
- Reflection ownership/fetch closure remains 5823/5888 = 98.89605978260869%;
  the residual 65 are still unpromoted.
- XModel Blender transport now preserves custom T6 color and exact retail
  tangent/handedness channels instead of invoking glTF PBR COLOR_0 semantics or
  Blender tangent recomputation.
- The first ordinary non-generated T6 `lprobe lit` families are source-closed by
  exact VS+PS DXBC identity:
  - opaque normal+specular+color;
  - glass specular+color.
- `t6_blender_shader_plan_v1.py` lowers only exact known VS+PS SHA pairs and
  fails closed for unknown shaders.
- `t6_blender_lprobe_nodes_v2.py` has passed inside real Blender 4.0.2.
  GitHub Actions run 34141524166 produced artifact
  `T6_BLENDER_LPROBE_NODES_V2_TEST` (artifact 10026081318, digest
  sha256:e09273aded9d75d217de963c063eda40f7afb71260b53642d5e986beb72e486f).
  The opaque graph contains 37 nodes and the glass graph 18 nodes; material-local
  exact nodes, opaque normal decode, glass sqrt-alpha, Non-Color role copies and
  no specular->Principled metallic/roughness mapping all passed.

## Complete-export blockers

A **complete Blender export** is not promoted until all of the following are
closed:

1. Build an exact Nuketown used-material -> TechniqueSet -> lit VS/PS census for
   all canonical world/static/MapEnt material uses, including shared FastFile
   TechniqueSets.
2. Classify every exact VS+PS pair into:
   - already solved Blender family;
   - generated final-output DAG family;
   - newly unsolved family.
   No material may silently enter a generic glTF PBR path.
3. Add a generic Blender compiler for the exact generated slot-4 DAG vocabulary
   (`textureSample`, scalar/vector arithmetic, dot products, select/branch,
   saturate, sqrt/rsq/exp/log/frc/round/rcp, discard) with exact source resource
   names and sampling coordinates.
4. Supply Blender representations for T6 global shader resources where a direct
   Blender node has no equivalent. Expected important classes include:
   `modelLightingSampler` texture3D, `reflectionProbeSampler` cube+explicit LOD,
   primary/secondary lightmaps, grid/reflection SH constants, fog and HDR
   constants. Prefer exact bake/lookup representations over semantic guesses.
5. Integrate exact per-technique Material state into Blender metadata and the
   closest supported viewport/render setting. Any D3D11 blend equation Blender
   cannot reproduce exactly must be explicitly reported rather than approximated
   invisibly.
6. Produce one fresh canonical Nuketown `.blend`, then verify scene counts,
   material assignment cardinality, missing textures, missing shader plans,
   unresolved-family count, and no forbidden PBR fallback.

## Retail-render-parity blockers beyond complete export

Even after the complete `.blend` gate passes, retail parity remains open until:

- all generated/non-generated final output arithmetic is compiled or exactly
  baked;
- primary/dynamic light, light-grid and shadow terms are source-closed for all
  used shader families;
- reflection residuals are closed or proven irrelevant to the exported scene;
- fog/HDR output transfer is reproduced;
- unsupported Blender destination-blend behavior has an exact rendering/bake
  strategy;
- sampling/filtering/LOD behavior is validated closely enough that authoring
  image decoding is not mistaken for D3D11-bit-identical sampling.

## Current practical assessment

- **Scene/asset completeness needed to emit a useful full `.blend`: very close.**
- **Shader-aware complete export with no silent fallback: last major integration
  phase.**
- **100% retail-render parity: materially further than file generation because
  global renderer resources and some shader families remain open.**

The immediate next operation is the all-used-material exact shader census,
followed by generated-DAG Blender lowering. These two gates provide the fastest
path from the current proven pieces to one complete fail-visible Nuketown
`.blend`.
