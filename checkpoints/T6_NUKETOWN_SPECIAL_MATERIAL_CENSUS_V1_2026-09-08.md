# T6 Nuketown exact special Material census v1 — 2026-09-08

## Result

The finite `mp_nuketown_2020` special-world-material tail is now isolated end-to-end from the complete native Material → TechniqueSet → Technique → pass → shader census.

The exact population is:

- **11 Material uses**
- **7 TechniqueSets**
- families: **8 unlit + 1 raw-normal special + 2 shadowcaster**
- **85 exact Technique-type/shader groups**
- **33 unique pixel-shader payloads**
- **14 unique vertex-shader payloads**
- unresolved special Materials: **0**

Most importantly, **none of these seven special TechniqueSets depends on any of the nine duplicate parent TechniqueSets that still require retail-client precedence proof**:

`pcServerDuplicateParentSelectionDependencyCount = 0`

Therefore the Nuketown special-material tail is not blocked by the unresolved server-vs-retail duplicate-XAsset selection question. Its selected Material/Technique/pass/shader identities come from the physical SHA-pinned retail FastFiles and same-root pinned-OAT ownership without invoking the dedicated-server duplicate-parent rule.

## Exact special population

### Shadowcaster — 2 uses

`wpc_shadowcaster_wj6w5j60`

- `wpc/caulk_shadow_primary`
- `wpc/shadowcaster`

### Raw-normal special — 1 use

`wpc_sw4_3d_phong_rawnormal_8ejf1f28`

- `wpc/glass_clear_wall_opaque_white`

### Unlit — 8 uses

`wpc_sw4_3d_unlit_1layer_w29e37e5`

- `wpc/light_backlit_glass_green`

`wpc_sw4_3d_unlit_4layer_z17fejf2`

- `wpc/nt_2020_shuffleboard_screen_01`

`wpc_unlit_add_8ez3wzw3`

- `wpc/nt_2020_glass_glow_multicolor`

`wpc_unlit_blend_2840z6q0`

- `wpc/ao_decal_ramp`
- `wpc/ao_decal_square`

`wpc_unlitdecalblend_multiply_35079164`

- `wpc/decal_damage_wall_fillet`
- `wpc/decal_grunge_lightstain_04`
- `wpc/me_decal_adobe_top_01`

Every row above has `dependsOnPcServerDuplicateParentSelection = false` in the generated exact census.

## Exact visual shader identities

The seven exact `unlit` Technique-type groups reduce to only **five unique pixel shaders**:

- `19d4d2ce53fa78e1f3bb5cc3cc472f3b71d15c715eff0f5adc731d8ce1fc0370` — `pimp_shader_unlit_4ea12045.hlsl`
- `f483cbb31106fecb6ca2b0c381108c0b0e5ed879ae793476bf92b28d1c2ca262` — `pimp_shader_unlit_4b1d2e0b.hlsl`
- `e9820077a4df69228fd1626997270d7b31337f82eab6c26c1a14a33257424a0b` — `pimp_shader_unlitdecalblend_5c3f6d9c.hlsl`
- `cffae8606c1d91c9f9b2bb773053d05689b3f67dce7702507d61acf81878befc` — `pimp_shader_radiant_46ce1b1c.hlsl`
- `2a2510a4df2ae2c98a7c421ed3cb96fc617e5201747577dc36c158235e7c78c7` — `pimp_shader_vertcolorsimple_b871d333.hlsl`

The exact `emissive` groups use four of those same payloads; no separate unproven emissive shader family is required for this population.

The three special TechniqueSets that declare a `lit` path have these exact primary `lit` pixel shaders:

- `wpc_sw4_3d_unlit_1layer_w29e37e5` → `78fb2a01cdf3621f476598c6788d0eaf34cc0e5cf601803a3ec111c23d1f2571`
- `wpc_sw4_3d_unlit_4layer_z17fejf2` → `386e340bcd940e6e81624984dc88f07156b37d96741e5a5ad1ec9583b4941a55`
- `wpc_sw4_3d_phong_rawnormal_8ejf1f28` → `da4278ded596e6128b0134883815985f2fc79f9530b4eddf1b82b5dc0a247953`

The raw-normal family remains covered by the separately retained straight-line and branch-aware SM4 symbolic work; this checkpoint does not reinterpret it as generic PBR.

## Shadow/depth identity

Both exact `build shadowmap depth` and `depth prepass` groups resolve to the same exact stage pair:

- VS: `pimp_shader_transformonly_d4f4e04b.hlsl`
  - SHA-256 `b77f42b646f07d63214ebf3132d187f13073329756c437c91dfcfe7131952ba3`
- PS: `pimp_shader_null_3b4a8bd3.hlsl`
  - SHA-256 `ba6a650c7c7f4a7703a13ad59ba939958af63e114e90ef67d74c4acad7fecf0b`

This closes the shader identity for those passes. It does **not** by itself claim framebuffer/depth-write semantics; those remain governed by exact render-state decoding.

## Workflow / artifact

Run: `34268259389`

Artifact:

- ID: `10072729522`
- name: `T6_NUKETOWN_PC_SERVER_MATERIAL_SHADER_CENSUS_V1`
- ZIP SHA-256: `22f0ebfbe765af9ca2f089cbdc9c8d3248845b97552b1ab8c0d333cbda1621ce`

Generated full special result:

- `T6_NUKETOWN_SPECIAL_MATERIAL_CENSUS_V1.json`
- SHA-256: `57df76307c16d8c03e018a2746ef9641e0d8253ea8f9eaf520471ab31e75af9d`
- evidence digest: `f425c3d14b6a455003c1b07f52886463e0c826ddf8894bbfd6a87e40148c5bbe`

Compact repository seal:

- `manifests/render/T6_NUKETOWN_SPECIAL_MATERIAL_CENSUS_V1.json`

## Proof boundary

The special-family labels identify the finite map population; they are not used as a substitute for shader semantics. Material, TechniqueSet, child Technique, pass and stage identities come from the complete native pinned-OAT census over SHA-pinned retail FastFiles.

The complete ordinary census is still explicitly non-authoritative for retail duplicate-parent selection in general. The key result here is narrower and stronger: **the seven TechniqueSets in this special tail require no duplicate-parent selection at all**, so their identity closure is independent of the nine outstanding retail-client precedence cases.

No blend equation, depth state, sampling mode, shader arithmetic or runtime constant is inferred from a TechniqueSet name in this checkpoint.

## Next closure

The immediate next step is to compile all five exact non-lightmapped `unlit` pixel-shader payloads to complete `o0.xyzw` symbolic DAGs instead of filtering for lightmap dependency. Those exact DAGs can then be bound to Material textures/constants and emitted through the existing Blender replay backend. The shadow/depth pair can be routed separately as an explicit depth/no-color pass once the exact state map semantics are closed.
