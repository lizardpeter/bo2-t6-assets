# T6 Final-Output Symbolic Reversal Checkpoint — v25 — 2026-09-05

This checkpoint continues `T6_SHADER_LIGHTING_REFLECTION_V23_2026-09-05.md` and
records the new final-output reversal branch.  Preserve all earlier source-closed
generated diffuse/normal/specular/lightmap/reflection state; this stage does not
replace any of it with generic PBR assumptions.

## Important correction to old conversational shorthand

The authoritative Nuketown generated-material worldVertFormat histogram is the
one enforced by the current recovery implementation:

```text
worldVertFormat 1: 95 materials
worldVertFormat 2:  7 materials
worldVertFormat 3: 17 materials
worldVertFormat 6:  1 material
```

Source:

`tools/t6_nuketown_generated_shader_recipe_recover_v1.py`

Do not regress to older conversation notes that described this population as
0/1/3/7.  The repository recovery code and its retained strict gates are the
authoritative contract.

## Starting point retained from v23

- Production visual pipeline through v23:
  - exact generated diffuse/vN recipes;
  - exact layered normal decode/transform/basis playback metadata;
  - exact generated specular XYZW state for Nuketown;
  - raw lightmap DDS archive + derived PNG preview;
  - per-GfxSurface lightmap preview material ownership;
  - reflection archive remains separately preserved.
- Blender v8 can compute the source-closed directional secondary-lightmap RGB
  state but deliberately does not connect it to final material shading.
- Reflection closure remains 5823/5888; the final 65 are not promoted here.
- Real Blender v7/v8 runtime fixtures remain committed, but hosted Actions has
  repeatedly failed with zero executed job steps.  No real Blender pass should
  be claimed from those runs.

## Final-output symbolic v1

Commit:

`7d84c8b4afa1b51e5bf602fb721499be0adf14e7`

Tool:

`tools/t6_generated_slot4_final_output_symbolic_v1.py`

Purpose: create the missing forensic bridge between already-proven shader
subgraphs and the still-unpromoted final output equation.

For every canonical generated material it resolves:

```text
Material recipe TechniqueSet
 -> OAT techsets/<TechniqueSet>.techset slot 4 "lit"
 -> exact techniques/<Technique>.tech
 -> exact pixelShader asset
 -> exact shader_bin/ps_<asset>.cso bytes
```

Then it:

- parses strict DXBC/RDEF metadata;
- maps texture and sampler bind registers to exact reflected names;
- symbolically executes supported SM4 instructions;
- supports structured IF/ELSE/ENDIF state merging;
- preserves DISCARD side effects separately;
- keeps every output-register write instead of filtering to a known lightmap
  dependency;
- serializes all `o0.xyzw` lanes explicitly, including unwritten lanes;
- preserves the complete DAG and exact per-output texture-resource ancestry;
- fails closed on unsupported opcodes, unresolved RDEF registers, malformed
  control flow, read-before-write or incomplete o0.rgb.

This is an assembly-level expression graph only.  It does not name a physical
lighting equation.

## Final-output symbolic v2

Commit:

`94cbfa3a39d19bd53457cc73db3468a222a2d7c8`

Regression:

`093c8e9d5ad7c0a83c0edd35f1740defbedc1cc7`

Files:

- `tools/t6_generated_slot4_final_output_symbolic_v2.py`
- `tools/test_t6_generated_slot4_final_output_symbolic_v2.py`

Hardening:

1. `sample_d*` derivative operands retain all four source components rather than
   being scalarized.
2. Branch-merge `undefined` sentinels may exist internally only when dead; any
   undefined node reachable from a written output fails closed.

The regression covers derivative operand width, dead-vs-reachable undefined
state, and v1->v2 promotion behavior.

## Final-output symbolic v3 — canonical shader identity gate

Commit:

`d1afd5362874312e0b51eacdbb5dad12732239fd`

Regression:

`2b5e69fc95902393052bf2d88fa99c6fddb49aab`

Files:

- `tools/t6_generated_slot4_final_output_symbolic_v3.py`
- `tools/test_t6_generated_slot4_final_output_symbolic_v3.py`

Key correction: canonical recovered recipes encode shader identity as:

```text
pixelShaderArchetype = "sha256:<64hex>"
```

v3 requires, for every material:

```text
pixelShaderArchetype hash
== proof.pixelShaderSha256 (when present)
== exact OAT slot-4 CSO SHA-256
```

Strict Nuketown mode independently rechecks:

- 120 generated materials;
- 34 exact TechniqueSets;
- 34 unique slot-4 pixel shaders;
- zero cross-TechniqueSet shader reuse;
- worldVertFormat histogram `1:95, 2:7, 3:17, 6:1`;
- shader model 4.0 throughout;
- canonical recovery counters agree with those invariants.

It records an exact generated slot-4 pixel-shader set SHA for future pinned
comparisons.

## Production pipeline v24 — final-output proof sidecar

Commit:

`d38a0860a1d4a2b9e6253889cf1afa28d82aea09`

Regression:

`ae085cdadca64dc8e0ad56c2dee361042b8f4653`

Files:

- `tools/t6_oat_world_textured_export_pipeline_v24.py`
- `tools/test_t6_oat_world_textured_export_pipeline_v24.py`

v24 preserves v23 visual data byte-for-byte.  When canonical generated recipes
and an exact OAT shader root are both supplied, it runs symbolic v3 twice and
requires byte-identical JSON regeneration.

Output sidecar:

```text
<map>.generated_slot4_final_output_symbolic_v3.json
```

The sidecar is proof data only; it is not embedded into material shading.

The production visual GLB/glTF bytes remain inherited unchanged from v23, apart
from generation filename/version renaming.

## Exact final-output resource ancestry v1

Commit:

`649f8426cad6a423ce2784b971ca37a3e4653d71`

Regression:

`e392fdc5432ca52d3bc96cec1db3803a006acbf6`

Files:

- `tools/t6_generated_final_output_resource_ancestry_v1.py`
- `tools/test_t6_generated_final_output_resource_ancestry_v1.py`

This independently walks every written `o0` root through the serialized full DAG
and recomputes the exact set of RDEF-named `textureSample` resources that can
influence that lane.  Stored symbolic-v3 ancestry must match exactly.

Exact-name classes only:

- `colorMapSampler`, `colorMapSampler1..3` -> generated color
- `normalMapSampler`, `normalMapSampler1..3` -> generated normal
- `specularMapSampler`, `specularMapSampler1..3` -> generated specular
- `lightmapSamplerPrimary` -> primary lightmap
- `lightmapSamplerSecondary` -> secondary lightmap
- `reflectionProbeSampler` -> reflection probe

Anything else remains `unclassified` by exact reflected name.  Similar-looking
names are deliberately not generalized.

The sidecar records:

- exact o0 lane resource sets;
- rgb union/intersection sets;
- exact-name class coverage;
- unknown output resources;
- output ancestry signatures and counts;
- independent ancestry check count;
- zero ancestry mismatches required.

This proves dependency only, not arithmetic or physical meaning.

## Production pipeline v25 — ancestry sidecar

Commit:

`b88ace08ddb25583f0a5f3dde9f8515b26546ad8`

Regression:

`32a88a3f8927a36443adaaef3c255a74dca98a9b`

Files:

- `tools/t6_oat_world_textured_export_pipeline_v25.py`
- `tools/test_t6_oat_world_textured_export_pipeline_v25.py`

When the v24 full-output sidecar exists, v25 runs the ancestry verifier twice and
requires byte-identical regeneration.

Output sidecar:

```text
<map>.generated_final_output_resource_ancestry_v1.json
```

Again the visual GLB/glTF bytes are inherited unchanged.

## Current strongest production chain

```text
retail world/OAT bytes
 -> exact geometry/material/image dependencies
 -> canonical generated recipes
 -> exact vN diffuse DAGs
 -> exact normal sample/transform/paired-VS basis state
 -> exact generated specular XYZW state
 -> exact raw lightmap/reflection archives
 -> lightmap preview + per-surface ownership
 -> v23 visual artifact
 -> v24 exact complete slot-4 o0 symbolic DAG sidecar
 -> v25 independently recomputed exact output-resource ancestry sidecar
```

Blender remains at:

```text
v7 exact generated diffuse + layered normal
 -> v8 exact directional secondary-lightmap RGB state
 -> final shading connection intentionally absent
```

## Validation boundary in the current ChatGPT runtime

There is no local checkout of `bo2-t6-assets` in the active filesystem, so the
new pure-Python regressions could not be executed directly in this runtime.
They are committed as deterministic regression drivers.

The previously configured GitHub-hosted Blender workflow continues to exhibit a
runner-provisioning failure with zero executed steps.  Do not reinterpret that
infrastructure failure as a shader/test result.

## Immediate continuation targets

1. Run the v3/v24/v25 chain against the retained exact Nuketown OAT shader dump
   and archive the generated sidecar hashes/statistics.
2. Use the v25 exact resource ancestry to classify which of the 34 Nuketown
   slot-4 shaders' `o0.rgb` depend on:
   - generated color;
   - normal maps;
   - generated specular;
   - secondary/primary lightmap;
   - reflection probe;
   - any currently unclassified RDEF resources.
3. Match already-proven subgraphs into the full output DAG instead of guessing a
   final HLSL/PBR formula.  Recommended anchor order:
   - generated RGB compositor / explicit RGB-square state;
   - directional secondary-lightmap equation;
   - reconstructed normal state;
   - generated specular XYZW state;
   - reflection probe state;
   - primary/dynamic light/shadow/light-grid terms.
4. Promote a final composition only when the complete arithmetic path to `o0`
   is source-closed for the target shader family.
5. Keep the final 65 reflection fetches unpromoted until pinned retained proof
   exists.
6. Compile/run the corrected OAT GfxWorld lightmap/reflection dumpers on retained
   retail Nuketown and archive exact catalog/output hashes.
7. Repeat the full evidence chain on representative MP and Zombies/DLC maps
   before generalizing any Nuketown-only contracts.
