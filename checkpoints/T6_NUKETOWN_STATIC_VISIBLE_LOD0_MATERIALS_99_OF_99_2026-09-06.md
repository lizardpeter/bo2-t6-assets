# T6 Nuketown visible static LOD0 material closure — 99 / 99 — 2026-09-06

This checkpoint closes the canonical visible LOD0 static-XModel material-identity tranche for the fresh retail `mp_nuketown_2020` reconstruction.

## Result

- canonical visible LOD0 packed material targets: **99 / 99 exact**
- unresolved targets: **0**
- alias conflicts: **0**
- no old GLB material assignment participates in the final promotion

The last unresolved target is now closed exactly:

- block 5 / VIRTUAL offset **26,834,420**
- exact Material: `mc/mtl_ac_prs_vehicle_sheet_a`

The final six targets that were open at the 93 / 99 checkpoint are therefore all closed:

- `16,786,500` -> `mc/mtl_nt_2020_plaster_whitewall_01`
- `17,416,648` -> `mc/jun_art_metal_white`
- `25,197,340` -> `mc/mp_m_vista_bldgs_01`
- `26,084,736` -> `mc/glass_clear_wall_opaque_white`
- `26,117,744` -> `mc/mtl_nt_2020_vista_cart`
- `26,834,420` -> `mc/mtl_ac_prs_vehicle_sheet_a`

## Final car-material proof

Reusable verifier:

- `tools/t6_nuketown_car_material_alias_proof_v1.py`
- verifier commit: `09ae9008bbedddce39d58ed74af104332933dda7`

CI proof run:

- workflow: `T6 Nuketown car material alias proof v1`
- run: `34055340462`
- result: **success**
- exact packed consumers reproduced: **7 / 7**
- conflicts: **0**

Stored proof:

- `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_CAR_MATERIAL_ALIAS_PROOF_V1.json`
- bytes: **4,602**
- SHA-256: `23a86b48490da4a555b72fd0c30d633928cf4108443b67fb60876f8fb4f98335`
- storage commit: `1f4902dfccc68af5908a9857cc4f5587a691ddde`

The proof regenerates the retail XModel interval from the exact expanded FastFile and source-checks the pinned OpenAssetTools T6 loader semantics at commit `2ca512abe7cb82d70a94d5ad7846043c3978862d`.

XAsset 289 `ny_harbor_veh_civ_car_a_10` has one `FOLLOWING` Material pointer slot and dispatches the inline Material `mc/mtl_ac_prs_vehicle_sheet_a`. XAssets 290 through 296 each contain one packed Material pointer to block 5 / offset `26,834,420`.

The retail loader generator registers asset pointer-array slots with `AddPointerLookup` at their normal-block address, and packed TEMP-asset pointers resolve through `ConvertOffsetToAliasLookup`. Therefore a later packed Material pointer can only resolve through an already registered Material pointer slot. The final address is consequently the exact XAsset 289 Material-handle slot by loader construction, not by ordering, naming, adjacency, mesh similarity, or appearance.

## Exact retail source identity

- retail FastFile SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- expanded bytes: **154,653,476**
- expanded SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`

## Forward-only boundary

This closes visible static LOD0 **material identity**, not the entire downloadable map by itself.

The next promoted visual successor still has to merge forward:

1. exact R2/IPAK texture extraction and binding for world/static/generated materials;
2. exact lightmap, reflection-probe and retail sky integration;
3. the six MapEnt/destructible cars plus retained animation/support scenes;
4. all v31-and-later generated-shader-facing contracts without generic PBR substitution;
5. a fresh full-map rebuild from retail-derived layers;
6. the existing v25 scene-policy/release floor with **zero failures**.

No future exporter should reopen or heuristically replace these 99 material identities. If a source replay disagrees, it must fail closed and be investigated as a loader/reconstruction regression.
