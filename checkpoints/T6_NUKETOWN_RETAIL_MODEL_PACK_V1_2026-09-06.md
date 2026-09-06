# T6 Nuketown retail model pack v1 — 2026-09-06

The first standalone source-derived Nuketown XModel deliverable pack is now generated directly from the exact retail FastFile.

## Result

- models exported: **3 / 3**
- exact expanded FastFile SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`
- output: self-contained **LOD0 GLB + glTF + normalized mesh/skeleton provenance sidecars** for every model
- source/identity/walker/export/GLB validation failures: **0**

### `mlv/nt_tree_ficus_lrg_01_sway`

- XAsset: **246**; fixed source start: **24530208**
- bones: **1**; LOD0 surfaces: **3**
- LOD0 vertices / triangles: **1,959 / 1,535**
- GLB bytes: **157,596**
- GLB SHA-256: `f96975eebd76a24b50f6ceccdcac4b4726989f833f92b2b9db0a322360236917`

### `mlv/nt_2020_vista_ufo_01`

- XAsset: **255**; fixed source start: **25254741**
- bones: **1**; LOD0 surfaces: **1**
- LOD0 vertices / triangles: **369 / 400**
- GLB bytes: **33,096**
- GLB SHA-256: `acf27d5a2acdbd8875932de1734055908d5ac1939340e0ff9e2bb977480f047f`

### `mp_nuketown_2020_vista_bldg_03`

- XAsset: **257**; fixed source start: **25309099**
- bones: **1**; LOD0 surfaces: **1**
- LOD0 vertices / triangles: **36 / 18**
- GLB bytes: **6,816**
- GLB SHA-256: `14eeefe9539bc19b23ddffb5153611d4e1c7c54f5655ee007679b63c82f17912`

## Proof boundary

Exact retail FastFile -> exact expanded stream -> exact top-level XAsset identity/source offset -> blocker-free serialized XModel walk -> source-owned mesh normalization -> reusable-owner-aware skeleton normalization -> validated bind-pose glTF -> container-only GLB conversion. No old GLB geometry, inferred model identity, guessed weights, or substitute assets are accepted.

Materials are intentionally **not** attached in v1. Geometry and skeletons are exact; the next material pass will only consume already source-closed Material/Image identities rather than infer them from appearance or surface order.

The two parked-car XModels remain the next model-format extension because their exact names are packed VIRTUAL references. Their identities are already closed; the mesh normalizer will be extended to accept that proof without mutating or guessing retail bytes.

- manifest bytes: **5,697**
- manifest SHA-256: `c643da28a34a6b841fc5c52d419e98afe948c9e593890d288eb34f6d66313fb2`
