# T6 Every-Map Export Progress — Nullable Lightmaps / Production v5 — 2026-09-01

This checkpoint records two independent advances toward a universal Black Ops II / T6 map exporter:

1. formula-independent retail validation of the known Nuketown `vd1` layouts; and
2. correction of the production lightmap pipeline after retained retail Nuketown bytes proved that `GfxLightmapArray.primary` may be null while `secondary` is present.

The goal remains a fail-visible, deterministic exporter that can ingest every retail T6 map without inventing geometry, image dependencies, shader semantics, or fallback assets.

## Current completion estimate

These percentages are engineering estimates, not a mathematical coverage score.

| Area | Current estimate | Proof boundary |
|---|---:|---|
| Fast-file / asset extraction and identity | ~95% | broad retail extraction is working; preservation is not the same as semantic reconstruction |
| Static world geometry + placement reconstruction | ~90–92% | Nuketown is strongly byte-proven; remaining universal risk is uncommon world vertex formats |
| Static / rigid / skinned XModel reconstruction | ~93% | rigid + animated rigid paths are proven; blended model path is substantially decoded |
| XAnim / skeleton / inverse-bind reconstruction | ~93–95% | retail animated model proofs exist; broader clip/model-family coverage remains |
| Material / texture dependency preservation | ~85% | exact dependency identities and DDS portability are strong; special shader semantics remain |
| Lightmap structure / identity / archival | ~85% | surface indexing, sampler identities, OAT names, raw DDS archive, and nullable roles are represented |
| Lightmap pixel-channel + combine equation | ~45% | exact retail shader bytes / representative pixel semantics are still required |
| Universal world-vertex compatibility | ~86% overall path | formats 0/1/2/3/6 retail-proven; 4/5/7/8 still need direct retail byte fixtures |
| Automatic retail-looking Blender/GLB scene | ~72% | geometry and dependency transport are ahead of special materials, lightmaps, FX, decals, and dynamics |
| Perfect archival gameplay/renderer recreation | ~60% | gameplay systems, runtime FX, shader families, probes/lighting behavior and special cases remain |

**Practical headline:** approximately **86% of the core work needed to properly export every T6 map** is now in place. A fully automatic scene that visually reproduces the retail renderer is lower, approximately **72%**, because renderer semantics and special effects lag behind geometry/asset reconstruction.

## Retail `vd1` progress

The retained `T6_NUKETOWN_WORLD_VERTEX_PROOF_V1.json` is 873,158 bytes with SHA-256:

```text
2e0a72303593a082ea0468a6ffd6b18e9d5bd9aa16c2a0b7337a2e7a95fe505d
```

It records:

```text
map                    mp_nuketown_2020
surfaces                5,614
unique vertex groups      340
vd0 bytes           5,285,088
vd1 bytes              33,764
observed formats       0, 1, 2, 3, 6
```

The formula-independent extent pass derives secondary-stream stride from serialized `vertexDataOffset1` differences plus independently established vertex counts before consulting the semantic format table.

Unambiguous retail allocations independently confirm:

```text
format 1  TEX_2_NRM_1   4 bytes/vertex
format 2  TEX_2_NRM_2   8 bytes/vertex
format 3  TEX_3_NRM_1   8 bytes/vertex
format 6  TEX_4_NRM_1  12 bytes/vertex
```

No contradiction was observed for those formats.

Format 0 does not behave as an ordinary `vd1` owner on Nuketown. Many format-0 groups either point to the end of the stream or share an active offset with a nonzero format. Therefore bare `vertexDataOffset1` equality is not ownership proof.

Permanent commits:

| Commit | Artifact |
|---|---|
| `c81082c` | raw `vd1` allocation census v1 |
| `ad48cd4` | hardened census: ambiguous/shared offsets cannot promote a format |
| `b4fa6b9` | regression with deliberately contradictory raw allocation |
| `fb73e3c` | formula-independent Nuketown retail extent proof |

### Still unproven

Direct retail fixtures are still needed for:

```text
4  TEX_3_NRM_2
5  TEX_3_NRM_3
7  TEX_4_NRM_2
8  TEX_4_NRM_3
```

The current semantic table predicts `vd1` strides 12/16/16/20 bytes respectively, but those values remain hypotheses until a retail map actually contains those formats and the raw extent census confirms them.

Format 8 is especially important because independent T6 work has reported surveyed secondary-stream element strides up to 16 bytes. That does not disprove a 20-byte format-8 allocation; it does make direct retail proof mandatory.

## Retail nullable-lightmap discovery

Retained proof:

```text
T6_NUKETOWN_GFXWORLD_DRAW_PROOF_V1.json
bytes     3,508
SHA-256  f20dfd43e1caff1df564fe10a25dc2fdc4e9598cb63a7f80924d3260f1a951d7
```

Nuketown GfxWorld:

```text
GfxWorld asset index     624
surfaceCount           5,614
lightmapCount              2
vertexCount          146,764
vertexDataSize0     5,285,088
vertexDataSize1        33,764
indexCount            300,840
```

The serialized lightmap array is exactly:

```text
00000000ffffffff00000000ffffffff
```

Decoded as:

```text
entry 0
  primaryPointer   0x00000000  null
  secondaryPointer 0xffffffff  following
  secondary image  *lightmap0_secondary
  512 x 3072
  resourceSize     6,291,456

entry 1
  primaryPointer   0x00000000  null
  secondaryPointer 0xffffffff  following
  secondary image  *lightmap1_secondary
  512 x 1536
  resourceSize     3,145,728
```

The retained proof also validates:

```text
lightmap images end exactly at vd0
vd0 immediately followed by vd1
vd1 immediately followed by indices
```

Therefore there is no evidence for a skipped inline primary image between the lightmap image region and the vertex buffers.

Permanent retail proof:

| Commit | Artifact |
|---|---|
| `437e001` | `manifests/maps/mp_nuketown_2020/lightmap_role_presence_proof_v1.json` |

## Why production v4 was wrong

The previous lightmap manifest/archive path required both primary and secondary image identities.

That assumption meant a truthful Nuketown catalog with:

```text
primaryImage = null
secondaryImage = "*lightmap0_secondary"
```

would fail as an empty primary asset, even though those are the actual retail semantics.

The correct response is not:

```text
primary = white
primary = black
primary = secondary
primary = synthetic placeholder
```

All of those invent data.

The correct representation is:

```text
primaryPresent = false
primaryImage = null
primarySourceTexture = null

secondaryPresent = true
secondaryImage = exact retail GfxImage identity
secondarySourceTexture = exact OAT filename
```

The global renderer sampler contract still exists:

```text
0x4  lightmapSamplerPrimary
0x5  lightmapSamplerSecondary
```

An absent image role simply means that particular `GfxLightmapArray` entry has no GfxImage dependency for the role.

## Nullable lightmap manifest v3

Commit:

```text
ca05c11  tools/t6_world_lightmap_manifest_v3.py
```

Properties:

- exact `GfxSurface.lightmapIndex` join remains;
- primary and secondary presence are independent;
- absent role preserves null image/path/source fields;
- present role uses exact T6 GfxImage identity;
- present role uses exact OAT ImageDumper disk mapping;
- only present roles count as DDS dependencies;
- filename collisions remain fail-closed;
- sampler 4/5 identities remain present regardless of per-entry image presence;
- both-present, secondary-only, primary-only, and both-null entries are representable;
- no fallback image is created.

Regression:

```text
cd167fa  tools/test_t6_world_lightmap_manifest_v3.py
```

The nullable manifest regression was executed in a local dependency-compatible harness and passed. This is local algorithm validation, not a full repository CI result.

## Nullable lightmap GLB archive v3

Commit:

```text
bd77296  tools/t6_world_lightmap_glb_embed_v3.py
```

Properties:

- consumes `t6-world-lightmap-manifest-v3`;
- archives exact DDS bytes only for present roles;
- absent roles remain explicit archive entries with `present=false`;
- absent roles never enter missing-file accounting;
- unique present GfxImage identities retain exact SHA-256 / byte count / bufferView provenance;
- present identity <-> disk source remains bijective;
- raw DDS storage remains renderer-neutral;
- no core glTF material/lightmap binding is invented;
- no shader equation is guessed.

Regression:

```text
0631997  tools/test_t6_world_lightmap_glb_embed_v3.py
```

The regression exercises:

```text
both present
secondary only
primary only
both null
all present DDS files available
one present DDS missing with fail-closed behavior
one present DDS missing with allow-missing accounting
attempt to attach an invented identity to an absent role
deterministic repeated embedding
```

The nullable archive regression was executed in a local dependency-compatible harness and passed. This is local algorithm validation, not a full repository CI result.

## Production world exporter v5

Commit:

```text
d0da1d2  tools/t6_oat_world_textured_export_pipeline_v5.py
```

v5 keeps the already-audited v4 world/material/DDS orchestration and promotes only the lightmap stages:

```text
world/material pipeline v4
  -> lightmap manifest v3
  -> lightmap archive v3
  -> final portable textured v5 GLB/glTF
```

Final names:

```text
<map>.world_lightmap_manifest_v3.json
<map>.world_oat_portable_textured_v5.glb
<map>.world_oat_portable_textured_v5.gltf
<map>.world_oat_textured_export_manifest_v5.json
```

The temporary v4 lightmap functions are restored in a `finally` block, including failure cases. The stale staging-level v4 top-level manifest is removed after promotion.

Regression:

```text
c4a0a6b  tools/test_t6_oat_world_textured_export_pipeline_v5.py
```

The promotion regression was executed locally and passed for:

```text
lightmap-enabled export
no-lightmap export
GLB + glTF naming promotion
v3 manifest naming
v5 top-level manifest
nullable role statistics
successful restoration of v4 globals
restoration after injected failure
```

Again, this is local algorithm validation, not a repository CI/status claim.

## Shader/lightmap semantic boundary

The structural lightmap path is now substantially stronger, but the following remain deliberately separate:

```text
primary channel meanings
secondary channel meanings
which channels representative retail shaders consume
exact arithmetic/combine equation
variation across technique families
special materials that repurpose/bypass ordinary world lightmaps
```

The shader research path now includes exact DXBC/RDEF/register/disassembly/lineage tooling, but a retained retail T6 lightmap shader fixture is still required to promote the semantic result beyond hypothesis.

## Highest-value next work

1. Scan additional retail MP maps for formats 4/5/7/8 using the formula-independent raw `vd1` census.
2. Promote each observed format only after raw allocation extent agrees with a unique stride.
3. Run the new production v5 path against the retained/local Nuketown catalog + exact secondary DDS assets and retain the resulting v5 manifest hashes.
4. Acquire representative retail lightmap shader `.cso` bytes and feed them through the v2 shader research chain.
5. Reconstruct special material families: cutout/alpha, glass, emissive, scrolling, decals, detail normals, environment/reflection behavior.
6. Continue dynamic/animated world entity, FX, GameWorld, MapEnts and AddonMapEnts reconstruction.
7. Expand the all-retail-map regression census from MP into Zombies once MP world-format coverage is closed.

## Current universal-map blocker statement

The production pipeline no longer requires a false primary+secondary image pair. The remaining highest-risk geometry compatibility blocker is now cleanly isolated to **world vertex formats 4, 5, 7 and 8**.

A map containing only currently retail-proven formats 0/1/2/3/6 can proceed through the known world-layout path without that particular compatibility uncertainty. A map containing 4/5/7/8 must remain fail-visible until a retail fixture proves its raw secondary-stream allocation.

That is the next boundary to close.
