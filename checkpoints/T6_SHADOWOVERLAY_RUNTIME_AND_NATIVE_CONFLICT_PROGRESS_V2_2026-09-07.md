# T6 shadowoverlay runtime + native dependency conflict progress v2

Date: 2026-09-07

## Scope

This checkpoint keeps two related but distinct workstreams separate:

1. the **authoritative native `shadowoverlay` family**, whose remaining proof is runtime/executable-only;
2. the **generic Nuketown Material/TechniqueSet duplicate-dependency census**, which is a broader T6 shader/material correctness problem.

It also records the demotion of the old `pimp_technique_shadowoverlay_5255c888` tuple so later work cannot accidentally restore it as a retail target.

## Authoritative serialized shadowoverlay family

The exact native family remains:

`Material shadowoverlay`

→ `TechniqueSet trivial_shadowoverlay_14e2e827`

→ declared type `unlit`

→ `Technique pimp_technique_trivial_7bf1260`

→ VS `pimp_shader_hdr_933ab43.hlsl`

→ PS `pimp_shader_trivial_3981dec1.hlsl`

with exact pixel argument:

`colorMapSampler = sampler.feedbackSampler`

The family is byte-identical in the native SP, MP, and Zombies startup bundles. See:

- `T6_SHADOWOVERLAY_NATIVE_ALL_MODES_FAMILY_V1_2026-09-07.md`
- `T6_SHADOWOVERLAY_SHADER_SEMANTICS_AND_EXE_BOUNDARY_V1_2026-09-07.md`
- `T6_SHADOWOVERLAY_RUNTIME_TARGETS_V1_2026-09-07.md`

Exact T6 source identities already closed from pinned OpenAssetTools source:

- `TEXTURE_SRC_CODE_FEEDBACK = 0x8` / `feedbackSampler`
- `CONST_SRC_CODE_FILTER_TAP_0 = 0x1A` / `filterTap[0]`

The exact 5600-byte native pixel shader arithmetic is already closed independently from SHA-pinned DXBC/RDEF/disassembly evidence.

## Demoted old shadowoverlay candidate

The tuple:

- `pimp_technique_shadowoverlay_5255c888`
- 592 bytes
- SHA-256 `cc2f2805aef4899b24ed1a181f816bfcdfd18c6ab876a1172cae11f0abd20d71`

is **not** an authoritative retail target.

`T6_SHADOWOVERLAY_TARGET_PROVENANCE_AUDIT_V1_2026-09-07.md` establishes that its name/size/hash entered the repository as probe literals without a source artifact. The complete green 215/215 retail FastFile census found zero occurrence of that exact name and zero occurrence of the `pimp_technique_shadowoverlay_` stem.

Any workflow file or diagnostic artifact whose historical label still says `exact target` for this tuple must be read as a **scoped unproven-candidate probe**, not retail target authority. Generic absence/closure tools remain reusable; the old candidate-specific invocation carries no positive target provenance.

## Exact retail executable identity

Required client identity:

- file historically supplied as `t6mp(1)(1).exe`
- bytes `12,850,328`
- SHA-256 `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`
- PE32 / Intel i386
- image base `0x00400000`
- PE timestamp `2013-05-24 19:30:57`

Retained File Library analysis products preserve this identity, but the raw executable bytes are not currently materialized in the active corpus.

### Public ZIP negative

Workflow `.github/workflows/t6_shadowcookie_retail_exe_probe_v1.yml` run `34164688816` attempted exact range recovery from the referenced public full-game ZIP64 archive and failed with:

`no candidate t6mp executable entries found`

This agrees with the independently retained complete executable inventory for that archive: only redistributable/setup executables are present.

### User R2 explicit-path negative

Workflow `.github/workflows/t6_r2_retail_exe_exact_probe_v1.yml`:

- commit `a52a0076344c054e0073ae8fc436555e5c576201`
- run `34164827501`
- artifact `10033798975`
- artifact digest `sha256:729e7e54364aa4818aa9c6376309b922475d8df140598b2c81f5c46c9d8dc27c`

Result:

- candidate paths tested: `12`
- reachable: `0`
- exact SHA matches: `0`
- all 12 explicit paths returned HTTP `404`

The tested bases were:

- `https://r2.houseofkublai.com/bo2`
- `https://r2.houseofkublai.com/bo2/pluto_t6_full_game`
- `https://r2.houseofkublai.com/bo2/Plutonium/pluto_t6_full_game`
- `https://r2.houseofkublai.com/bo2/game`

with names:

- `t6mp.exe`
- `t6mp(1)(1).exe`
- `t6mpv43.exe`

This excludes only those explicit 12 HTTP paths. It does not prove the executable is absent elsewhere.

Connected Google Drive searches for `t6mp`, `t6mp.exe`, `t6mp.rar`, and the exact SHA have not exposed a client executable. A visible `Call of Duty - Black Ops 2 (Server Files) [2013-03-11]` hierarchy contains server-file material and is not substituted for the exact client.

## Retail executable probe prepared for the real runtime targets

`tools/t6_retail_shadowcookie_material_probe_v1.py` was retargeted at commit:

`124fc5b49d1d1dcb4e7419d26dfff14aa8eeffe1`

Its output format is now `t6-retail-shadowoverlay-runtime-probe-v2`.

It still SHA/size/PE32 gates the exact retail client, but now inventories:

- exact built-in Material name `shadowoverlay` and neighboring shadow Materials;
- `sm_showOverlay`;
- `sm_showOverlayDepthBounds`;
- lineage-only routine-name anchors `RB_GetShadowOverlayDepthBounds`, `RB_SetSunShadowOverlayScaleAndBias`, and `RB_DrawSunShadowOverlay`;
- exact string pointer/xref provenance;
- candidate historical 8-byte built-in Material table windows;
- source-closed target identities `feedbackSampler=0x8` and `filterTap[0]=0x1A` as search metadata only.

The tool explicitly refuses to infer a runtime consumer, renderer-global slot, codeImages[8] image, filterTap[0] values, or draw scheduling from those names/numeric values alone.

## Native Nuketown dependency-conflict census

The host-resource failure from run `34170077645` was fixed without weakening authority by capping OAT build parallelism and preserving independent per-dump return codes.

Hardened workflow commit:

`44ba059e06e9315f01231e6ef13bfcca36d0a376`

Run `34171955671` proved all five required native OAT dumps can complete successfully; its next failure was diagnostic handling of a missing parent TechniqueSet, not FastFile/OAT extraction.

The structured conflict census was then expanded to retain four unresolved classes without choosing winners:

- missing parent TechniqueSet owner;
- divergent parent TechniqueSet definition;
- divergent parent-owned child Technique;
- missing parent-owned child Technique.

Relevant commits:

- `fc09639e492689c92aeff8efc1fd3ea5b03262f6`
- `865c970dee4ec9175fed7ddbae49af8c16b1e373`

### Complete real conflict result

Run `34172208730`, artifact `10036058009`, reached a complete structured diagnostic census before the production v4 fail-closed census intentionally stopped on unresolved duplicate semantics.

Summary over ordinary Nuketown Materials:

- ordinary native Materials: `702`
- generated Materials excluded: `120`
- unique TechniqueSets referenced: `106`
- checked parent-Technique relations: `1,970`
- divergent parent-owned child conflicts: `58`
- missing parent TechniqueSet owner conflicts: `2`
- divergent parent TechniqueSet definition conflicts: `0`
- missing parent-owned child conflicts: `0`
- total unresolved conflicts: `60`
- authoritative winners selected: `0`

The 58 divergent child conflicts are concentrated in nine duplicate TechniqueSets. The two owner-universe gaps are:

- `hdr_create_lut2dv_827z0f8q` — Material `mp_nuketown2020_lut`
- `mc_lit_sm_r0c0d0n0s0_qwq4q449` — two Materials

These two gaps are not precedence questions and remain separate owner-universe work.

## Quarantined lineage projection

The conflict-lineage projection remains explicitly non-authoritative.

Run `34172396171`:

- artifact `10036115875`
- digest `sha256:d65d909ea0415400865d1722d581867eee050c6fa5ffbc854d7efac4b5684997`

Projection summary:

- total conflicts: `60`
- authoritative winners: `0`
- unique lineage-priority predictions: `57`
- lineage-priority ties: `0`
- owner-universe gaps: `2`
- unmapped conflicts: `1`

The 57 predictions choose `/tmp/patch_out` only under the quarantined reconstructed priority hypothesis:

- ordinary map flag `0x00008000` → lineage priority `5`
- patch flag `0x00000008` → lineage priority `13`

The one deliberately unmapped conflict is:

- TechniqueSet `mc_lit_sm_r0c0n0x0_q361191u`
- Technique `pimp_technique_debugperformance_65f8920f`
- declared type `debug performance`
- parent owners `common_mp` + `patch_mp`
- affects `93` Materials

No `common_mp` zone flag/priority was guessed, so this conflict remains unresolved.

Runtime `DB_GetZonePriority` / `DB_OverrideAsset` / `DB_LinkXAssetEntry` behavior must still be source-closed against exact T6 runtime evidence before any lineage prediction may feed production authority.

## Scoped candidate absence diagnostic

Run `34172396171` also scanned four successful map/shared OAT Technique roots containing:

- `3,488` physical Techniques
- `276` TechniqueSets

It found zero filename hits and zero 592-byte/SHA hits for the **demoted unproven candidate** `pimp_technique_shadowoverlay_5255c888` tuple, including under alternate filenames.

This result is diagnostic only. The stronger retail statement is the complete 215/215 FastFile provenance audit, and neither result turns the old tuple back into an authoritative target.

## Current exact next gates

### Native shadowoverlay runtime

The serialized/shader side is already closed. Remaining T6-native runtime proof is:

1. obtain or rematerialize the exact SHA-matching retail client bytes;
2. identify the retail renderer-global/equivalent Material slot receiving native `shadowoverlay`;
3. close the retail draw/consumer path;
4. close the concrete image written to code-image source `0x8` for that draw;
5. close the producer and exact values written to code-constant source `0x1A` / `filterTap[0]`;
6. close render-target/shadow-map identity and scheduling.

Historical T5/OpenBO2 behavior remains search guidance only.

### Generic native Material/Technique dependencies

1. source-close retail duplicate-XAsset winner semantics;
2. determine the exact `common_mp` zone flag/priority rather than assigning one by analogy;
3. expand the owner universe for the two missing TechniqueSets;
4. rerun the authoritative v4 census only after those gates are closed.

## Proof boundary

Nothing in this checkpoint promotes:

- the old 592-byte shadowoverlay candidate;
- guessed map/patch/common precedence;
- historical renderer routine names;
- server-build behavior;
- passive string adjacency;
- appearance-based shader selection.

All authoritative statements above come from exact native OAT outputs, SHA-pinned shader artifacts, complete retail FastFile census evidence, exact workflow return codes/artifacts, or previously source-closed T6 definitions. Runtime producer/consumer and duplicate-XAsset selection remain open until independently closed.
