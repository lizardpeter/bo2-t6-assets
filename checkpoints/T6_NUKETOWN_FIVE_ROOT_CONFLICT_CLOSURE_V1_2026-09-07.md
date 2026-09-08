# T6 Nuketown five-root native dependency/conflict closure v1

Date: 2026-09-07

## Result

The Nuketown native Material/TechniqueSet dependency universe is now complete enough to eliminate the two prior missing-parent TechniqueSet gaps.

The corrected five physical roots are:

1. `mp_nuketown_2020.ff`
2. `common_mp.ff`
3. `common_patch_mp.ff`
4. `patch_mp.ff`
5. `code_post_gfx_mp.ff`

All five TechniqueSet dumps plus the map Material dump completed successfully under the same pinned OpenAssetTools build.

The remaining unresolved set is now **purely duplicate-runtime-selection work**:

- missing parent TechniqueSet owners: **0**
- missing same-root child Techniques: **0**
- divergent parent TechniqueSet definitions: **0**
- divergent parent-owned child Techniques: **58**
- total unresolved conflicts: **58**
- winner selected by retail-client census: **0**

The 58 duplicate-child conflicts affect **269 ordinary Nuketown Materials** and are concentrated in **9 TechniqueSets**.

## Native run

Workflow run: `34176055029`

Artifact:

- ID: `10037272717`
- name: `T6_NUKETOWN_NATIVE_MATERIAL_SHADER_CENSUS_V5_FIVE_ROOT`
- digest: `sha256:fcf52ea7d6cedec03866beea397197f3c7ffea8a854119ecd63024868b624b06`

All required OAT commands returned `0`:

- map Material dump
- map TechniqueSet dump
- `common_mp` TechniqueSet dump
- `common_patch_mp` TechniqueSet dump
- `patch_mp` TechniqueSet dump
- `code_post_gfx_mp` TechniqueSet dump

Physical counts in this run:

- map Materials: `822`
- ordinary native map Materials after generated-row exclusion: `702`
- generated Materials excluded from conflict authority: `120`
- map TechniqueSets: `109`
- `common_mp` TechniqueSets: `126`
- `common_patch_mp` TechniqueSets: `0`
- `patch_mp` TechniqueSets: `41`
- `code_post_gfx_mp` TechniqueSets: `108`

The conflict census checked `1,999` Material→declared-Technique relations over `106` unique referenced TechniqueSets.

## Closed former owner gaps

The old four-root census reported two missing-parent TechniqueSets:

- `hdr_create_lut2dv_827z0f8q` used by `mp_nuketown2020_lut`
- `mc_lit_sm_r0c0d0n0s0_qwq4q449` used by two Materials

Those were not absent retail assets. They were outside the supplied four-root shader universe.

A separate exact native closure against SHA-pinned `code_post_gfx_mp.ff` completed green in run `34175258046`, artifact `10037018901`, digest `sha256:1da03a67c5a6971872cd0172ed7dbc733c74a4b853b131963ed320718fde469f`.

Pinned OAT physically emitted both parent TechniqueSets and all declared child Technique/shader dependencies without parser/dependency errors.

Consequently the five-root conflict census now has:

- `missingParentTechniqueSetOwnerConflictCount = 0`
- `missingParentOwnedChildConflictCount = 0`

## Exact remaining duplicate distribution

All 58 remaining conflicts are `divergent-parent-owned-child`.

Owner combinations:

- `/tmp/map_out` + `/tmp/patch_out`: **57**
- `/tmp/common_out` + `/tmp/patch_out`: **1**

No remaining divergence uses `code_post_gfx_mp` as a conflicting parent owner in this Nuketown set.

The nine affected TechniqueSets are:

- `mc_lit_sm_r0c0_77e21qq8` — 24 divergent child Techniques
- `mc_lit_sm_r0c0s0_986ezzjq` — 24
- `distortion_81587199` — 2
- `effect_8f63534j` — 2
- `mc_lit_sm_r0c0n0s0_zqq1fze7` — 2
- `effect_50567j38` — 1
- `effect_w77q49e8` — 1
- `mc_lit_sm_r0c0n0x0_q361191u` — 1
- `trivial_9z33feqw` — 1

## Exact PC dedicated-server projection

The exact SHA-pinned PC dedicated-server proof has now been extended to include `code_post_gfx_mp`:

- `patch_mp`: allocFlags `0x02`, priority `65`
- ordinary built-in MP map: `0x8000`, priority `57`
- `common_mp`: `0x80`, priority `54`
- `code_post_gfx_mp`: `0x08`, priority `52`

The `code_post_gfx_mp` row is byte-gated by:

- `code_post_gfx` base-string copy into `CODE_FAST_FILE_NAME`
- exact `_mp` suffix append into the same buffer
- `DB_LoadGraphicsAssetsForPC` assigning allocFlags `0x08`
- the exact `DB_GetZonePriority` low-flag dispatch/index/jump tables
- selected return target `0x0055027b`, returning `0x34 = 52`

Server proof files:

- `tools/t6_pc_server_xasset_override_proof_v2.py`
- `manifests/engine/T6_PC_SERVER_XASSET_OVERRIDE_PROOF_V2.json`
- `tools/t6_oat_conflict_pc_server_projection_v2.py`

The exact server-only projection over the corrected five-root conflict census reports:

- source conflicts: `58`
- unique PC-server predictions: `58`
- predicted `/tmp/patch_out`: `58`
- owner-universe gaps: `0`
- unmapped server zone classes: `0`
- priority ties: `0`
- authoritative retail-client winners: `0`

Thus **one retail-client duplicate-XAsset precedence closure would clear the entire remaining 58-conflict Nuketown Material/Technique blocker at once**, if and only if the exact retail client independently reproduces the relevant rule/flags/priorities.

## Proof boundary

The five-root OAT conflict identities and physical ownership are authoritative for the pinned retail FastFiles and pinned OAT dump semantics.

The PC dedicated-server duplicate projections are authoritative only for exact `CoDMPServer_PC.exe` SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d` with its exact linker MAP.

They are **not** authority for retail `t6mp.exe` SHA-256 `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`.

Therefore the production retail-client v4 census remains correctly fail-closed. Run `34176055029` is intentionally red only at that production census step; all native dumps, conflict enumeration, and PC-server projection stages are green.

No retail duplicate winner may be selected from load order, zone naming, server behavior, OpenBO2 lineage, PS3 flags, or appearance.
