# T6 Final-Output Semantic Anchors — v29 — 2026-09-05

Continuation of `T6_FINAL_OUTPUT_SYMBOLIC_V25_2026-09-05.md`.

This checkpoint records the first semantic boundaries anchored *inside* complete
generated slot-4 final-output DAGs.  Do not convert these proofs into generic
PBR semantics or infer unproved final-lighting arithmetic.

## Retained non-regression boundaries

- Nuketown recovery: 120 generated materials / 34 TechniqueSets / 34 unique
  slot-4 pixel shaders / zero cross-TechniqueSet shader reuse.
- Authoritative Nuketown worldVertFormat histogram: `1:95, 2:7, 3:17, 6:1`.
- Reflection closure remains 5823/5888; 65 residuals unpromoted.
- Generated specular state remains exact XYZW state with no generic
  metallic/roughness/F0 interpretation.
- Visual GLB bytes remain unchanged by all v24-v29 final-output proof stages.
- No real Blender v7/v8 execution has occurred in the current environment;
  hosted runner attempts had zero executed steps.

## v26 — generated RGB-square semantic anchor

Tool:

`tools/t6_generated_final_output_rgb_square_anchor_v1.py`

Regression:

`tools/test_t6_generated_final_output_rgb_square_anchor_v1.py`

Production:

`tools/t6_oat_world_textured_export_pipeline_v26.py`

Production regression:

`tools/test_t6_oat_world_textured_export_pipeline_v26.py`

Commits:

- anchor `47e1db3544f88d8f90e981df7e4a65602faf8639`
- anchor regression `0ba5f65aa701e98b331f970cf035b5762244d7e1`
- v26 `7b0abdcdab481219c2772f965efde8298fa098a8`
- v26 regression `9b94a997e9ee7257ec7ca414a186322e936c3693`

The exact already-proven encoded-generated-RGB -> RGB-square boundary is located
inside each `o0.rgb` DAG as a unique reachable `mul(X,X)` whose texture ancestry
is exclusively exact `colorMapSampler*` resources and whose RGB sample lane
matches the output lane. Color alpha samples remain legal ancestry because exact
layer-weight DAGs consume them.

Strict production refuses missing or ambiguous square anchors.

## Directional-lightmap explicit probe and semantic promotion

Explicit structural probe:

`tools/t6_generated_final_output_directional_lightmap_anchor_probe_v1.py`

Regression:

`tools/test_t6_generated_final_output_directional_lightmap_anchor_probe_v1.py`

Commits:

- probe `4915bbecf5afeb86a93ec039393e26fa66101b80`
- initial regression `72a0605d6870d91a773a53c11eb5599309e00a2f`
- regression fixture fix `7da032d103437946d81051e8ff926a19b4267ffa`

The probe matches:

```text
row0 = secondary(u, v/3)
row1 = secondary(u, v/3 + 1/3)
row2 = secondary(u, v/3 + 2/3)
direction = 2*row2.rgb - 1
factor = saturate(dot(direction,N))
rgb = row0.rgb/(row0.a+1e-6) + row1.rgb/(row1.a+1e-6)*factor
```

including exact `0x358637bd` epsilon, exact affine row relationship and final
`o0.rgb` ancestry.

### Important compiler-materialization clarification

The retained global proof distinguishes:

- 316 equations with explicit materialization;
- 15 equations with row0 normalization folded into final MAD.

The full symbolic engine lowers SM4 MAD by its exact instruction semantics to:

```text
add(mul(a,b),c)
```

Therefore the compiler's explicit-vs-folded materialization distinction can
vanish at expression-DAG level without any algebraic rewrite.

Semantic promotion:

`tools/t6_generated_final_output_directional_lightmap_anchor_v2.py`

Regression:

`tools/test_t6_generated_final_output_directional_lightmap_anchor_v2.py`

Commits:

- semantic anchor `bdfa0df4b1b58da74b4149371c1508bdfe15d28e`
- regression `6a4cfe9eb75c2190b3b2fade9ffd7d2db3ba15b0`

Strict semantic mode requires exactly one or two directional equations per
shader, matching the separately retained five-world invariant:

- 173 shaders;
- 331 directional equations;
- 15 one-equation shaders;
- 158 two-equation shaders;
- 0 shader failures.

The expression DAG deliberately does not claim whether an anchor originated
from the explicit or folded compiler materialization.

## v27 / v28 production

v27 diagnostic production:

`tools/t6_oat_world_textured_export_pipeline_v27.py`

Regression:

`tools/test_t6_oat_world_textured_export_pipeline_v27.py`

Commits:

- v27 `1fd8829d0eeaf696ca434f452fb65fc56cc5202c`
- regression `93fcfd60dc44f9922a22dc97cad951e6aeb2531d`

v27 intentionally allows zero explicit-probe matches as evidence while the
compiler-materialization issue is being normalized.

v28 strict semantic production:

`tools/t6_oat_world_textured_export_pipeline_v28.py`

Regression:

`tools/test_t6_oat_world_textured_export_pipeline_v28.py`

Commits:

- v28 `b64878f0a06ef065156e497b9a2d7e9d3f6c8740`
- regression `f4c458bbf5dd7d60f78174ec0aa88b764ca143a0`

v28 is a strict proof stage: one or two semantic directional-equation anchors
are required for every shader presented to the sidecar builder.

## Reusable exact DXBC ISGN/OSGN binding

Tool:

`tools/t6_dxbc_signature_v1.py`

Regression:

`tools/test_t6_dxbc_signature_v1.py`

Commits:

- parser `c9865d7dd7b43337bdaea92bf700abc7d56105ad`
- regression `9987d2acc836022b8ef67221090ff0bb0a342b41`

This extracts strict SM4 ISGN/OSGN register -> semantic identities using the same
24-byte signature-entry layout already used by retained T6 reflection proofs.
No pixel input semantic is inferred from register number.

## Exact final-output I/O signature sidecar

Tool:

`tools/t6_generated_final_output_io_signature_v1.py`

Regression:

`tools/test_t6_generated_final_output_io_signature_v1.py`

Commits:

- binder `7d3f497dd461daa2a4fa820dc2b383d7f40216a4`
- regression `2fc7a0ccb89ab8050b6e88c9141b3947357cde53`

Every full-output shader CSO is reopened by exact OAT relative path, re-hashed,
and its ISGN/OSGN parsed. Every used raw input symbol `vN.<lane>` must map to an
actual ISGN register/component mask; every written output register must exist in
OSGN.

This sidecar supplies proof-grade semantic mappings such as `TEXCOORD1/2/3` to
later final-output joins.

## Layered-normal final-output semantic anchor

Tool:

`tools/t6_generated_final_output_layered_normal_anchor_v1.py`

Regression:

`tools/test_t6_generated_final_output_layered_normal_anchor_v1.py`

Commits:

- anchor `764be1d2ae856788ad6757a5230a481a50708f4e`
- regression `8dfdbad3db35727e5bb9c0d4b7bb9445bb02f457`

For every generated TechniqueSet with a secondary normal-bearing layer, exactly
one directional equation must use:

```text
raw.xyz = TEXCOORD1.xyz
        + layeredX * TEXCOORD3.xyz
        + layeredY * TEXCOORD2.xyz
N.xyz = raw.xyz * rsq(dot(raw.xyz,raw.xyz))
```

Requirements:

- exact ISGN semantics, not register guesses;
- three raw components each contain exactly base + X-basis term + Y-basis term;
- the same layered-X root is shared across x/y/z;
- the same layered-Y root is shared across x/y/z;
- exact shared `rsq` root;
- dot contains exactly three `raw_i * raw_i` terms;
- exactly one v28 directional equation matches for each secondary-normal target.

This directly joins the separately retained universal layered-normal proof to the
specific downstream directional equation that consumes it. Any second
directional equation in the shader remains separately typed rather than being
forced into the same normal semantic.

## v29 production

Production:

`tools/t6_oat_world_textured_export_pipeline_v29.py`

Regression:

`tools/test_t6_oat_world_textured_export_pipeline_v29.py`

Commits:

- v29 `83b205d42b63d2f9257d54de0d3856c77345eae4`
- regression `922e961dd6c7040dcca6f46a0d569ddacb02fce5`

v29 emits, when the exact final-output DAG exists:

```text
<map>.generated_final_output_io_signature_v1.json
<map>.generated_final_output_layered_normal_anchor_v1.json
```

Both are regenerated twice and must be byte-identical. Visual GLB/glTF bytes are
inherited unchanged from v28.

## Current final-output proof stack

```text
v24 complete exact slot-4 o0 DAG
 -> v25 independent exact texture-resource ancestry
 -> v26 unique generated RGB-square anchors
 -> v28 strict semantic directional-lightmap equation anchors
 -> v29 exact ISGN/OSGN input semantics
 -> v29 exact layered-normal reconstruction -> directional-N join
```

## Immediate continuation

1. Anchor generated specular XYZW recurrence roots inside the full `o0` DAG and
   determine exactly where that state is consumed downstream. Do not reinterpret
   XYZW as generic PBR.
2. Join the separately retained reflection-probe subgraphs into the full `o0`
   graph and identify which directional equation / normal counterpart feeds
   reflection-related output.
3. Continue primary-light / light-grid / shadow terms only from exact RDEF names
   and assembly-level ancestry.
4. Promote a complete final equation only after every arithmetic path from the
   anchored generated RGB/lightmap/normal/specular/reflection states to `o0` is
   source-closed.
5. Run v24-v29 against the retained exact Nuketown OAT shader corpus when a
   runtime containing that corpus is available; archive all sidecar hashes and
   counts.
