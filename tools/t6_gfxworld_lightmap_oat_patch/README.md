# T6 GfxWorld Lightmap Catalog Dumper Patch

This patch adds the smallest defensible T6 `GfxWorld` dumper needed by the current lightmap proof work.

It deliberately does **not** attempt to dump an entire `GfxWorld`, rebuild renderer state, or infer lightmap shader semantics. It emits only the source-closed relationship already present in the loaded T6 asset:

```text
GfxWorld.draw.lightmapCount
GfxWorld.draw.lightmaps[i].primary->name   (nullable)
GfxWorld.draw.lightmaps[i].secondary->name (nullable)
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

The patch is prepared against OpenAssetTools commit:

```text
7d027e8f89118196713e955b0e11f8404149c54d
```

At that revision:

```cpp
struct GfxWorldDraw
{
    unsigned int reflectionProbeCount;
    GfxReflectionProbe* reflectionProbes;
    GfxTexture* reflectionProbeTextures;
    int lightmapCount;
    GfxLightmapArray* lightmaps;
    ...
};

struct GfxWorld
{
    ...
    GfxWorldDraw draw;
    ...
};
```

So the exact loaded lightmap path is **`world->draw.lightmapCount` / `world->draw.lightmaps`**. An earlier revision of this local patch incorrectly used `world->lightmapCount` and `world->lightmaps`; because the patch had never been compiled, that latent source-level error had not yet been caught. Commit `ad9ccf11...` corrects it against the pinned OAT structure.

`GfxLightmapArray` contains nullable `primary` / `secondary` `GfxImage*` members. Later retained-map work established that either role can actually be null, so the dumper now emits JSON `null` for a null retail pointer rather than rejecting or fabricating a fallback. A non-null `GfxImage*` with a null name still fails closed because it lacks a stable archival identity.

The stock T6 ObjWriter at the pinned revision has its GfxWorld dumper registration commented out, so stock OAT does not currently emit this catalog.

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

An exact reference diff is retained in `ObjWriterT6.registration.patch`.

## Build / validation boundary

This repository stores the patch and exact upstream revision so it can always be reproduced. The patch is **not considered compiled/retail-proven merely because the source is committed here**.

Promotion path:

1. Apply to the pinned OAT checkout.
2. Regenerate/build OAT for the required Windows target.
3. Run Unlinker against a retained retail T6 map zone containing `GfxWorld`.
4. Preserve the generated catalog unchanged.
5. Validate it with `tools/t6_world_lightmap_manifest_v3.py` against that map's normalized world.
6. Commit a proof manifest with source zone hash, GfxWorld identity, lightmap count, nullable primary/secondary identities, surface-use counts, and output hash.
7. Only then promote the corresponding lightmap-catalog relationship to retail proof in `research/T6_REVERSE_ENGINEERING_LEDGER.md`.

## Fail-closed behavior

The dumper refuses to emit a catalog when:

- the `GfxWorld` pointer is null;
- `draw.lightmapCount` is negative;
- a nonzero count has a null `draw.lightmaps` array;
- a **non-null** primary/secondary `GfxImage*` has no name.

A null primary/secondary pointer is preserved as JSON `null`; it is not an error and creates no inferred image dependency.

The dumper does not serialize raw process pointers because pointer values are not stable archival identities. Exact `GfxImage::name` identities are the portable join key used by the downstream material/image pipeline.

## What this does not solve

This patch does **not** establish:

- the pixel/channel meaning of primary vs. secondary beyond separately proven shader equations;
- whether either image should be represented as sRGB or linear in a generic renderer;
- light-grid, reflection-probe, primary-light, shadow, or dynamic-light semantics.

The exact directional-secondary-lightmap equation is handled separately by `tools/t6_directional_lightmap_semantics_v1.py`. Reflection probes are being cataloged independently so resource ownership and shader semantics remain separate proof boundaries.
