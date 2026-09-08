# T6 Nuketown complete Material/shader census under exact PC dedicated-server precedence v1

Date: 2026-09-07

## Result

The complete ordinary Nuketown native Material → TechniqueSet → Technique → pass → shader census is now green when duplicate parent TechniqueSets are selected using the exact SHA-pinned **PC dedicated-server** precedence proof.

This is a decisive diagnostic result:

- ordinary native Nuketown Materials: **702 / 702 resolved**
- generated Materials excluded for the separately closed generated-DAG path: **120**
- unique referenced TechniqueSets: **106**
- unresolved Materials: **0**
- divergent selected parent-owned dependencies: **0**
- parent-owned Technique dependencies resolved: **1,695**
- exact Technique-type/shader groups: **1,686**
- authoritative retail-client winners emitted: **0**

Therefore there is no hidden Material/Technique dependency blocker behind the current retail-client duplicate-XAsset selection gate. For this five-root Nuketown universe, exact duplicate runtime selection is the sole remaining reason the production retail-client v4 census does not close.

## Workflow / artifact

Workflow run: `34176399898`

Artifact:

- ID: `10037392221`
- name: `T6_NUKETOWN_PC_SERVER_MATERIAL_SHADER_CENSUS_V1`
- digest: `sha256:adcc7e964d163dc3e7401c5ecbd4394ab849df74ae2a19a46a294ddab34017b2`

The run completed fully green, including:

1. server-projected-census guardrails;
2. exact pinned OAT cache verification;
3. SHA verification of all five retail FastFiles;
4. native map Material dump;
5. native TechniqueSet dumps from map, common, common_patch, patch, and code_post_gfx_mp;
6. complete server-projected Material shader census;
7. artifact upload.

## Authority domains

The physical assets and same-root parent→child provenance come from SHA-pinned retail FastFiles and pinned OAT commit:

`9dca965366541504b71fa8cfb7ac049cb9b717e1`

The duplicate-parent selection comes only from the exact PC dedicated-server proof:

- `CoDMPServer_PC.exe`
- bytes: `13,711,872`
- SHA-256: `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`

Server MP priority order:

1. `patch_mp`: `0x02` → **65**
2. ordinary built-in MP map: `0x8000` → **57**
3. `common_mp`: `0x80` → **54**
4. `code_post_gfx_mp`: `0x08` → **52**

The server census is explicitly:

- `authoritativeForPcDedicatedServerBuild = true`
- `authoritativeForRetailClient = false`
- `authoritativeRetailClientWinnerCount = 0`

## Nine duplicate parent TechniqueSets

Exactly nine parent TechniqueSets required server selection. Every parent `.techset` is byte-identical across its physical duplicate owners; the divergence is in child Technique payloads beneath those parents.

All nine selected `/tmp/patch_out` at exact server priority 65:

1. `distortion_81587199`
2. `effect_50567j38`
3. `effect_8f63534j`
4. `effect_w77q49e8`
5. `mc_lit_sm_r0c0_77e21qq8`
6. `mc_lit_sm_r0c0n0s0_zqq1fze7`
7. `mc_lit_sm_r0c0n0x0_q361191u`
8. `mc_lit_sm_r0c0s0_986ezzjq`
9. `trivial_9z33feqw`

Eight are map↔patch duplicate parents. `mc_lit_sm_r0c0n0x0_q361191u` is common↔patch.

This selection resolves all **58** previously enumerated divergent child Technique relations.

## Complete green census counts

The final server-projected census reports:

- ordinary native Materials: `702`
- lit-binding Materials: `620`
- non-lit-only Materials: `82`
- unique TechniqueSets: `106`
- declared Technique types: `29`
- parent-owned Technique dependencies: `1,695`
- exact Technique-type/shader groups: `1,686`
- unique vertex shader payloads: `159`
- unique pixel shader payloads: `1,342`
- duplicate parent selections: `9`
- non-parent alternate Technique definitions retained: `269`
- divergent non-parent alternate definitions retained: `110`
- unresolved Materials: `0`

The non-parent alternate definitions are evidence only; v4 same-root provenance does not allow them to override the selected parent-owned child.

## Why this matters

The production five-root retail-client census previously established:

- no missing parent TechniqueSets;
- no missing parent-owned child Techniques;
- no divergent parent TechniqueSet definitions;
- exactly `58` divergent duplicate child Technique relations;
- `269` affected ordinary Materials;
- zero selected retail winners.

This full server-projected run applies only the separately byte-closed server duplicate-parent rule and immediately resolves all `702` ordinary Materials end-to-end.

That proves, for the present Nuketown Material/shader scope, that the remaining production blocker is not another missing asset, parser defect, shader dependency, or provenance gap. It is specifically **retail-client duplicate-XAsset precedence**.

## Retail client remains blocked

The historical exact retail multiplayer client identity remains:

- `t6mp.exe`
- bytes: `12,850,328`
- SHA-256: `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`
- image base used by prior static work: `0x00400000`

The exact same SHA/size is independently indexed by a 2018 Hybrid Analysis report, but that service currently marks the sample itself unavailable. The current Drive/File Library/public-game archive/R2 probes likewise do not expose retrievable raw client bytes.

Therefore the server result must not be copied into the production client census. Retail closure still requires one of:

1. the exact client bytes and direct static proof of the relevant DB routines/load flags;
2. retained exact client instruction fixtures covering the same rule;
3. genuine retail-client runtime duplicate-chain observation on a divergent asset.

## Durable tools

- `tools/t6_pc_server_xasset_override_proof_v2.py`
- `manifests/engine/T6_PC_SERVER_XASSET_OVERRIDE_PROOF_V2.json`
- `tools/t6_oat_material_shader_census_pc_server_v1.py`
- `tools/test_t6_oat_material_shader_census_pc_server_v1.py`
- `.github/workflows/t6_nuketown_pc_server_material_shader_census_v1.yml`

## Proof boundary

This checkpoint does not claim that retail `t6mp.exe` selects patch for these duplicates. It establishes only that:

- the retail FastFile dependency universe is physically complete for the 702 ordinary Nuketown Materials;
- all non-precedence dependencies resolve;
- the exact PC dedicated-server build selects patch for all nine duplicate parents and thereby yields a fully green census;
- retail-client duplicate selection remains the sole unresolved authority gate for this Material/shader census.
