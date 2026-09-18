# T6 Nuketown production texture union handoff — 2026-09-17

## Purpose

This checkpoint records the exact state of the Nuketown production-image closure after recovering the previously opaque GfxWorld Actions failure and wiring a durable handoff into the production texture census.

The proof standard remains fail-closed. No filename similarity, dimensions, adjacency, material order, validator expectation, renderer appearance, or inferred image role is promoted as retail ownership.

## Existing authoritative Material floor

The current production Material graph remains:

- required Material identities: **327**
- exact Material texture dependency occurrences: **973**
- unique Material GfxImage identities: **423**
- exact 81-image DDS bridge overlap with Material graph: **75**
- Material-only exact DDS coverage floor: **75 / 423 = 17.7304964539%**

These counts are not the final Nuketown production denominator. The final denominator is the exact identity-deduplicated union:

```text
Material GfxImages
UNION GfxWorld lightmap GfxImages
UNION GfxWorld reflection-probe GfxImages
```

Category counts must never be added without identity-level deduplication.

## Exact recovery of failed GfxWorld run

Historical workflow run:

- run: `34490172182`
- job: `102914543950`
- workflow: `.github/workflows/t6_nuketown_gfxworld_light_reflection_catalog_v2.yml`
- pinned OpenAssetTools: `7d027e8f89118196713e955b0e11f8404149c54d`

The full job log was recovered on 2026-09-17.

The two custom T6 ownership dumpers compiled successfully in that build:

- `GfxWorldLightmapDumperT6.cpp`
- `GfxWorldReflectionProbeDumperT6.cpp`

The build then failed in unrelated upstream host-portability code before any retail FastFile dump ran:

1. `src/ObjWriting/Game/IW3/Menu/MenuWriterIW3.cpp`
   - GCC reports `std::format` is not a member of `std`.
2. `src/ObjLoading/Game/T5/XModel/XModelHighMipVolumeT5.cpp`
   - GCC reports `std::sqrtf` is not a member of `std` and suggests `std::sqrt`.

The later upload-artifact failure was secondary: the build stopped before the old workflow created proof output files.

This is therefore a host-build portability failure, not evidence against T6 GfxWorld ownership, lightmap count, reflection-probe count, or image identity.

## Exact pinned-source compatibility closure

The pinned OAT source at `7d027e8...` was inspected directly.

Exact required portability edits for that revision are bounded to five source edits:

- add `<format>` to the IW3 menu writer;
- add `<format>` to the IW4 menu writer;
- add `<format>` to the IW5 menu writer;
- add `<limits>` to `FlatXAnimDataWriter.cpp`;
- replace the single exact T5 expression `std::sqrtf(v6)` with `std::sqrt(v6)`.

The different OAT `9dca965...` compatibility helper was not reused blindly because `7d027e8...` does not contain the T4 menu writer expected by that helper.

New fail-closed helper:

- `tools/t6_oat_7d027_gcc_compat_patch_v1.py`
- commit `d09406a6c513298844a99456646ce240c3f87246`

The helper verifies the exact OAT HEAD before editing and does not modify T6 loader, ZoneCode, FastFile, GfxWorld, Material, TechniqueSet, shader, pointer, or stream semantics.

## GfxWorld workflow repair

Commit:

- `9dd4a04e64a8e02c3f05df40a916e9cadf7e14af` — unblock exact Nuketown GfxWorld ownership build

The v2 workflow now:

- applies the exact `7d027e8...` compatibility helper;
- runs `git diff --check`;
- archives the exact compatibility diff;
- captures the OAT build log under `/tmp/proof/oat_build.log` even if another compiler failure occurs;
- hashes the ownership dumpers and compatibility helper.

Commit:

- `08f5ece665c315cabd5a0b9c3c1f967e03892dd4` — persist exact GfxWorld image ownership catalogs

After the retail FastFiles are SHA-256 verified, the patched OAT dump succeeds, and both catalogs pass fail-closed validation, the workflow persists:

- `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_GFXWORLD_LIGHTMAP_CATALOG_V2.json`
- `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_GFXWORLD_REFLECTION_PROBE_CATALOG_V2.json`
- `checkpoints/T6_NUKETOWN_GFXWORLD_PRODUCTION_IMAGE_OWNERSHIP_V2.md`

No catalog is committed if the build, retail dump, or validation fails.

## Production census handoff

Commit:

- `438508816933025d8ca14b816563cefa262c8a75` — join exact GfxWorld images into production texture census

The existing production census workflow already independently rebuilds:

- the exact 327-Material dependency graph;
- the exact 81-image lossless DDS bridge.

It now also watches the two persisted GfxWorld catalog paths.

Behavior is fail-closed:

- if neither GfxWorld catalog exists, it emits the existing Material-only census;
- if either one exists, **both must exist**;
- when both exist, census v2 receives both exact catalogs and emits `T6_NUKETOWN_PRODUCTION_TEXTURE_DEPENDENCY_CENSUS_FULL_V2.json`;
- the production denominator is computed by Python set union over exact GfxImage identities, so cross-category overlap is deduplicated automatically.

The full census retains the exact Material invariants:

- `materialUniqueImageCount == 423`
- `materialCoveredByExact81Count == 75`
- `exact81BridgeImageCount == 81`

## Current proof boundary

As of this checkpoint, the repaired workflow has been committed but a new successful retail GfxWorld catalog artifact has **not yet been promoted here**.

Therefore:

- **423** remains the proven Material-only denominator;
- **75 / 423 = 17.73%** remains the proven exact DDS coverage floor;
- the test/workflow expectation of two lightmap records is **not** a production fact until the SHA-verified retail dump succeeds;
- historical workflow code that intended to persist ownership catalogs is not treated as surviving proof because those generated catalog files are absent from current `main`.

## Next exact gate

Follow the newest v2 GfxWorld workflow execution caused by the repair commits.

If build fails:
1. recover the exact new compiler line from `oat_build.log`;
2. bound any additional compatibility edit to the exact pinned source;
3. do not touch T6 semantics to solve a host-build issue.

If build and retail dump pass:
1. verify the persisted catalog hashes and identities;
2. follow the automatically triggered production census;
3. promote the first exact full production denominator and exact-81 coverage only from the resulting identity-deduplicated full census;
4. then move to the remaining sampler/TechniqueSet ownership boundaries without conflating them with texture payload coverage.
