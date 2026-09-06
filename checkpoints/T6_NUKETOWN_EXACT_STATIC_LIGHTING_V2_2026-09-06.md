# T6 Nuketown exact static-lighting integration v2 — 2026-09-06

This checkpoint closes the retail PC coefficient-decode path for Nuketown and wires it into the **fresh source-derived 2,992-static reconstruction**. It does not lower or replace the v25/v31 full-map visual floor.

## Retail PC renderer closure

The exact PC server binary `CoDMPServer_PC.exe` and symbols establish:

- `R_CalculateLightGridColorFromCoeffs` — `0x00A6EE90`
- `R_DecodeLightGridCoeffsWeighted` — `0x00A6EF30`
- `R_BlendAndSetLightGridColors` — `0x00A6FD40`
- `GenerateLightGridBasisDirs` — `0x00A98020`

The 9×RGB `uint16` coefficient decode is source-closed as float32 operations:

```text
v = uint16
v *= float32(1 / 65535)   # 0x37800080, VA 0x00D23240
v *= 32.0                 # 0x42000000, VA 0x00D23250
v += -16.0                # 0xC1800000, VA 0x00D23260
v *= weight
```

The renderer then evaluates each 9-vector record at the exact 56 normalized cube-shell directions produced by `GenerateLightGridBasisDirs`:

```text
max(
  c0 + x*c1 + y*c2 + z*c3
  + z*x*c4 + z*y*c5 + y*x*c6
  + (3*z*z - 1)*c7
  + (x*x - y*y)*c8,
  0
)
```

The regenerated 56-direction float32 table hashes to:

```text
9dd96f562853c9286e37d31cd4c328a9bb955159d9e704e640a8164463f23d32
```

## Exact GfxLightingSH packing

For decoded coefficient vector `ci`, define in PC scalar instruction order:

```text
L(ci) = 0.25*ci.r + 0.5*ci.g + 0.25*ci.b
D = L(c0) + float32(0.0001)
```

with epsilon bits `0x38D1B717`.

The packed T6 `GfxLightingSH` is:

```text
V0 = [ c0.r/D, c0.g/D, c0.b/D, 3*L(c7) ]
V1 = [ L(c1), L(c2), L(c3), D-L(c7) ]
V2 = [ L(c4), L(c5), L(c6), L(c8) ]
```

This is now implemented without a guessed Blender/PBR lighting conversion.

## Retail Nuketown coefficient bank

Canonical expanded stream:

- bytes: **154,653,476**
- SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`

Coefficient bank:

- start: **82,258,056**
- end: **84,451,266**
- records: **40,615**
- bytes/record: **54**
- bytes: **2,193,210**
- SHA-256: `cb78afcf9fd6abd008b2beeb56eedc355885bd681b384f92b261152c8eebb1e5`

All 40,615 records decode to finite float32 coefficients. Observed decoded coefficient range:

```text
-6.655618667602539 .. 8.81385612487793
```

## Static lighting reconstruction

`tools/t6_nuketown_lightgrid_coeff_decode_v1.py` joins the exact coefficient bank to all **2,992 / 2,992** source-derived `GfxStaticModelDrawInst` placements by `colorsIndex`.

Validation:

- static placements: **2,992**
- unique static coefficient indices: **2,992**
- colorsIndex range: **2 .. 6,784**
- all packed `GfxLightingSH` values finite
- exact directional decode checked at 56 directions for every static
- directional RGB lanes checked: **502,656**
- negative post-clamp lanes: **0**
- zero post-clamp lanes: **987**
- directional maxima: `[19.9177570343, 19.5775070190, 19.0428180695]`
- primary-light-1 statics: **2,222 / 2,992**

The generated full static-lighting JSON is deterministic:

- uncompressed bytes: **1,668,665**
- SHA-256: `99c6aa39f00e216b037f22019d3e11fc7d008f7a3af9ee965b71d25eb7fc0de7`
- zlib bytes: **520,580**
- zlib SHA-256: `16295fa5898fbef24808177f48b1cd7f5edfe3a5b2fc47755d4bc483816014d1`
- zlib+base64 bytes: **694,109**
- SHA-256: `959eaa5b4bb177a09485580afcafe02fcbf418b2679a7fc73ce0f076b12781c4`

The deterministic math regression `tools/test_t6_nuketown_lightgrid_coeff_decode_v1.py` passes, including exact float32 bit patterns for coefficient decode, basis generation, SH packing and directional evaluation.

## Fresh static scene v2

The source-derived static model index is now reproducible with:

`tools/t6_nuketown_static_model_index_v1.py`

For the retained 349 source-derived static XModel exports it produces:

- bytes: **227,901**
- SHA-256: `9b7e3043c9b92332a5fec6c6417a261a482c998c023388841e3dc5f837c50eb4`

`tools/t6_nuketown_static_scene_rebuild_v2.py` then joins the exact lighting record into every fresh static placement node while retaining the source-derived XModel geometry and exact placement transform.

Generated diagnostic GLB:

- `mp_nuketown_2020_FRESH_RETAIL_STATICS_LIGHTING_v2.glb`
- bytes: **24,845,256**
- SHA-256: `55ddda4ab453c96f3aba7220b0dd7ccdc39f4a77cf98595f7837bbc6a9066ade`
- meshes: **349**
- placement nodes: **2,992**
- nodes carrying exact retail `GfxLightingSH`: **2,992**
- primitive definitions: **605**
- LOD0 triangle definitions: **351,232**
- unique static coefficient indices retained: **2,992**
- all 349 LOD0 source GLB hashes matched
- all 2,992 placement XAssets resolved
- all 2,992 lighting joins matched `colorsIndex`, `primaryLightIndex`, and `visibility`
- GLB 2.0 reparsed successfully
- `trimesh.load(..., process=False)` passed

No retained combined/full-map GLB was used as geometry input.

## Promotion boundary

`mp_nuketown_2020_FRESH_RETAIL_STATICS_LIGHTING_v2.glb` is **diagnostic/source-layer output, not a visual successor**.

The next user-facing full-map candidate still must merge this exact static-lighting layer forward with:

1. the fresh 5,614-surface GfxWorld;
2. exact static/world materials and recovered texture payloads;
3. exact lightmaps / reflection data / retail skybox;
4. six MapEnt cars plus animation/support scenes;
5. v31-and-later generated-material shader contracts;
6. the v25 scene-policy release floor with **zero failures**.

No partial build is promoted merely because this lighting branch is now closed.
