# T6 Nuketown static material alias closure v2 — 2026-09-06

This checkpoint advances the fresh `mp_nuketown_2020` static-XModel reconstruction from exact retail-source evidence. It does not use an old combined GLB as production input.

## Inputs

- `NUKETOWN_ALL_STATIC_XMODEL_EXTRACTION_MANIFEST_V3.json`
  - bytes: 4,030,192
  - SHA-256: `7a9ea51cd9b88f07b09e94ab8a754b35814e8dceb3b9563c6a4d6f3d7afde836`
- decoded retained playable-static material proof
  - bytes: 97,761
  - SHA-256: `e1704755fdf365eb97c47f517afe0173152ca4a3ae702b309cb4d02981380423`
- expanded retail `mp_nuketown_2020` stream
  - bytes: 154,653,476
  - SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`

## v2 exact-geometry route

v2 adds a second independent closure route on top of the retained LOD0 proof and strict same-XModel multi-anchor propagation.

Reusable static geometry references encode exact block-5 VIRTUAL destination addresses. For each source XModel that has such references, v2 pairs the packed destination address with the exact serialized source range and replays the remaining rigid XSurface allocations using the retail PC32 destination-alignment contract:

- `GfxPackedVertex`: align 16
- `XRigidVertList`: align 4
- `XSurfaceCollisionTree`: align 4
- `XSurfaceCollisionNode`: align 16
- `XSurfaceCollisionLeaf`: align 2
- `XSurfaceTri16`: align 16
- `materialHandles`: align 4

Every later independently observed geometry pointer must equal the replayed VIRTUAL address. Source ranges must close exactly at each model's `geometrySerializedEnd`. If a model also has an independently solved strict material-array base, both routes must agree exactly.

## Result

Static source population:

- 349 static XModels
- 901 packed block-5 material references
- 286 unique packed material targets

v2 geometry replay:

- 26 source XModels obtain exact material-handle-array bases from reusable geometry pointers
- 254 / 254 independently observed geometry-address checks pass
- zero source-range drift
- zero strict-base disagreements
- zero alias conflicts

Closure improvement:

- v1: 93 / 286 unique targets, 516 / 901 references
- v2: **106 / 286 unique targets, 548 / 901 references**
- exact unique targets added: **13**
- exact packed references added: **32**
- remaining: **180 unique targets / 353 references**

Newly admitted identities include exact slots for the desk lamp, recessed kitchen-light family, pool towel, dish mug, bedside drawer, yellow cup warmer, mailbox, Ficus foliage, hydro plant, and generator families. They are admitted by VIRTUAL-address evidence, not naming similarity.

## Local artifacts produced and verified

- local resolver: `t6_nuketown_static_material_alias_resolve_v2.py`
  - bytes: 28,239
  - SHA-256: `26b5237eec5f1cfbeeb457370733880f86f090bc82f78ab6c0fc7a1d530eb153`
- full v2 manifest:
  - bytes: 495,741
  - SHA-256: `b1f636bc4c919620c966ad0dc1a3d4a1eaeb6c593902db93e94303a16188b508`
- compressed manifest payload:
  - bytes: 38,581
  - SHA-256: `5f04e4d1881b63fea4d6ff27a6c4397132ca5aa735b64736b518dcd17a136ad4`

The large full manifest remains an internal generated artifact until its compressed repository payload is promoted. The hashes above pin it exactly.

## Proof boundary

No one-anchor material inference is accepted. No old GLB material assignment, filename similarity, material-name similarity, visual appearance, or ordering-only guess is accepted. A reusable-geometry replay is admitted only when every available downstream geometry anchor agrees with the same native-alignment cursor.

## v3 route now opened

The next exact route is cross-XModel VIRTUAL cursor propagation. The static stream contains many source-contiguous XModel runs, including independently anchored consecutive controls such as XAssets 29 -> 30 -> 31 and 217 -> 218. Those controls will be used to validate a Material/GfxImage tail walker before the cursor is propagated into previously unanchored neighboring XModels. Unsupported inline asset classes fail closed rather than being skipped.
