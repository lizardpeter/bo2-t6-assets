# T6 Nuketown Ficus material-alias proof v1 — 2026-09-06

## Scope

This checkpoint source-closes the three previously unresolved packed Material* targets used by the Ficus static family. It does **not** use a retained combined/full-map GLB as identity evidence.

Canonical source:

- expanded `mp_nuketown_2020` stream: 154,653,476 bytes
- SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`
- fresh all-static manifest: 4,030,192 bytes
- SHA-256: `7a9ea51cd9b88f07b09e94ab8a754b35814e8dceb3b9563c6a4d6f3d7afde836`

## Exact boundary proof

XAsset 254 `mlv/nt_tree_ficus_lrg_01` reuses XAsset 246 `mlv/nt_tree_ficus_lrg_01_sway` geometry through exact block-5 VIRTUAL pointers.

The final reused source allocation is XAsset 246 surface 8's triangle array:

- source start: `24692569`
- bytes: `756`
- source end: `24693325`
- virtual start: `24584032`
- virtual end: `24584788`
- source - virtual delta: `108537`

`24693325` is exactly XAsset 246 `geometrySerializedEnd`, so the next serialized object is its 9-entry, 4-byte material-handle array. Therefore the exact material-handle array VIRTUAL base is `24584788`.

The raw retail handle words at that source boundary are:

`FFFFFFFF FFFFFFFF FFFFFFFF A1772255 A1772259 FFFFFFFF A1772255 A1772259 A1772269`

The packed references decode to slots 0, 1 and 5 of that exact array.

## Closed aliases

- block 5 / `24584788` -> `mlv/mtl_p6_tree_ficus_lrg_01_bark1`
- block 5 / `24584792` -> `mlv/t5_foliage_tree_standard_gobo_128`
- block 5 / `24584808` -> `mlv/mtl_p6_tree_ficus_lrg_01_foliage_noshadow`

XAsset 254 consumes exactly `[24584788,24584792,24584808]` twice, one triplet per retained LOD group.

## Canonical LOD0 progress

- before: 90 / 99 unique packed LOD0 targets exact
- added here: 3
- after: **93 / 99**
- remaining: **6**
- alias conflicts: **0**

## Reproducible artifacts

- verifier source (decoded): `tools/t6_nuketown_ficus_material_alias_proof_v1.py`
  - bytes: 13,303
  - SHA-256: `14601c26f6cbb862b31f5e61a33e605728496b0038d8764262556d0a349ad2b8`
- proof manifest (decoded): `T6_NUKETOWN_FICUS_MATERIAL_ALIAS_PROOF_V1.json`
  - bytes: 4,710
  - SHA-256: `7804651c27192248f17c89f24b612dec6b56700ad42e987cf78ceabcec8ac5fb`

Repository stores the source and manifest as zlib+base64 payloads to keep the checkpoint compact. Decode with base64 then zlib before execution/inspection.

## Proof boundary

No alias is promoted from material-name similarity, model naming, mesh similarity, surface order alone, adjacency, render appearance, or an old GLB assignment. The array base is fixed by the exact source/virtual end of a reusable retail geometry allocation and the material identities are the defining inline slots from the fresh source-derived manifest tied to the same FastFile SHA.
