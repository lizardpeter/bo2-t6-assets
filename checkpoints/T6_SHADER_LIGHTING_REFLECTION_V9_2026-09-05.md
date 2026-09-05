# T6 shader / lighting / reflection checkpoint — 2026-09-05

This checkpoint is a conservative handoff for the concurrent T6 reversal work.
It records what is source-closed, what is integrated, and what still requires an
actual retail/runtime execution. Do not replace these contracts with generic
PBR guesses merely because an intermediate GLB renders plausibly.

## Starting visual checkpoint: Nuketown internal v31

Internal combined-map artifact:

```text
SHA-256 6aff8a3c8e44dd5d0c20a7f229d2102677b092add054341b265aec74547882df
```

Retained v31 state reported by the build:

- v25 non-regression: 0 failures;
- v25 binary exact prefix of v31;
- independent trimesh import passed;
- exact secondary material UV1: 507 full-world surfaces;
- exact UV2: 48 surfaces;
- exact UV3: 1 surface;
- exact normal-transform data: 34 surfaces / 548 vertices;
- all 933 generated-material primitives use `_T6_LAYER_WEIGHTS`;
- zero generated packed-color streams exposed as ordinary Blender `COLOR_0`;
- 120 generated materials had complete retail shader recipes in the internal build state;
- 34/34 retail pixel-shader archetypes resolved;
- exact generated diffuse operation census: 8 add / 84 blend / 47 multiply;
- 9 generated normal-layer material recipes source-closed;
- 7 secondary-specular Nuketown cases identified and texture-resolved.

The v31 binary and its internal 120-row shader-archetype table were not committed
as a repository artifact. Do not invent that missing serialization. The repo now
has a canonical recipe schema for future builds.

## Generated/layered shader contract

`tools/t6_generated_world_shader_semantics_v1.py` now contains the reusable,
map-independent recovered semantics.

### Exact color recurrence

- A: `prev.rgb + layer.rgb * exactWeight`
- B: `prev.rgb + (layer.rgb - prev.rgb) * exactWeight`
- M: `prev.rgb * (1 + (layer.rgb - 1) * exactWeight)`
- T: `select(exactThresholdCondition, layer.rgb, prev.rgb)`

Weight dispatch:

- ordinary A/B: `layerAlpha * vertexWeight`;
- M: `vertexWeight`;
- `xN` B: `vertexWeight`;
- T: `(layerAlpha * vertexWeight) >= 0.5`;
- `vN`: exact retained per-shader height DAG only; no universal approximation.

Generated color is composed in the retail encoded texture domain before the
explicit shader RGB-square stage.

### Exact normal transform / recurrence

Stored four-byte transform order:

```text
[m00, m11, m01, m10]
```

Logical shader matrix after UNORM8 -> [-1,+1]:

```text
[[m00,m01],[m10,m11]]
```

Layered normal XY uses the exact layer weight/threshold recurrence. Universal
retail reconstruction:

```text
raw = baseNormal + layeredX*xBasis + layeredY*yBasis
normal = normalize(raw)
```

### Exact layered-specular recurrence

The seven Nuketown secondary-specular cases are an integration problem, not
seven unknown compositor equations. Retained shader proof closes the ordered
XYZW recurrence:

```text
blend     = prevSpec + (layerSpec - prevSpec) * exactRgbWeight
threshold = select(exactRgbThresholdCondition, layerSpec, prevSpec)
```

Corpus recurrence accounting recorded in prior proof work:

- 82 layered-specular steps;
- 74 blend transitions;
- 8 threshold transitions;
- 328 XYZW checks;
- 0 recurrence failures.

No-base-spec fallback:

- RGB = `(0.2,0.2,0.2)`;
- W = base color alpha for `x0` techniques, else 0.

Do **not** reinterpret this XYZW state as generic metallic/roughness without a
separate source proof.

## Canonical generated shader recipes

Repository-owned canonical location:

```text
material.extras.T6.generatedShaderRecipeV1
```

Manifest:

```text
t6-generated-world-shader-recipe-manifest-v1
```

Implementation:

- `tools/t6_generated_shader_recipe_contract_v1.py`
- `tools/t6_world_textured_gltf_export_v3.py`
- canonical Blender adapter v3 consumes only this key/manifest.

Policy: exact material-name join only; every generated material and every recipe
must account exactly in production mode. Compound material name grammar alone
is not sufficient evidence for a TechniqueSet/pixel-shader archetype.

## Blender/Tour visual adapter

Implemented:

- `tools/t6_blender_generated_layer_preview_v1.py`
- `tools/t6_blender_generated_layer_preview_v2.py`
- `tools/t6_blender_generated_layer_preview_v3.py`

The adapter:

- resolves exact dependency identities from GLB extras;
- samples exact material UV sets;
- consumes `_T6_LAYER_WEIGHTS`;
- composes supported A/B/M/T generated color in the retail encoded domain;
- applies the explicit retail RGB square;
- leaves Blender Principled as **preview downstream lighting only**;
- preserves normal/spec dependency identity;
- refuses unsupported `vN` height execution rather than approximating it;
- does not invent a T6 specular/lightmap/reflection -> Principled conversion.

Real-runtime test added:

```text
tools/test_t6_blender_generated_layer_preview_runtime_v3.py
.github/workflows/t6-blender-runtime.yml
```

The runtime test constructs a self-contained generated-material glTF, imports it
through Blender, runs adapter v3, saves/reopens `.blend`, then verifies UV layers,
`_T6_LAYER_WEIGHTS`, image datablocks, node graph, custom properties and report.

### Runtime execution boundary

In the current ChatGPT container there is no `blender` executable and no `bpy`
module. Direct official Blender archive downloads and the official CPython-3.13
`bpy` wheel could not be transferred through the runtime download bridge.
A temporary GitHub pull-request run was also created to exercise the workflow,
but GitHub allocated no runner (`runner_id=0`, empty runner name, zero steps), so
**no Blender process executed in that run**. The PR was closed; the actual runtime
test/workflow remain on main.

Do not label the Blender adapter consumer-validated until that real runtime test
executes successfully.

## Directional lightmap shader

`tools/t6_directional_lightmap_semantics_v1.py` implements the retained exact
secondary-lightmap equation:

```text
row0 = sample(secondary, (u, v/3))
row1 = sample(secondary, (u, v/3 + 1/3))
row2 = sample(secondary, (u, v/3 + 2/3))
direction = 2*row2.rgb - 1
factor = saturate(dot(direction, N))
rgb = row0.rgb/(row0.a+1e-6) + row1.rgb/(row1.a+1e-6)*factor
```

The decoded direction is not renormalized. `N` is the already reconstructed
fully composed normal.

Committed retained proof covers 173/173 unique layered slot-4 shaders with zero
failures for this equation.

## Reflection shader state

The old project ledger understated reflection closure. The corrected retained
ledger:

```text
manifests/render/T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V2.json
```

records measured closure:

```text
5,823 / 5,888 fetches = 98.8960597826%
65 fetches remain unpromoted
```

Remaining families in that ledger:

- TEXCOORD2/TEXCOORD1: 21 remaining (54/75 already closed);
- TEXCOORD3/TEXCOORD1: 20 remaining (22/42 already closed);
- named sphere-electric TEXCOORD2/TEXCOORD0: 24 remaining.

Newer residual/sphere closure drivers and CI regressions exist, but no committed
pinned-corpus final run was found that promotes those 65. Keep the measured
boundary at 5,823/5,888 until such evidence is archived.

### Universal all-5,888 reflection mechanics

`tools/t6_reflection_probe_semantics_v1.py` records:

```text
A = normalize(rawA)
B = normalize(rawB)
cubeCoordinate = B - 2*A*dot(A,B)
probeRgb = probe.rgb / (probe.a + float32(0x358637bd))
```

Mip selection is the finite retained set:

- affine `4 - 4*x`;
- affine `0.475*x` using exact float bits;
- affine `0.25*x + 0.75`;
- compiled zero affine;
- literal LOD 0, 0.8, 2.4, 4;
- SAMPLE_B literal bias -3.

5,682 fetches have the exact linked angular core:

```text
D = saturate(dot(U, -V))
E = 2^(-9.28 * D)
```

206 are retained as the unlinked family rather than generalized.

### Dominant exact 4,236-fetch family

For the source-closed shared-parameter family the same scalar `x` drives:

```text
LOD = 4 - 4*x
Q = x*A + B
C = min(E,Qy)
F = Qx*C + Qz
factor.rgb = saturate(P.rgb*(Qw-F) + F)
reflection.rgb = decodedProbe.rgb * factor.rgb
```

with the exact retained float32 A/B vectors encoded in
`t6_reflection_probe_semantics_v1.py`.

P source:

- 4,216 fetches: `P.rgb = S.rgb * S.rgb`;
- 20 fetches: exact immediate float bits `0x3d23d70a` (~0.04).

Do not apply this dominant family to a residual family based on visual
similarity.

## Exact reflection resource ownership

Pinned OpenAssetTools T6 structure was rechecked. At OAT commit:

```text
7d027e8f89118196713e955b0e11f8404149c54d
```

resources live under `GfxWorld::draw`:

```cpp
struct GfxWorldDraw {
    unsigned int reflectionProbeCount;
    GfxReflectionProbe* reflectionProbes;
    GfxTexture* reflectionProbeTextures;
    int lightmapCount;
    GfxLightmapArray* lightmaps;
    ...
};
```

Probe payload:

```cpp
struct GfxReflectionProbe {
    vec3_t origin;
    GfxLightingSH lightingSH;
    GfxImage* reflectionImage;
    GfxReflectionProbeVolumeData* probeVolumes;
    unsigned int probeVolumeCount;
    float mipLodBias;
};

struct GfxReflectionProbeVolumeData {
    vec4_t volumePlanes[6];
};
```

### Corrected latent lightmap patch defect

The old uncompiled local lightmap OAT patch incorrectly referenced
`world->lightmapCount/world->lightmaps`. It was corrected to
`world->draw.lightmapCount/world->draw.lightmaps` and now also preserves nullable
primary/secondary retail GfxImage roles.

Relevant patch directory:

```text
tools/t6_gfxworld_lightmap_oat_patch/
```

### Reflection OAT catalog patch

Added:

```text
tools/t6_gfxworld_reflection_probe_oat_patch/
```

It emits exact dense probe index, origin, SH V0/V1/V2, nullable reflectionImage,
volume planes/count and mipLodBias. Runtime `GfxTexture*` values are deliberately
not archival identities.

The combined registration patch registers independent lightmap and reflection
GfxWorld dumpers; pinned `IObjWriter` supports multiple dumpers for one XAsset
class because it appends them to a vector and runs every dumper.

## Reflection manifest + portable GLB archive

Implemented:

```text
tools/t6_world_reflection_probe_manifest_v2.py
tools/test_t6_world_reflection_probe_manifest_v2.py
tools/t6_world_reflection_probe_glb_embed_v1.py
tools/test_t6_world_reflection_probe_glb_embed_v1.py
```

Manifest v2:

- exact surface `reflectionProbeIndex` join;
- dense index 0 is valid; no sentinel is inferred;
- nullable reflectionImage remains null;
- exact T6 GfxImage identity retained separately from OAT filename;
- exact pinned OAT filename mapping (`*` -> `_`);
- flat staging conflicts/path mismatches fail closed;
- origin/SH/volume planes/mipLodBias retained.

GLB archive v1:

- embeds each unique present exact DDS once as an untyped bufferView;
- preserves DDS bytes verbatim, including cubemap faces/mips/native pixel format;
- records SHA-256, byte count, bufferView and GfxImage identity;
- null reflectionImage creates no dependency;
- no standard glTF image/texture/material binding is created;
- missing accounting is by unique present T6 GfxImage identity.

## Strict GLB parser

`tools/t6_glb_parse_v1.py` was added for post-processing production GLBs.
It returns logical `buffers[0].byteLength` bytes, not the BIN chunk's container
padding. It rejects malformed/multiple/unknown chunks and nonzero BIN padding.

This prevents archive append stages from accidentally turning GLB alignment
padding into source asset bytes.

## Concurrent production pipeline

Parallel work advanced the production pipeline independently:

- v6: authoritative retail world-vertex format registry gate;
- v7: render-state-aware OAT material archival;
- v8: renderer-neutral render-state contract + retail-D3D11-grounded wgpu state.

Our work was layered on top rather than overwriting those revisions.

### Production pipeline v9

Added:

```text
tools/t6_oat_world_textured_export_pipeline_v9.py
tools/test_t6_oat_world_textured_export_pipeline_v9.py
```

v9 calls the full v8 production path, then deterministically post-processes the
final GLB to optionally attach:

1. canonical generated shader recipes;
2. exact reflection probe manifest + verbatim DDS archive.

It rebuilds the post-pass twice and requires byte-identical raw/GLB output and
identical semantic stats.

This makes the current architectural chain:

```text
retail world sidecars
 -> vertex-format registry gate
 -> normalized geometry
 -> exact OAT materials/images
 -> material DDS portability
 -> nullable lightmap archive
 -> exact material GPU render-state contract
 -> retail-grounded wgpu state
 -> canonical generated shader recipes (when supplied)
 -> exact reflection probe ownership + raw DDS archive (when supplied)
 -> portable GLB
```

## Per-surface lighting ownership

`tools/t6_world_surface_lighting_material_split_v1.py` provides a reversible
renderer-facing split keyed by:

```text
(sourceMaterialIndex, lightmapIndex, reflectionProbeIndex, primaryLightIndex)
```

Geometry buffers/accessors are untouched and original source materials remain an
immutable prefix. This exists because T6 lighting ownership is per surface while
Blender material datablocks are commonly shared.

## Immediate remaining blockers to next visual successor to v31

1. **Run the real Blender runtime regression.** The test exists; current runtime
   infrastructure did not provide an executable/runner. Do not mark it passed.
2. **Recover/serialize the actual 120-row Nuketown generated shader recipe table**
   (especially the pixel-shader-archetype field) from retained/internal build
   state or independently reconstruct it from retail evidence. OAT preserves
   TechniqueSet identity, but that alone is not the missing full v31 table.
3. **Compile exact `vN` height DAGs** into the renderer/Blender application layer.
4. **Wire exact layered normal state into the live visual graph**, including
   tangent-basis orientation validation against the T6->glTF axis contract.
5. **Carry layered-specular XYZW through the exact reflection/lighting consumer**
   without generic metallic/roughness conversion.
6. **Compile/run the corrected OAT lightmap + reflection-probe dumpers** against
   retained retail Nuketown and archive the resulting catalogs/hashes.
7. **Stage/archive exact reflection DDS cubemaps** from that catalog and run v9.
8. **Promote the 65 reflection residual fetches only after a pinned-corpus final
   closure run** proves them.
9. Continue downstream primary-light/light-grid/shadow/output composition proofs
   as required; directional secondary lightmap and most reflection mechanics are
   no longer generic unknowns.

The next large downloadable map should be promoted only after these contracts
are actually applied/validated visually. Keeping v31 internal until then avoids
shipping another hundreds-of-megabytes artifact whose shader data is present but
not visibly consumed.
