# T6 GfxWorld Reflection-Probe Catalog Dumper Patch

This patch archives the exact structural reflection-probe payload already loaded by OpenAssetTools for a T6 `GfxWorld`. It is intentionally a **resource/ownership dumper**, not a renderer and not a PBR conversion.

Output schema:

```text
t6-gfxworld-reflection-probe-catalog-v1
```

Typical output:

```text
gfxworld_reflection_probes/<gfxworld asset name>.json
```

For every dense `GfxWorld.draw.reflectionProbes[i]` entry it preserves:

```text
index
origin[3]
lightingSH.V0[4]
lightingSH.V1[4]
lightingSH.V2[4]
reflectionImage->name      (nullable)
probeVolumeCount
probeVolumes[j].volumePlanes[6][4]
mipLodBias
```

Runtime `GfxWorld.draw.reflectionProbeTextures` values are deliberately **not** serialized. They are runtime graphics-resource pointers, not stable archival identities. The exact `reflectionImage` `GfxImage::name` is the portable asset identity.

## Pinned upstream structure

Prepared against OpenAssetTools commit:

```text
7d027e8f89118196713e955b0e11f8404149c54d
```

The pinned T6 declarations establish:

```cpp
struct GfxReflectionProbeVolumeData
{
    vec4_t volumePlanes[6];
};

struct GfxReflectionProbe
{
    vec3_t origin;
    GfxLightingSH lightingSH;
    GfxImage* reflectionImage;
    GfxReflectionProbeVolumeData* probeVolumes;
    unsigned int probeVolumeCount;
    float mipLodBias;
};

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

So the archival path is explicitly:

```text
GfxWorld.draw.reflectionProbeCount
GfxWorld.draw.reflectionProbes[i]
```

No nearest-probe search or inferred spatial assignment is required: normalized world surfaces already preserve their retail `reflectionProbeIndex` and `tools/t6_world_reflection_probe_manifest_v1.py`/later consumers join by that exact index.

## Install

Copy:

```text
GfxWorldReflectionProbeDumperT6.h
GfxWorldReflectionProbeDumperT6.cpp
```

into:

```text
src/ObjWriting/Game/T6/GfxWorldReflectionProbe/
```

The pinned OAT `src/ObjWriting.lua` already includes `ObjWriting/**.h` and `ObjWriting/**.cpp`.

If using both the lightmap and reflection-probe catalog dumpers, copy the lightmap patch files too and apply:

```text
ObjWriterT6.registration.combined.patch
```

The combined patch registers two independent `IAssetDumper` instances for `AssetGfxWorld`. This is supported by the pinned `IObjWriter`: `RegisterAssetDumper` simply appends accepted dumpers to `m_asset_dumpers`, and `DumpZone` executes every registered dumper. Keeping the two outputs separate preserves their independent proof schemas.

## Fail-closed behavior

The reflection-probe dumper refuses output when:

- the `GfxWorld` pointer is null;
- `draw.reflectionProbeCount > 0` but `draw.reflectionProbes` is null;
- origin, SH coefficients, volume planes, or `mipLodBias` contain non-finite values;
- a non-null `reflectionImage` has no `GfxImage::name`;
- `probeVolumeCount > 0` but `probeVolumes` is null.

A **null `reflectionImage` pointer is preserved as JSON `null`** rather than replaced with a guessed cubemap.

Float output uses `std::numeric_limits<float>::max_digits10`, so finite source floats are serialized with enough decimal precision for round-trip recovery of their float32 value.

## Separation from shader reversal

This catalog does not infer what the probe pixels mean. Shader behavior remains in the separately retained/reconstructed contracts, particularly:

```text
tools/t6_reflection_probe_semantics_v1.py
```

That module already preserves the universal 5,888-fetch coordinate/decode/mip behavior and the exact dominant 4,236-fetch shared-parameter family while leaving the closure-ledger residual families explicit.

The intended pipeline is therefore:

```text
GfxSurface.reflectionProbeIndex
  -> GfxWorld.draw.reflectionProbes[index]
  -> exact reflectionImage GfxImage identity
  -> exact archived image/cubemap payload
  -> source-closed reflection shader family
```

rather than:

```text
surface -> guessed nearest environment -> generic Principled roughness
```

## Promotion boundary

Source committed here is **not automatically retail proof**. Promotion requires:

1. Build the patch against the pinned OAT revision.
2. Run Unlinker against retained retail T6 worlds.
3. Archive the generated catalog unchanged with source-zone and output hashes.
4. Validate dense indices, surface references, nullable image roles, volume counts, and image identities with the Python manifest layer.
5. Stage/archive exact reflection-image payloads without discarding cubemap faces or mip chains.
6. Only then promote probe-resource ownership to retained retail P4/P6 for that map.
