# T6 GfxWorld Lightmap Catalog Dumper Patch

This patch adds the smallest defensible T6 `GfxWorld` dumper needed by the current lightmap proof work.

It deliberately does **not** attempt to dump an entire `GfxWorld`, rebuild renderer state, or infer lightmap shader semantics. It emits only the source-closed relationship already present in the loaded T6 asset:

```text
GfxWorld.lightmapCount
GfxWorld.lightmaps[i].primary->name
GfxWorld.lightmaps[i].secondary->name
```

Output schema:

```text
t6-gfxworld-lightmap-catalog-v1
```

Typical output location from Unlinker:

```text
gfxworld_lightmaps/<gfxworld asset name>.json
```

## Pinned upstream reference

The patch was prepared against OpenAssetTools commit:

```text
7d027e8f89118196713e955b0e11f8404149c54d
```

At that revision, T6 declares `AssetGfxWorld`, the T6 structure contains `lightmapCount` / `lightmaps`, and `GfxLightmapArray` contains `primary` / `secondary` `GfxImage*` members. The stock T6 ObjWriter has its GfxWorld dumper registration commented out, so stock OAT does not currently emit this catalog.

## Install into an OpenAssetTools checkout

Copy:

```text
GfxWorldLightmapDumperT6.h
GfxWorldLightmapDumperT6.cpp
```

into:

```text
src/ObjWriting/Game/T6/GfxWorldLightmap/
```

OpenAssetTools' `src/ObjWriting.lua` already includes `ObjWriting/**.h` and `ObjWriting/**.cpp`, so no Premake source-file list change is required at the pinned revision.

Then edit:

```text
src/ObjWriting/Game/T6/ObjWriterT6.cpp
```

Add near the other T6 includes:

```cpp
#include "GfxWorldLightmap/GfxWorldLightmapDumperT6.h"
```

and replace the currently commented GfxWorld dumper placeholder:

```cpp
// REGISTER_DUMPER(AssetDumperGfxWorld, m_gfx_world)
```

with:

```cpp
RegisterAssetDumper(std::make_unique<gfx_world_lightmap::DumperT6>());
```

An exact reference diff is also retained in `ObjWriterT6.registration.patch`.

## Build / validation boundary

This repository stores the patch and exact upstream revision so it can always be reproduced. The patch is **not considered compiled/retail-proven merely because the source is committed here**.

Promotion path:

1. Apply to the pinned OAT checkout.
2. Regenerate/build OAT for the required Windows target.
3. Run Unlinker against a retained retail T6 map zone containing `GfxWorld`.
4. Preserve the generated catalog unchanged.
5. Validate it with `tools/t6_world_lightmap_manifest_v1.py` against that map's normalized world.
6. Commit a proof manifest with source zone hash, GfxWorld identity, lightmap count, primary/secondary names, surface-use counts, and output hash.
7. Only then promote the corresponding lightmap-catalog relationship to retail proof (P4) in `research/T6_REVERSE_ENGINEERING_LEDGER.md`.

## Fail-closed behavior

The dumper refuses to emit a catalog when:

- the GfxWorld pointer is null;
- `lightmapCount` is negative;
- a nonzero count has a null `lightmaps` array;
- any primary/secondary image pointer is null;
- any referenced image has no name.

It does not serialize raw process pointers because pointer values are not stable archival identities. Exact `GfxImage::name` identities are the portable join key used by the downstream material/image pipeline.

## What this does not solve

This patch does **not** establish:

- the pixel/channel meaning of primary vs. secondary;
- how the T6 shader combines the two;
- whether either image should be represented as sRGB or linear in a generic renderer;
- light-grid, reflection-probe, primary-light, shadow, or dynamic-light semantics.

Those remain separate proof boundaries. The catalog exists so those later steps can be solved without ever losing the exact retail image-pair identity.
