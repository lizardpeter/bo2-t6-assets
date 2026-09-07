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
- The v25 full-map release floor contains 711 used materials, 9,088 primitives,
  567,122 triangles and 809 embedded images while retaining the complete
  canonical world/static/MapEnt/skybox population.
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
- A generic exact scalar symbolic-DAG Blender compiler now exists:
  `t6_blender_symbolic_dag_nodes_v1.py` + semantic-hardening v2.
  It preserves SM4 base-2 `exp`/`log`, explicit saturate, select/branch tests,
  reciprocal/rsqrt and the ordinary scalar arithmetic used by final-output DAGs.
  `round_ne` and bitwise `and/or` remain deliberately fail-closed pending exact
  backend semantics.
- The generic symbolic-DAG compiler passed inside real Blender 4.0.2 in GitHub
  Actions run 34142277643. Artifact `T6_BLENDER_SYMBOLIC_DAG_V2_TEST`
  (artifact 10026353744) has digest
  sha256:ff0f306e6cb30b24f870da9bb81ca7d1efe456af4ef75055b627134a5a45e3d3.
- `t6_blender_symbolic_dag_capability_v1.py` now provides a fail-closed census of
  which exact operations/resources are actually reachable from the 34 real
  generated `o0` outputs, so remaining generated-family gaps can be measured
  rather than guessed.

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
3. Run the new capability census against the retained/regenerated 34 real
   generated final-output DAGs, then close only operations/sampling modes that
   actually remain blocked. The generic scalar arithmetic compiler itself is
   now real-Blender validated.
4. Supply Blender representations for T6 shader resources where a direct
   Blender node has no equivalent. Expected important classes include:
   `modelLightingSampler` texture3D, `reflectionProbeSampler` cube+explicit LOD,
   primary/secondary lightmaps, grid/reflection SH constants, fog and HDR
   constants. Prefer exact bake/lookup representations over semantic guesses.
5. Add exact textureSample resource/coordinate adapters for the generated DAG
   compiler, including derivative/LOD/bias sampling modes used by the real 34
   shaders; preserve DISCARD/alpha-test behavior explicitly.
6. Integrate exact per-technique Material state into Blender metadata and the
   closest supported viewport/render setting. Any D3D11 blend equation Blender
   cannot reproduce exactly must be explicitly reported rather than approximated
   invisibly.
7. Produce one fresh canonical Nuketown `.blend`, then verify scene counts,
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

- **Raw scene/asset export:** already essentially complete; the canonical v25
  scene proves the full geometry/placement/material/image population exists.
- **Shader-aware complete `.blend` with no silent fallback:** approximately
  **88-92% of the engineering path is closed**. The remaining work is dominated
  by all-used-material shader classification, exact generated/global resource
  adapters, and final integration/validation rather than missing asset reversal.
- **Retail-equivalent visual rendering inside Blender:** approximately
  **75-82% of the backend integration path is closed**. Source evidence is ahead
  of the Blender backend; global model-light/reflection/lightmap/SH/fog/HDR,
  some sampling modes, non-generated families and exact blend behavior remain.
- **100% all-T6-shader converter beyond Nuketown:** lower than the Nuketown-only
  numbers because representative MP/Zombies/DLC families still have to be
  censused and source-closed before generalizing the backend.

The immediate next operation is the all-used-material exact shader census and
real 34-shader generated-DAG capability census, followed by the resource/sampler
adapters they prove are actually needed. Those are now the shortest path to one
complete fail-visible Nuketown `.blend`.
