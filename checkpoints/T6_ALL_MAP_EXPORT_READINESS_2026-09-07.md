# T6 All-Map Export Readiness — 2026-09-07

This checkpoint separates three targets that must not be conflated:

1. **Generic retail extraction** — given a supported retail T6 map FastFile and its shared dependencies, recover the canonical map/world geometry, placements, exact Material/GfxImage identities and renderer metadata without map-specific visual guesses.
2. **Generic fail-visible Blender export** — open the recovered map in Blender with every material routed either through an exact solved shader/replay path or an explicit unresolved family; no silent generic-PBR fallback.
3. **Retail-render parity for every map** — reproduce all visible shader arithmetic, dynamic code resources, lightmaps/reflection/fog/HDR, sampling behavior, blend/depth state and special material families closely enough that Blender/output is a faithful retail renderer rather than merely a complete asset scene.

## Current cross-map evidence

The reversal is no longer Nuketown-only at the engine-format level. Five SHA-pinned retail worlds are retained as broad structural canaries:

- `mp_nuketown_2020`
- `mp_raid`
- `mp_hijacked`
- `zm_prison`
- `zm_tomb`

These span multiplayer and Zombies and already validate important shared T6 structures rather than one map layout.

### World/material structure already cross-map

- Retail FastFile expansion and GfxWorld extraction are source-derived and regression-gated.
- The five-world Material state census parses exact Material child layout/state serialization across all five retained worlds.
- The five-world layered-material census proves map-local generated/layered identities and worldVertFormat selection without assuming numeric layer tokens are globally reusable.
- Special material family census exists across the retained worlds and intentionally keeps shader arithmetic outside the identity proof until source-closed.
- World vertex formats 4/5 and layered normal/secondary-UV transport have retained-byte proofs on independent maps rather than Nuketown-only fitting.

### Global shader resources already cross-map

The retained-byte DXBC/RDEF guards scan every strictly valid embedded DXBC container in all five retained worlds:

- `lightmapSamplerSecondary` is source-closed as TEXTURE2D + SAMPLER at bind point 13 across **4,531 unique shaders** with zero binding failures.
- `reflectionProbeSampler` is source-closed as TEXTURECUBE + SAMPLER at bind point 15 across **5,868 unique shaders** with zero binding failures.
- Reflection coordinate/weight/mip proofs and directional-secondary-lightmap work are separately retained and cross-checked against these resource identities.

This is strong evidence that the important lighting/resource ABI is engine-wide rather than a Nuketown-local convention.

## Nuketown depth now achieved

Nuketown remains the deepest complete renderer canary:

- canonical full-map scene already includes the world/static/MapEnt/skybox population;
- exact generated population: **120 generated Materials / 34 TechniqueSets / 34 slot-4 pixel shaders**;
- fresh retail recovery through generated recipe v3 is green;
- **34/34 exact generated final-output shaders are arithmetic-lowerable by the Blender symbolic backend**;
- **0 blocked shaders, 0 unsupported ops, 0 unknown ops, 0 branches, 0 discards** in reachable `o0` output;
- reachable generated texture sampling uses only `sample` and `sample_l`;
- every observed `sample_l` instruction is the exact `reflectionProbeSampler` path, reducing generated sampling to ordinary 2D sampling plus explicit-LOD cube reflection sampling;
- generated `o0.xyzw` compilation with one shared DAG cache passed in real Blender 4.0.2 and terminates in Emission with no Principled fallback;
- the v51 renderer-neutral replay contract now has a real-Blender resolver for exact static Material constants/textures, dynamic T6 code constants/samplers and shader-native inputs; unresolved replay owners fail closed;
- solved lprobe opaque/glass final diffuse + reflection + fog + HDR arithmetic now has a real-Blender Emission output bridge, so Principled is no longer required once exact global inputs are supplied.

## Native ordinary-material census generalization

The previous native census correctly exposed an architectural assumption rather than a corrupt asset: `trivial_9z33feqw` is a valid ordinary TechniqueSet with **no `lit` binding**.

`tools/t6_oat_material_shader_census_v3.py` therefore replaces the lit-only census model with an all-TechniqueSet model:

- generated `materials/generated/*` remain excluded for the separate exact generated-DAG path;
- every declared TechniqueSet type is retained verbatim;
- every referenced Technique/pass and every emitted shader stage is hashed exactly;
- duplicate TechniqueSet owners require byte identity;
- duplicate Technique owners require identical parsed pass/stage shader identities;
- non-lit-only materials are counted rather than treated as failures;
- no type label is promoted to shader semantic meaning merely from its name.

The synthetic v3 regression is green. The full pinned-OAT Nuketown 702-ordinary-material retail census is running as Actions run `34147912267`.

## Practical readiness estimates

These are engineering-path estimates, not asset-count completion percentages.

### Generic retail map extraction

**~90–95% closed.**

Why this is high:

- core FastFile/GfxWorld/Material/image machinery is already reusable;
- geometry, placement and material-state formats are validated on independent MP and Zombies maps;
- the main global lighting resource ABI is cross-map validated over thousands of real shaders;
- the production export pipeline is map-parameterized through v51 rather than hard-coded as a Nuketown-only exporter.

Remaining risk is concentrated in rare map/DLC-specific asset/layout families and dependency-zone ownership, not the basic world extraction architecture.

### Generic fail-visible Blender export for arbitrary maps

**~82–90% closed.**

Already reusable:

- exact geometry/material/image transport;
- generated symbolic-DAG compiler and full-output Emission backend;
- v51 replay-contract leaf dispatch;
- exact lprobe opaque/glass local and final-output arithmetic;
- cross-map lightmap/reflection resource identities;
- fail-closed shader-family routing principle.

Still required before claiming every map:

1. finish the all-TechniqueSet native census and classify the finite ordinary/special shader-family tail;
2. implement exact ordinary 2D sampler-state adapters and explicit-LOD cube sampling/bake support;
3. provide global model-light/grid/SH/fog/HDR runtime values or exact baked equivalents;
4. integrate per-technique D3D blend/depth/alpha-test state with explicit reporting where Blender cannot reproduce destination blending;
5. run the complete pipeline against additional MP/Zombies/DLC maps and make any truly new family fail visibly instead of falling back.

### Retail-render parity for every map

**~75–85% closed.**

The source reversal is ahead of Blender here. The main remaining work is backend/runtime reproduction:

- 3D model-light lookup or exact baking;
- reflection cube explicit LOD;
- light-grid / SH values and map/object bindings;
- fog/HDR runtime constants;
- exact sampler/filter/mipmap behavior where Blender image nodes are not equivalent to D3D11;
- destination blending and other framebuffer-state behavior Blender cannot express directly;
- rare special families such as water/unlit/TV/burning/raw-normal/shadow paths after exact shader census classification;
- exhaustive DLC/campaign/Zombies canaries, not only the five retained worlds.

## Interpretation

The project is substantially closer to **“run the same extractor on every map”** than to **“every map is already retail-perfect in Blender.”** The remaining work is no longer primarily decoding map geometry. It is converging on a reusable renderer backend plus a finite special-family tail.

A realistic sequence to whole-game coverage is:

1. close the 702 ordinary-material all-TechniqueSet Nuketown census;
2. turn its exact groups into solved/unsolved family counts;
3. finish the two generated sampling adapters (2D `sample`; reflection `sample_l`) and shared global-resource providers/bakes;
4. produce one zero-silent-fallback Nuketown `.blend`;
5. batch-run Raid + Hijacked + Mob + Origins through the same Blender exporter;
6. add every remaining retail MP/Zombies/DLC map as a corpus run, treating only genuinely new exact shader/asset families as blockers;
7. extend the same engine-level machinery to campaign maps where their zone/dependency population introduces additional families.

The critical architectural point is that new maps should now mostly add **data and a bounded number of new exact families**, not require a new extraction pipeline.
