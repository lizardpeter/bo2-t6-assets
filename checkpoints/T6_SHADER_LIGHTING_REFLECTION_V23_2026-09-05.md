# T6 Shader / Lighting / Reflection Checkpoint — v23 — 2026-09-05

This checkpoint supersedes the renderer-integration portions of
`T6_SHADER_LIGHTING_REFLECTION_V9_2026-09-05.md` while retaining its historical
proof facts. It exists so another worker can continue without widening any
proof boundary or reverting source-closed renderer state to generic PBR guesses.

## Non-regression facts retained

- Original internal Nuketown v31 SHA-256:
  `6aff8a3c8e44dd5d0c20a7f229d2102677b092add054341b265aec74547882df`.
  The large v31 artifact itself is not currently retained in the repository.
- Reflection closure remains **5823 / 5888 = 98.89605978260869%**. The final 65
  residuals are **not** promoted by this checkpoint.
- Corrected OAT GfxWorld lightmap/reflection dumper patches are source-prepared
  but still require compilation/retail execution for a new exact catalog.
- Do not reinterpret generated specular XYZW as metallic/roughness/F0.
- Do not invent a final material/lightmap/specular/reflection equation.

## Canonical generated recipe

Authoritative glTF location remains:

`material.extras.T6.generatedShaderRecipeV1`

Canonical recipe work now includes, when recovered/proved:

- exact generated TechniqueSet + PS/VS identity;
- exact A/B/M/T/vN color-layer program;
- exact vN forensic weight DAG + material constants + leaves;
- exact base/secondary normal sample decode DAGs;
- dual-proof normal transform ownership;
- exact paired-VS physical N/T/B basis proof;
- exact base-normal zero/explicit baseline;
- exact generated specular-state attachment for Nuketown v21.

## Generated normal path: production v18–v20

### v18

`tools/t6_oat_world_textured_export_pipeline_v18.py`

Canonical recipe carries complete generated normal sample state:

- base `normalMapSampler.x/y` exact sample-only DAG, or exact zero baseline;
- secondary `normalMapSamplerN.x/y` exact sample-only DAGs;
- exact `.tech` sampler/material ownership;
- exact v15 dual-proof direct/2x2 transform mapping.

No hard-coded `2*RG-1` assumption is required by renderer playback.

### v19

`tools/t6_oat_world_textured_export_pipeline_v19.py`

Generated primitives expose exact existing retail basis bytes as zero-copy
application attributes:

- `_T6_WORLD_NORMAL`
- `_T6_WORLD_TANGENT`
- `_T6_TANGENT_HANDEDNESS`

v19 changes no BIN bytes.

### v20

`tools/t6_oat_world_textured_export_pipeline_v20.py`

Adds separately interpolated per-vertex binormal:

`B_vertex = cross(N_vertex, T_vertex) * TANGENT.w`

This preserves retail vertex-stage topology. Recomputing `cross(interpolated
N, interpolated T)` in the fragment/material graph is forbidden because it is
not algebraically equivalent to interpolating the vertex-stage cross.

v20 preserves the complete v19 BIN as an exact prefix and appends only derived
binormal VEC3 data.

Regression:

`tools/test_t6_oat_world_textured_export_pipeline_v20.py`

## Blender generated normal playback v6/v7

`tools/t6_blender_generated_layer_preview_v6.py`

Executes:

1. exact base normal decode / zero baseline;
2. exact secondary decode DAG;
3. exact direct or 2x2 transform;
4. the **same exact layer factor socket** used by generated diffuse;
5. ordered XY normal recurrence;
6. exact paired-VS basis reconstruction `N + X*T + Y*B`;
7. normalization;
8. final normal handed to Blender Principled only as a downstream authoring
   lighting consumer.

It never uses Blender Normal Map or Tangent nodes.

`tools/t6_blender_generated_layer_preview_v7.py`

Adds explicit conversion for custom glTF basis-vector attributes:

`(x,y,z) -> (x,-z,y)`

before OBJECT->WORLD. This prevents relying on Blender's standard semantic
conversion for custom `_T6_*` attributes.

Real runtime fixture:

`tools/test_t6_blender_generated_layer_preview_runtime_v7.py`

The fixture is committed and production-shaped, but hosted GitHub Actions did
not execute it. Do not claim a real Blender v7 pass until a Blender process
actually runs.

## v21 — exact generated specular XYZW state, Nuketown only

Production:

`tools/t6_oat_world_textured_export_pipeline_v21.py`

Contract:

`tools/t6_world_generated_specular_state_v1.py`

Regressions:

- `tools/test_t6_world_generated_specular_state_v1.py`
- `tools/test_t6_oat_world_textured_export_pipeline_v21.py`

Source proof:

`manifests/render/T6_RETAIL_LAYERED_SPECULAR_COMPOSITOR_V1.json`

Retained proof has:

- 73 shaders;
- 82 secondary specular steps;
- 74 blend, 8 threshold;
- 328 XYZW recurrence checks;
- 0 recurrence failures;
- 0 same-RGB-weight mismatches.

Exact state recurrence:

- blend:
  `prevSpecRGBA + (layerSpecRGBA - prevSpecRGBA) * exactRgbWeight`
- threshold:
  `select(exactRgbThresholdCondition, layerSpecRGBA, prevSpecRGBA)`

No-base-spec fallback:

- RGB = `(0.2,0.2,0.2)`
- W = base color alpha for `x0` TechniqueSets
- W = 0 otherwise.

v21 binds exact embedded specular texture ownership and explicitly binds the
specular transition to the same exact RGB layer factor/condition. It does not
assign physical meaning to XYZW. v21 is currently source-gated to
`mp_nuketown_2020` rather than pretending the retained five-map census is a
per-shader membership registry for arbitrary future maps.

v21 is metadata-only over v20; BIN is byte-identical.

## Directional secondary lightmap proof

Authoritative proof:

`manifests/render/T6_RETAIL_LAYERED_DIRECTIONAL_LIGHTMAP_V1.json`

The newer retained-DXBC proof supersedes the old 2026-09-01 statement that all
lightmap channel/combine behavior was unknown. What is now closed is the
**secondary directional-lightmap RGB state** for 173/173 retained layered slot-4
shaders:

```
row0 = sample(secondary, (u, v/3))
row1 = sample(secondary, (u, v/3 + 1/3))
row2 = sample(secondary, (u, v/3 + 2/3))
direction = 2*row2.rgb - 1
factor = saturate(dot(direction, N))
rgb = row0.rgb/(row0.a+1e-6)
    + row1.rgb/(row1.a+1e-6)*factor
```

Important boundaries:

- `direction` is **not** renormalized.
- `N` is the reconstructed T6 surface normal for the proven generated-normal
  population.
- The final material/lightmap/specular/reflection output composition is still
  not promoted here.
- Blender/Pillow authoring texture sampling is not claimed bit-identical to the
  retail D3D11 sampler until that sampler-state/backend boundary is separately
  closed.

## v22 — exact-DDS-derived lightmap PNG preview staging

Production:

`tools/t6_oat_world_textured_export_pipeline_v22.py`

Derived preview contract:

`tools/t6_world_lightmap_preview_embed_v1.py`

Regressions:

- `tools/test_t6_world_lightmap_preview_embed_v1.py`
- `tools/test_t6_oat_world_textured_export_pipeline_v22.py`

Behavior:

- canonical `extras.T6.lightmapArchive` v3 raw DDS remains authoritative;
- each unique **embedded** present GfxImage DDS is decoded via Pillow's DDS
  decoder to an RGBA PNG authoring preview;
- exact GfxImage identity, source filename, DDS SHA-256 and preview PNG SHA-256
  are retained;
- repeated uses of one GfxImage deduplicate to one preview image;
- absent/null roles produce no preview or fallback;
- preview is tagged `previewOnly` and `dataTexture` / Non-Color semantics;
- no material binding is created;
- v21 BIN remains an exact prefix; only preview PNG bytes are appended.

This follows the same safe pattern already used by the repository's cubemap
preview tool: preserve retail source bytes and clearly label decoded previews as
an authoring derivative.

## v23 — exact per-surface lightmap material specialization

Production:

`tools/t6_oat_world_textured_export_pipeline_v23.py`

Contract:

`tools/t6_world_lightmap_material_specialize_v1.py`

Regressions:

- `tools/test_t6_world_lightmap_material_specialize_v1.py`
- `tools/test_t6_oat_world_textured_export_pipeline_v23.py`

Reason:

T6 `GfxSurface` owns `lightmapIndex`; `Material` does not. One retail material
may therefore appear on multiple differently lightmapped surfaces. Blender
material sharing cannot represent that ownership without specialization.

v23 creates preview-only material shells keyed by:

`(retail material index, lightmapIndex, lightmapTexCoord)`

Each shell:

- retains the full original material metadata and canonical recipe;
- adds `lightmapPreviewBindingV1` with exact retail material identity;
- records exact primary/secondary preview ownership where available;
- never rewrites `generatedShaderRecipeV1.material`;
- redirects only the relevant GfxSurface primitive to the shell.

No-lightmap surfaces retain the original retail material shell.

v23 is JSON-only over v22; BIN is byte-identical.

## Blender v8 — directional lightmap state, not guessed final shading

`tools/t6_blender_generated_layer_preview_v8.py`

Equation node compiler:

`tools/t6_blender_directional_lightmap_nodes_v1.py`

Real runtime fixture:

`tools/test_t6_blender_generated_layer_preview_runtime_v8.py`

v8:

- validates v23 preview-shell -> retail material identity before accepting the
  canonical recipe;
- never treats the preview shell name as retail identity;
- extracts the embedded PNG directly by bufferView + PNG SHA + source DDS SHA,
  so Blender does not need to import unused glTF textures;
- packs the decoded image and sets Non-Color;
- rebuilds v7 diffuse/height/normal graph against retail identity;
- when exact v7 normal playback and exact secondary-lightmap preview both exist,
  builds the retained 3-row directional equation;
- stores the resulting directional RGB state in the node graph;
- **does not connect that RGB state to Principled or Material Output**.

The runtime fixture specifically asserts the final directional RGB node has no
outgoing material-shading connection.

GitHub workflow now includes v8:

`.github/workflows/t6-blender-runtime.yml`

Latest hosted run after v8 workflow commit:

- run `34000651471`
- job `101398791920`
- conclusion failure
- **executed steps: 0**

This is the same hosted-runner provisioning failure seen earlier. It is not a
Blender v8 test failure because no checkout/download/test step ran.

## Current strongest production chain

For Nuketown, conceptually:

```
retail world bytes / OAT evidence
  -> exact geometry + generated attributes
  -> exact material/image dependencies
  -> exact generated recipes + vN DAGs
  -> exact base/secondary normal decode + transform ownership
  -> exact paired-VS N/T/B basis
  -> exact raw lightmap DDS archive
  -> exact reflection DDS archive
  -> exact material GPU render-state archive
  -> v20 separately interpolated binormal
  -> v21 exact generated specular XYZW state
  -> v22 DDS-derived lightmap preview images
  -> v23 per-surface lightmap preview material ownership
```

Blender authoring path:

```
v7 exact generated diffuse + layered normal
  -> v8 exact directional secondary-lightmap RGB state
     [final lighting composition intentionally still disconnected]
```

## Immediate next targets

1. Build a generated-layer final-output symbolic probe by reusing the existing
   SM4 symbolic DAG engine and exact slot-4 recipe shader identities. Match
   proved generated-color, normal/lightmap and specular subexpressions against
   `o0` ancestry rather than reconstructing HLSL from assumptions.
2. Run v7/v8 real Blender fixtures in an environment that actually supplies a
   Blender process; current hosted runner does not start.
3. Close the final T6 output composition that consumes generated diffuse,
   generated specular XYZW, directional lightmap state, reflection probe state,
   primary light/light-grid terms, shadows, etc. Do not infer this from generic
   PBR.
4. Continue the final 65 reflection residuals only with pinned retained proof.
5. Compile/run corrected OAT GfxWorld lightmap/reflection dumpers against retail
   Nuketown and archive exact catalog/output hashes.
6. Repeat the production evidence path across representative MP + Zombies/DLC
   maps rather than treating Nuketown-specific promotion as universal.
