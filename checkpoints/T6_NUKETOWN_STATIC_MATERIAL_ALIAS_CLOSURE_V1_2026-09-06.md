# T6 Nuketown static material alias closure v1 — 2026-09-06

This checkpoint advances the fresh `mp_nuketown_2020` static-XModel rebuild without using an old GLB as production input.

## Inputs

- fresh all-static XModel extraction manifest: `NUKETOWN_ALL_STATIC_XMODEL_EXTRACTION_MANIFEST_V3.json`
- retained retail LOD0 material proof: `T6_NUKETOWN_PLAYABLE_STATIC_MATERIAL_PROOF_V1.json`
- both independently bind to expanded retail FastFile SHA-256 `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`

The retained proof covers 297 playable static XModels / 538 LOD0 material slots with zero unresolved or generic placeholder slots.

## Exact alias propagation

The source manifest contains:

- 349 static XModels
- 901 packed block-5 material references
- 286 unique packed material targets

Applying the retained proof directly to the matching source XModel surfaces proves:

- 197 proof-covered packed slots
- 90 unique packed target identities
- 510 / 901 packed references globally, because the same exact target aliases are reused outside the original LOD0 proof rows

A second fail-closed stage uses the retail-proven T6 4-byte contiguous XModel material-handle-array contract. It admits neighbor slots only when at least two distinct already-proven packed targets in the same XModel independently imply one identical array base and each target material maps to a unique inline slot in that XModel.

Eight XModels satisfy that strict multi-anchor rule. It adds exactly three new unique referenced aliases:

- block 5 / `0x0066e364` (`6742884`) -> `mc/nt_2020_plastic_yellow`
- block 5 / `0x00f267bc` (`15884476`) -> `mlv/metal_stainless_steel_groves_editor`
- block 5 / `0x01bd430c` (`29180692`) -> `mc/mtl_p_jun_bench_wood_weathered01`

Final exact closure at this checkpoint:

- **93 / 286 unique packed targets resolved**
- **516 / 901 packed references resolved**
- **193 unique packed targets remain unresolved**
- **385 packed references remain unresolved**
- alias conflicts: **0**

## Artifacts

- resolver: `tools/t6_nuketown_static_material_alias_resolve_v1.py`
- compressed full manifest: `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_STATIC_MATERIAL_ALIAS_CLOSURE_V1.json.zlib.b64`
- decoded manifest bytes: 120,876
- decoded manifest SHA-256: `4af344ef94a5b00acc643c828c3fa02a82d05373fb03bc54406954f653f6817f`

## Proof boundary

No one-anchor inference is promoted. No filename/material-name similarity, geometry similarity, old GLB assignment, render appearance, or ordering-only guess is used to assign a packed alias.

Next work is to source-close the remaining 193 packed targets, preferentially through exact VIRTUAL destination-cursor/handle-slot reconstruction from the now-materialized retail expanded FastFile and reusable geometry anchors, before rebinding static textures into the fresh full scene.
