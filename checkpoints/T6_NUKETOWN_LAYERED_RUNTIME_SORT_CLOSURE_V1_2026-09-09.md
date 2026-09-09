# T6 Nuketown Layered Runtime Sort Closure V1 — 2026-09-09

## Result

The generated texture-table ordering problem is closed for the exact Nuketown runtime Material population without inventing the unknown historical standalone component row order.

Exact green replay:

- workflow: `.github/workflows/t6_nuketown_layered_runtime_sort_closure_v1.yml`
- run: `34416657965`
- head: `580645a1c27449c449b28f1ac5d48cfa563a3750`
- artifact: `10129335774` / `T6_NUKETOWN_LAYERED_RUNTIME_SORT_CLOSURE_V1`
- artifact ZIP SHA-256: `53bbc145018fe0e0a4e8a367bc55c79b6975bf7f49ef96a2ba103455b92a08d8`
- result JSON SHA-256: `e8515acb17ad7025c7b00786a543446d89b96abe34171096a2bde986ff116fb1`

## Exact runtime rule

The SHA-pinned `CoDMPServer_PC.exe` machine code for `Material_CreateLayered @ 0x00A4DA60` closes the post-construction table sort:

- `Material+0x54` → texture count
- `Material+0x60` → texture table
- `qsort` element width → `0x10` bytes
- comparator → `0x00A4D630`, SHA-256 `89c3ef79d0956caceb677fd742d376f28895d8788fd9ad7c1e88a4535d840952`
- PDB aliases for that same comparator include both `CompareHashedMaterialTextures` and `CompareHashedMaterialConstants`
- the comparator reads the first `uint32`; for `MaterialTextureDef` that is `nameHash`
- T6 `nameHash` is `R_HashString(name,0) = djb2_xor_nocase(name,0)`

Immediately afterward the function independently sorts `Material+0x64` constants using count `Material+0x55`, element width `0x20`, and the same first-`uint32` hash comparator.

## Exact Nuketown corpus replay

Against the SHA-pinned `mp_nuketown_2020.ff` and pinned OAT `9dca965366541504b71fa8cfb7ac049cb9b717e1`:

- generated layered Materials: **120 / 120**
- generated texture rows: **460**
- generated tables strictly ascending by exact T6 `nameHash`: **120 / 120**
- generated tables with a `nameHash` collision: **0**
- target-bearing generated Materials: **14**
- missing standalone component identities represented: **7 / 7**
- target layer occurrences represented: **15 / 15**
- target texture-row occurrences represented: **24 / 24**

A useful concrete example is `*100n_236n(wpc/asphalt_smooth01_dark:wpc/asphalt_road_dark_dec)`. The previously unresolved three-row component contributes, after layer-1 renaming:

1. `normalMap1` → `0x9434AEDE` → runtime index 1
2. `colorMap1` → `0xB60D1850` → runtime index 3
3. `specularMap1` → `0xD2866322` → runtime index 4

Those rows are interleaved with rows from the other layer according to the global hash sort. That is why generated layered order cannot be used as evidence for the original standalone component row order.

## Reclassification of the six open standalone row orders

The historical source order of the six multi-row missing standalone component Materials remains **OPEN**. It is not reconstructed here.

It is, however, now proven **not to be a Nuketown generated-runtime rendering degree of freedom**. `Material_CreateLayered` sorts the complete generated table after layer-specific row renaming, and every exact Nuketown generated table has unique hash keys. Therefore every possible pre-sort permutation of the already source-closed component rows converges to the same exact final runtime texture table.

This removes the six standalone row-order gaps from the Nuketown rendering blocker list while preserving them as historical/source-provenance gaps.

## Retained files

- `manifests/materials/T6_PC_SERVER_LAYERED_MATERIAL_SORT_V1.json`
- `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_LAYERED_RUNTIME_SORT_CLOSURE_V1.json`
- `tools/t6_nuketown_layered_runtime_sort_closure_v1.py`
- `.github/workflows/t6_material_texture_sort_runtime_probe_v2.yml`
- `.github/workflows/t6_nuketown_layered_runtime_sort_closure_v1.yml`

## Proof boundary

This result does not synthesize the seven absent standalone Material XAssets, does not claim their unknown TechniqueSets/constants/state bits, and does not establish retail-client executable equivalence from the dedicated server. The exact retail FastFile plus pinned OAT is the observed generated-table authority; the server executable independently supplies the structural runtime sort semantics. Historical standalone serialization order remains explicitly open where not source-closed.
