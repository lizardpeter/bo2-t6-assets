# T6 Nuketown parked-car model pack v1 — 2026-09-06

Both retail parked-car XModels now export as standalone source-derived LOD0 GLBs while preserving the already-proven packed-name identity chain.

## Result

- exact parked-car models exported: **2 / 2**
- packed-name identity failures: **0**
- mesh/skeleton/export/GLB validation failures: **0**

### `veh_t6_nuketown_2020_car01_clean`

- packed name: `0xA0016ABB` -> VIRTUAL **92858**
- bones / all-LOD surfaces: **25 / 20**
- LOD0 surfaces: **5**
- LOD0 vertices / triangles: **10,814 / 12,390**
- GLB bytes: **870,096**
- GLB SHA-256: `26a1034b54f625636c677a1f479dc6fe1055765388921ee4ca556bf357e07d06`

### `veh_t6_nuketown_2020_car02_whole`

- packed name: `0xA0016BAD` -> VIRTUAL **93100**
- bones / all-LOD surfaces: **24 / 30**
- LOD0 surfaces: **8**
- LOD0 vertices / triangles: **18,198 / 22,213**
- GLB bytes: **1,465,184**
- GLB SHA-256: `b385117d19a1423079c36667abd3b9c3fb8a94e7e73e810dc7f3238f01accb48`

## Normalizer extension

`tools/t6_xmodel_mesh_normalize_v2.py` preserves the v1 geometry decoder byte-for-byte and adds exactly one capability: when `XModel.name` is a packed block-5 pointer, it resolves identity only through the self-calibrated retail StringTable logical mapping and consumes zero source bytes for the packed name. Packed/reused surface payloads remain fail-closed.

## Material boundary

These GLBs intentionally contain exact geometry + skeleton only. Materials/textures will be attached in the next pass from source-closed Material/Image provenance rather than inferred visually.

- manifest bytes: **3,830**
- manifest SHA-256: `e0ef35ac0cacc2865d6ad257ef93e8a77a0c142f28c5b49950c7c428c0c2e782`
