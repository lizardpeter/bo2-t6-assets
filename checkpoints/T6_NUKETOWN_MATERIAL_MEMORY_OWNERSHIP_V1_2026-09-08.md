# T6 Nuketown MaterialMemory ownership closure v1 — 2026-09-08

The Nuketown GfxWorld surface-material ownership path is now closed from exact retail bytes and pinned loader semantics without a fitted pointer-catalog assumption or byte-pattern candidate selection.

## Exact source

- retail `mp_nuketown_2020.ff`: **38,472,064 bytes**
- retail SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- expanded bytes: **154,653,476**
- expanded SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`
- pinned OpenAssetTools: `Laupetin/OpenAssetTools@9dca965366541504b71fa8cfb7ac049cb9b717e1`

## Closed ownership path

The exact path is:

`GfxSurface.material packed alias`

→ `VIRTUAL block 5 MaterialMemory.material slot`

→ `GfxWorld MaterialMemory[327]`

→ `FOLLOW-owned Material child in slot order`

→ strict serialized 327-Material chain

→ exact `Material::techniqueSet`

→ exact `MaterialTechniqueSet::worldVertFormat`.

Pinned T6 source defines `MaterialMemory` as an 8-byte PC32 record containing `Material* material` plus `int memory`. `GfxWorld.txt` owns `materialMemory` with `materialMemoryCount`, and the generated array-loader path reads the fixed array before processing each element's nested child. Therefore the fixed `MaterialMemory[327]` source array ends exactly at the independently established first serialized Material child; it is not selected from nearby byte-pattern candidates.

## Exact MaterialMemory spans

- record count: **327**
- record bytes: **8**
- fixed array bytes: **2,616**
- physical start: **84,463,050**
- physical end exclusive: **84,465,666**
- first Material child start: **84,465,666**
- all 327 `MaterialMemory.material` members: **FOLLOW-owned**
- VIRTUAL block: **5**
- VIRTUAL start offset: **71,642,512**
- VIRTUAL end exclusive: **71,645,128**
- exact GfxSurface alias count: **327**
- alias stride: **8 bytes**

## Downstream non-regression

Binding the 327 surface aliases through MaterialMemory ownership retains the exact canonical world population:

- strict Materials: **327 / 327**
- vertex groups: **340**
- worldVertFormat groups:
  - format 0: **220**
  - format 1: **95**
  - format 2: **7**
  - format 3: **17**
  - format 6: **1**
- mixed-format groups: **0**
- unresolved surface Materials: **0**

## Negative controls retained

The prior v1 sidecar hypothesis that GfxSurface Material pointers were top-level MATERIAL XAsset-array slots is rejected by live retail execution. The first exact alias `0xa4452d91` is a valid packed block-5 pointer but is not aligned to the top-level XAsset pointer-array base.

The subsequent v2 nearby-signature scan is also rejected as an ownership method. It found two overlapping 327-record windows: the true loader-derived array at `84,463,050..84,465,666` and a false window shifted 8 bytes earlier. The false window works locally only because it overlaps 326 true rows plus a preceding `0xFFFFFFFF` word. Ownership is now derived from serialization order instead of choosing between those candidates.

## Hosted proof

- tool: `tools/t6_nuketown_material_memory_ownership_v1.py`
- tool commit: `93182a58e102e468de4584e96164890d2185f40d`
- workflow: `.github/workflows/t6_nuketown_material_memory_ownership_v1.yml`
- workflow commit: `d45ed66998c0a50f1f3676fbeec472efe95eade2`
- run: **34278198130**
- job: **102236314916**
- conclusion: **success**
- exact pass: `GREEN NUKETOWN MATERIALMEMORY OWNERSHIP`
- proof JSON bytes: **106,404**
- proof JSON SHA-256: `6b5786897436f9c291e38aacab75ba73baef64bcc86e60d542982754e956be7a`
- artifact ID: **10076551249**
- artifact ZIP bytes: **107,216**
- artifact ZIP SHA-256: `340d24ceb20f5a6b14d97898438e1af9bd14d11d3b9f48b973cb231d6c17799b`

Machine-readable summary: `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_MATERIAL_MEMORY_OWNERSHIP_V1.json`.

## Proof boundary

This closes Nuketown GfxWorld surface Material ownership and preserves exact Material → TechniqueSet → worldVertFormat binding. It does **not** by itself close all shader arithmetic, the two remaining generated-material sampler ambiguities, or full user-facing map parity. The next production gate is a source-sidecar v3 that consumes this exact ownership boundary and reruns the strict world audit/export before any real v52 promotion.
