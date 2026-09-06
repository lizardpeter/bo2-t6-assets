# T6 Nuketown fresh static-placement rebuild v1 — 2026-09-05

This checkpoint advances the raw-source Nuketown regeneration without lowering the v25/v31 visual floor.

## Result

A new static-placement archive GLB was regenerated from the retained raw-FF-derived static XModel exports and exact `GfxStaticModelDrawInst` placement manifest. The prior combined/full-map GLBs were **not** used as source input.

Generated diagnostic artifact:

- `mp_nuketown_2020_FRESH_RETAIL_STATICS_ARCHIVE_v1.glb`
- bytes: **23,320,616**
- SHA-256: **`7423d6c0697704d46f052f3ac3e2a8ee0eeaa491fcbcb78996efe5c7df83b320`**
- **349 / 349** static XModel definitions resolved
- **2,992 / 2,992** serialized static placements resolved
- **0** unresolved placement XAssets
- 349 mesh definitions
- 2,993 nodes including the archive root
- 605 LOD0 primitive definitions
- 351,232 LOD0 triangle definitions before placement instancing

This artifact is an internal diagnostic layer, not a user-facing visual successor. It intentionally preserves all 2,992 placements, including the 69 reflection-proxy placements and the two `fxanim_*` support placements. Those are filtered by scene role only after the layer is merged back into the full map.

## Exact source identity

All 349 source model GLBs are descendants of the exact expanded retail FastFile identity:

- expanded bytes: **154,653,476**
- SHA-256: **`7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`**

Retained source files used in the regeneration environment:

- `NUKETOWN_2025_ALL_STATIC_XMODELS_GLTF_V3.zip`
  - bytes: 13,745,687
  - SHA-256: `7caf8bddfa5ac8202a4a0918d51168f205871fecc1f0fa424ad53ea525684e27`
- `NUKETOWN_ALL_STATIC_XMODEL_EXTRACTION_MANIFEST_V3.json`
  - bytes: 4,030,192
  - SHA-256: `7a9ea51cd9b88f07b09e94ab8a754b35814e8dceb3b9563c6a4d6f3d7afde836`
- `NUKETOWN_STATIC_MODEL_PLACEMENTS_V1.json`
  - bytes: 6,565,598
  - SHA-256: `601c1e42733c17fce05d005a9f5468c18303a288fdcfc07c6fcd33b9d407bfc3`

The static extraction manifest proves all **349 static placement models** and all **2,992 placements** are resolved, including the five rigid-segmented multi-bone static models / ten placements.

## Placement-transform closure

The exact placement conversion is now explicit in repository code:

`tools/t6_nuketown_static_scene_rebuild_v1.py`

For each retail placement, with T6 basis rows `A`, the glTF rotation is:

`R_gltf = C * transpose(A) * inverse(C)`

where `C` implements `(x,y,z) -> (x,z,-y)`. Translation is `(x,z,-y) * 0.0254`, and retail uniform scale is applied to the basis.

All **2,992 / 2,992** regenerated matrices were compared against the retained v6 assembly and were exactly equal as serialized floating-point values; maximum absolute difference was **0**.

## Independent non-regression validation against retained v6

The retained v6 archive was used **only as a validation reference**, never as source geometry or placement input:

- reference: `mp_nuketown_2020_FULL_ALL_STATIC_ARCHIVE_v6.glb`
- bytes: 35,226,532
- SHA-256: `b48e59353bdf8140afd42627cd881104ded090e1cbcee2960de3b2d23f360c14`

For every one of the 349 LOD0 static meshes, every primitive was compared attribute-by-attribute against v6:

- `POSITION`
- `NORMAL`
- `TEXCOORD_0`
- `TANGENT`
- `COLOR_0`
- index buffer

Result: **0 failures**. All compared accessor payloads are byte-identical.

For every one of the 2,992 placement nodes:

- placement matrix: exact match
- XAsset identity: match
- mesh identity: match

Result: **0 failures**.

The fresh static GLB also reparsed successfully as GLB 2.0 and independently loaded through `trimesh` with `process=False`.

## Forward-only integration boundary

This closes the major static-geometry/placement branch needed to repair the regression. The next promoted Nuketown build still has to merge this source-derived static layer with:

1. the fresh 5,614-surface GfxWorld reconstruction;
2. exact world/static material and texture bindings;
3. lightmaps, reflection data and retail skybox;
4. six MapEnt cars and retained animation/support scenes;
5. v31-and-later generated-material shader contracts.

No user-facing successor may be promoted until `T6_NUKETOWN_V25_RELEASE_FLOOR_V1.json` passes with zero failures and the v31 shader-facing data is retained.
