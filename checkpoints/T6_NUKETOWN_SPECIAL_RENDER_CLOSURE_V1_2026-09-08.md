# T6 Nuketown special render closure v1 — 2026-09-08

## Durable state

The finite `mp_nuketown_2020` special-material tail is now closed at the shader-arithmetic, native Material-input, and shadow-depth-state layers under the exact pinned OAT/five-FastFile evidence universe.

Canonical machine manifest:

- `manifests/render/T6_NUKETOWN_SPECIAL_RENDER_CLOSURE_V1.json`
- promotion commit: `4a050fcfbfa8e3756c7b441c8fd66a65b9408557`

Canonical green producer run:

- head: `e9898d435233670cfc65a8e8477b82e53719730d`
- workflow run: `34272241620`
- job: `102216446009`
- artifact: `10074278623`
- artifact ZIP SHA-256: `6b227cfa4dc6f8e73894b9497de6c4640fac4dd684e973ebffbf46f1655df9d9`

The final head includes both the exact T6 `R_HashString` Material-argument join and deterministic branch-DAG state ordering. Earlier raw-normal DAG digests produced before deterministic state ordering are not promotion authority.

## Exact source authority

Pinned OpenAssetTools commit:

`9dca965366541504b71fa8cfb7ac049cb9b717e1`

Exact five-root FastFile universe:

- `mp_nuketown_2020.ff` — `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- `common_mp.ff` — `93fe48b0f0d8cc6844be875ccad94e0cfcf635f62eeff00ac33f2f668a77cb77`
- `common_patch_mp.ff` — `95622d93d4fb761db311a123cd073bed34ea48c9c711d2c11bce4170dd08bae9`
- `patch_mp.ff` — `459077cda8e4a1457f7ee7d8f6c5e0abf30f41767a21ff6744df6a4307cbce1e`
- `code_post_gfx_mp.ff` — `b7bce1dbe94692b1668ae9a1c83a4dcf008979ee5d5f79b3d2e619c23a1002b3`

The selected seven special TechniqueSets have zero dependency on the separately unresolved duplicate-parent winner set. The global retail `t6mp.exe` duplicate-parent winner is still not claimed authoritative.

## Unlit / emissive closure

The 11 special Materials produce 19 selected unlit/emissive program bindings across five exact pixel shaders. The final input-binding proof closes:

- 19 / 19 exact DXBC RDEF → dumped Technique argument assignments
- 19 / 19 exact Technique material arguments → native Material texture entries
- 11 unique image identities
- 4 exact sampler states
- 6 Material-constant matches
- 5 non-Material constant leaves retained explicitly as runtime/code inputs

Generated evidence file SHA-256:

`T6_NUKETOWN_SPECIAL_MATERIAL_INPUT_BINDING_V1.json` → `57e6d23ccc8afe83ac9de606f8ad313269a6f7971bdb3cc33c05195a7e89c22e`

Evidence digest:

`951c82b88b4ca770a71e3d56ea33f9975d3e2e0df1540929dee18cdb9e747263`

## Raw-normal glass closure

Exact target:

`wpc/glass_clear_wall_opaque_white`

All 22 lit Technique variants reduce to 20 unique exact pixel shaders. Full assembly-level output reconstruction is closed for every RGBA output:

- 20 unique pixel shaders
- 9 straight-line shaders
- 11 branch shaders
- 26 exact IFs
- 0 discard shaders
- 0 symbolic blockers
- 80 output components
- 446 texture/sample sites
- 15,323 canonical DAG nodes
- 20 unique canonical DAGs

Generated full-output file SHA-256:

`T6_NUKETOWN_RAWNORMAL_FULL_OUTPUT_V1.json` → `46743020cb2ee0d30389fc234a9110aee189d344e56193343466a1a6c9aed243`

Canonical evidence digest:

`a766c8755b3cc3c590c49549557c43075451260ae5c68652d46062ff6355ed45`

Every one of the 446 sample sites is then ownership-classified from exact DXBC RDEF plus exact dumped Technique arguments:

- 60 Material-owned sample sites
- 386 engine/code-owned sample sites
- 60 Material-owned constant leaves
- 132 engine/code-owned constant leaves
- 3 unique Material images
- 1 unique Material sampler state
- 6 unique Material argument hashes
- 6 exact engine-owned resource bindings

Generated binding file SHA-256:

`T6_NUKETOWN_RAWNORMAL_INPUT_BINDING_V1.json` → `aabc241f5be593b7ff83da9c01d4afa9be9891b8a722083350c0f2e3595b95cf`

Evidence digest:

`6383fc1f186232bc788303ecfa82e90c1771c953eda68136f0e2a4c754cc5f03`

### Exact native Material texture inputs

All three use `{ clampU:false, clampV:false, clampW:false, filter:"aniso4x", mipMap:"linear" }`.

- `ColorMap`, T6 nameHash `0xa0ab1041` → native `colorMap` → `~-gglass_clear_wall_opaque_c`
- `Normal_Map`, T6 nameHash `0x942cbff0` → `glass_clear_wall_n`
- `SpecularAndGloss2`, T6 nameHash `0x11594eb2` → `~~-gglass_clear_wall_s-rgb&gl~32bf418c`

Technique/Material identity is joined using exact T6 `R_HashString(name,0)` (`djb2_xor_nocase`, seed 0, uint32). This is why source spellings such as `ColorMap` and native `colorMap` are the same runtime Material argument identity. Hash collisions fail closed.

### Exact native Material constants

- `NormalHeightMultiplier`, `0xb0dc3167` → `[0.23999999463558197, 0.0, 0.0, 1.0]`
- `ReflectionAmount`, `0x3ccffe8b` → `[0.0, 0.0, 0.0, 1.0]`
- `SpecularAmount`, `0xa8cd1103` → `[0.0, 0.0, 0.0, 1.0]`

### Exact engine/code texture inputs retained externally

- t9 / s9: `shadowmapSamplerSun` / `SunShadowSamplerState`
- t10 / s10: `shadowmapSamplerSpot` / `SpotShadowSamplerState`
- t11 / s11: `dlightAttenuationSampler`
- t12 / s12: `attenuationSampler`
- t13 / s13: `lightmapSamplerSecondary`
- t15 / s15: `reflectionProbeSampler`

Their runtime contents are not replaced with guessed textures or constants.

## Shadowcaster closure

The two exact Materials are:

- `wpc/caulk_shadow_primary`
- `wpc/shadowcaster`

Their five-state payloads are identical. Both depth-bearing slots use the same exact shader pair:

- VS SHA-256 `b77f42b646f07d63214ebf3132d187f13073329756c437c91dfcfe7131952ba3`
- PS SHA-256 `ba6a650c7c7f4a7703a13ad59ba939958af63e114e90ef67d74c4acad7fecf0b`

Depth prepass is exact:

- RGB write: false
- alpha write: false
- depth write: true
- depth test: `less_equal`
- cull: back
- polygon offset: `offset0`
- alpha test: disabled
- blending: disabled
- front stencil: equal / keep / keep / keep

Build-shadowmap-depth is exact:

- RGB write: false
- alpha write: false
- depth write: true
- depth test: `less_equal`
- cull: back
- polygon offset: `offsetShadowmap`
- alpha test: disabled
- blending: disabled

Generated state file SHA-256:

`T6_NUKETOWN_SHADOWCASTER_STATE_V1.json` → `6281652051a88e827b1628b15599a3e64abec357f197236506e655630cc72e1a`

Evidence digest:

`2a65724bd1c9ae321d936d794517a0bb3e472dbf05a10695aa37623ab2c97e3a`

## Implementation boundary

This checkpoint is enough to implement the special-family Material side without heuristic family-name shading. Exact portable replay still needs the runtime-owned values/textures that the native shader consumes: scene/light constant buffers, sun/spot shadow maps, attenuation resources, the secondary lightmap and reflection probe.

Those inputs must be supplied by the Blender approximation layer or the Rust renderer according to an explicit replay contract. Omitting them may be a useful preview mode, but it is not exact T6 rendering.

No HLSL source reconstruction is claimed; the authoritative shader behavior here is the exact DXBC assembly-level DAG plus exact native input binding/state evidence.
