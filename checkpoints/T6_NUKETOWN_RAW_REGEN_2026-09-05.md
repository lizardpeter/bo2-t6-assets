# T6 Nuketown raw-source regeneration checkpoint — 2026-09-05

This checkpoint records the first fresh Nuketown GfxWorld regeneration performed in the current execution environment directly from the connected Google Drive retail source package. No prior GLB was used as geometry input.

## Retail inputs materialized from Drive

- `mp_nuketown_2020.ff`
  - bytes: `38,472,064`
  - SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- `mp_nuketown_2020.ipak`
  - bytes: `165,543,936`
- `common_mp.ff`
  - bytes: `40,307,072`
  - SHA-256: `93fe48b0f0d8cc6844be875ccad94e0cfcf635f62eeff00ac33f2f668a77cb77`
- `common_patch_mp.ff`
  - bytes: `907,392`
  - SHA-256: `95622d93d4fb761db311a123cd073bed34ea48c9c711d2c11bce4170dd08bae9`
- `patch_mp.ff`
  - bytes: `3,638,592`
  - SHA-256: `459077cda8e4a1457f7ee7d8f6c5e0abf30f41767a21ff6744df6a4307cbce1e`
- `en_mp_nuketown_2020.ff`
  - bytes: `832`

The Drive package intentionally does not contain the large shared `base.ipak`, `mp.ipak`, `so.ipak`, or `en_base.ipak` containers.

## Exact T6 FastFile expansion reproduced live

`tools/t6_fastfile_expand_pc_v1.c` was derived from the pinned OpenAssetTools T6 loader behavior and executed locally.

Fresh Nuketown expansion result:

- record count: **4,730**
- stream counts: **1183 / 1183 / 1182 / 1182**
- expanded bytes: **154,653,476**
- expanded SHA-256: **`7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`**

This matches the repository-pinned canonical expanded identity exactly.

## Fresh live GfxWorld recovery

GfxWorld fixed start: `63,150,420` (XAsset index 624).

Directly recovered values:

- surfaces: **5,614**
- lightmaps: **2**
- vertices: **146,764**
- vd0 bytes: **5,285,088**
- vd1 bytes: **33,764**
- indices: **300,840 uint16 values**
- world material-memory entries: **327**

Exact child ranges recovered from the expanded stream:

- vd0: `[76,182,996, 81,468,084)`
  - SHA-256 `7a5be06b14564a2dafd065d77204ff808e7cbbaac1ab0f06f1c6ef3f3e29ca76`
- vd1: `[81,468,084, 81,501,848)`
  - SHA-256 `77018ac13744f39244f29ce2c4cce0f0eb1204071a679654bd4eb67374537897`
- indices: `[81,501,848, 82,103,528)`
  - SHA-256 `70344c3cfbc8eb12a2e29b37deb55b5767a33b5b97beb3681215bf393c346fa7`
- GfxSurface array: start **85,007,995**, 5,614 × 80-byte records, end **85,457,115**

Surface/lightmap census:

- lightmap 0: 4,779 surfaces
- lightmap 1: 750 surfaces
- no-lightmap sentinel 31: 85 surfaces

## Fresh Material -> TechniqueSet -> worldVertFormat recovery

All **327 / 327** world Materials were recovered from their exact serialized records and rebound through the retail TechniqueSet XAsset pointers with zero failures.

Material format histogram:

- format 0: 207
- format 1: 95
- format 2: 7
- format 3: 17
- format 6: 1

Vertex groups reconstructed from vd0 allocation spans:

- total groups: **340**
- format 0 groups: 220
- format 1 groups: 95
- format 2 groups: 7
- format 3 groups: 17
- format 6 groups: 1
- mixed-format groups: **0**
- derived group vertices sum exactly to **146,764**
- local index validation failures: **0**

## Fresh GLB checkpoint

A new renderer-neutral GfxWorld GLB was generated directly from the fresh expanded retail stream:

`mp_nuketown_2020_FRESH_RETAIL_GFXWORLD_v1.glb`

- bytes: **16,933,132**
- SHA-256: **`106be76034e4f35f5c5728595290ec9db48b050493c3cb3b39dae5349dc2834d`**
- meshes/groups: **340**
- primitives: **5,614**
- materials: **327 exact retail identities**
- vertices: **146,764**
- triangles: **100,280**

Attribute/export contract:

- T6 Z-up inches -> glTF Y-up meters: `(x,y,z) -> (x,z,-y) * 0.0254`
- winding unchanged (orientation-preserving axis transform)
- `NORMAL` / `TANGENT` decoded using the source-close T6 third-based PackedUnitVec contract
- lightmap UV fixed to `TEXCOORD_1`
- secondary material UVs begin at `TEXCOORD_2`
- generated-material packed color controls exported as `_T6_LAYER_WEIGHTS`
- ordinary vertex color remains `COLOR_0`
- raw packed normal/tangent/lightmap UV preserved as `_T6_*` attributes
- normal-transform raw bytes preserved and a logical reordered accessor is also emitted

Independent validation:

- GLB 2.0 chunk/header/buffer reparse: **pass**
- `trimesh` load with `process=False`: **pass**
- `trimesh` geometry count: **5,614**
- `trimesh` node/geometry count: **5,614**

## Proof boundary / next work

This checkpoint proves raw retail FF -> exact expanded XFile -> exact GfxWorld geometry/material identity regeneration in the current environment. It is **not yet the visual successor** to the older textured/static Nuketown builds because map/static XModels and retail texture bindings have not yet been reassembled into this fresh file.

Immediate next stages:

1. recover map-IPAK material images directly from the mounted `mp_nuketown_2020.ipak` and bind them to this fresh world;
2. regenerate static XModel placements/models from the raw FF/shared zones instead of importing an old GLB;
3. feed the newer generated-material/lightmap/normal/replay contracts into the regenerated artifact;
4. keep shared `base.ipak` / `mp.ipak` requirements explicit until those large containers or exact targeted payloads are available.
