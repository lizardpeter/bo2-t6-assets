# T6 Reverse-Engineering Closure Ledger

**Project:** Call of Duty: Black Ops II / Treyarch T6  
**Purpose:** Permanent, conservative record of what is known, what is proven, what is merely supported synthetically, and what still blocks a faithful whole-game reconstruction.  
**Proof rules:** `research/T6_PROOF_STANDARD.md`  
**Last audited:** 2026-09-01

This is the canonical project-state ledger. A subsystem is not marked solved because one export looks plausible. Formula knowledge, synthetic regression, retained retail proof, cross-fixture proof, production integration, and independent validation remain separate milestones.

## Proof-state shorthand

- **P0** — unknown
- **P1** — structural hypothesis
- **P2** — source/formula known
- **P3** — deterministic synthetic regression proven
- **P4** — retained retail byte/asset proven
- **P5** — cross-fixture retail proven
- **P6** — normal export/archive pipeline integrated
- **P7** — independent consumer validated
- **P8** — T6-closed for the declared scope

---

# 1. Source containers, XAssets, and provenance

| Area | Current state | Remaining closure work |
|---|---|---|
| FF/IPAK/SABS/SABL/IWD preservation | Original containers are archival truth; preservation is distinct from decoding | Hash/provenance-link every base, patch, DLC, MP, Zombies, and SP source used by future proofs |
| Base/patch precedence | MP work preserves `base -> common patch -> patch`; duplicate identities are overrides, not additive assets | Generalize winning-source provenance to every XAsset type and zone family |
| Raw XAsset inventory | Broad inventory works on tested zones | Complete all-zone/base+DLC census and explicit unresolved-class list |
| Serialized walkers | Strong retained proofs exist for XModel, XAnim, clipMap and related structures | Expand to a generic audited fixture matrix for all T6 XAsset classes |

**Closure requirement:** every reconstructed asset should be traceable to container, zone layer, XAsset type/name/index, decoder revision, source bytes/hash where available, and unresolved fields.

---

# 2. GfxWorld geometry

## 2.1 Current world reconstruction

The current world path reconstructs:

- surface/material pointer relationships;
- shared vertex groups;
- triangle/index spans;
- T6 coordinate conversion for glTF;
- material identities;
- primary packed world-vertex data;
- secondary `vd1` streams for the known enum family;
- native material UV sets;
- dedicated lightmap UVs;
- deterministic normalized world and glTF/GLB output.

The retained Nuketown proof reports 5,614 surfaces, 340 unique vertex groups, 146,764 vertices across those groups, and zero bad groups for its observed formats. The canonical machine-readable census is:

`manifests/world/T6_WORLD_VERTEX_FORMAT_CENSUS_V1.json`

## 2.2 `MaterialWorldVertexFormat` closure matrix

| Format | Name | Layer/normal meaning | Synthetic/formula | Retail-byte proof | State |
|---:|---|---|---|---|---|
| 0 | `TEX_1_NRM_1` | one material UV family / base normal family | P3 | Nuketown: 220 groups | **P4** |
| 1 | `TEX_2_NRM_1` | 2 layers, 0–1 real normal-mapped layers | P3 | Nuketown: 95 groups | **P4** |
| 2 | `TEX_2_NRM_2` | 2 layers, 2 real normal-mapped layers | P3 | Nuketown: 7 groups | **P4** |
| 3 | `TEX_3_NRM_1` | 3 layers, 0–1 real normal-mapped layers | P3 | Nuketown: 17 groups | **P4** |
| 4 | `TEX_3_NRM_2` | 3 layers, 2 real normal-mapped layers | P3 | none retained | **P3; NEED P4** |
| 5 | `TEX_3_NRM_3` | 3 layers, 3 real normal-mapped layers | P3 | none retained | **P3; NEED P4** |
| 6 | `TEX_4_NRM_1` | 4 layers, 0–1 real normal-mapped layers | P3 | Nuketown: 1 group | **P4** |
| 7 | `TEX_4_NRM_2` | 4 layers, 2 real normal-mapped layers | P3 | none retained | **P3; NEED P4** |
| 8 | `TEX_4_NRM_3` | 4 layers, 3 real normal-mapped layers | P3 | none retained | **P3; NEED P4** |

The format-selection rule is source/formula-known and implemented in:

`tools/t6_layered_world_format_v1.py`

Targeted missing-fixture discovery is implemented in:

`tools/t6_world_format_target_scan_v1.py`

The scanner should be run over additional retail material/surface catalogs. Priority targets are 3-layer materials with 2–3 real normals and 4-layer materials with 2–3 real normals, because those should exercise formats 4/5/7/8.

## 2.3 Universal claim boundary

- Enum/formula implementation: **P3**.
- Nuketown formats 0/1/2/3/6: **P4**.
- Current normal production world path on proven inputs: **P6**.
- Retained outputs have been independently accepted/validated for selected fixtures: **P7 on those fixtures**.
- Universal all-map T6 GfxWorld geometry: **not yet P5/P8**.

**P8 blockers:** retail byte fixtures for 4/5/7/8, broad base+DLC map census, and any newly discovered layout variants.

---

# 3. World materials and generated/layered materials

## 3.1 Ordinary Material assets

OAT T6 Material JSON exposes exact texture semantic, image identity, sampler state, technique set, flags, and related fields. The native adapter joins by exact material identity. Filename suffix guessing is not allowed when exact semantic data exists.

Current state:
- ordinary Material -> exact OAT JSON join: **P4/P6 on tested fixtures**;
- semantic material dependency manifest: **P6**;
- conservative generic-glTF preview bindings for independently safe `colorMap` / unambiguous `normalMap`: **P6**;
- non-core Treyarch semantics preserved rather than silently force-fit into PBR.

## 3.2 Generated/layered identity grammar

Recovered behavior:

- generated identities beginning `*` encode component BSP material indices;
- decimal token is parsed as `bspMaterialIndex` and resolved through `R_GetBspMaterial(...)` in inherited recovered renderer source;
- suffix `n` means the component is expected to contain a real normal map;
- `$identitynormalmap` does not count as a real normal map;
- component identities in parentheses preserve exact layer order;
- generated texture tables concatenate component Material texture tables in layer order;
- layer count plus real-normal-map count determines the layered `worldVertFormat` family.

Nuketown retained evidence:

- 120 unique compound world materials;
- 83 unique layer-index tokens;
- 83 unique component material identities;
- perfect token <-> component mapping in the retained fixture;
- zero token ambiguity;
- 106/106 compounds with all standalone component counts available satisfy `generated textureCount == sum(component textureCount)`.

Key files:

- `tools/t6_layered_material_name_v1.py`
- `tools/test_t6_layered_material_name_v1.py`
- `manifests/maps/mp_nuketown_2020/layered_material_fixture_proof_v1.json`
- `tools/t6_oat_material_manifest_v2.py`
- `tools/test_t6_oat_material_manifest_v2.py`

Current proof:
- grammar/engine algorithm: **P2**;
- deterministic parser/validation: **P3**;
- Nuketown component graph: **P4**;
- production OAT component reconstruction: **P6**;
- cross-map layered proof: **pending P5**.

## 3.3 Layered shader composition

**Not yet T6-closed.**

Exact component dependencies, native UV families, normal-transform count, generated texture-table order, and significant technique-builder behavior are known. Full per-pixel blend/compositor/channel math for every T6 layered technique is not yet claimed.

Current state: **P1/P2 depending on individual technique behavior**.

P8 requires source/fixture closure for generated texture names/arguments, blend masks/weights/channels, representative 2/3/4-layer retail rendering validation, and Treyarch-aware Blender/wgpu reconstruction.

---

# 4. GfxImage / DDS

Current deterministic first-mip staging supports the source-closed subset encountered so far:

- BC1 / DXT1;
- BC3 / DXT5;
- BC5_UNORM / ATI2 / BC5U and supported DX10 identity;
- supported 32-bit RGBA/BGRA masked forms.

`tools/t6_dds_texture_stage_v2.py` decides BC5 normal reconstruction from exact Material dependency semantics rather than generic-glTF binding state. This covers layered `normalMap` inputs that are intentionally unbound in PBR. Mixed normal/non-normal use of a BC5 source fails closed.

Current state:
- current codec subset + regressions: **P3**;
- retail-observed subset: **P4 where fixtures exist**;
- semantic normal staging integrated: **P6**.

P8 blockers include all remaining T6 image formats, mip chains, arrays/cubemaps, exact sRGB/linear semantics, reflection-probe images, and archival representation of complete source mip data.

---

# 5. Portable material-image GLB

`tools/t6_world_textured_gltf_export_v2.py` embeds every exact staged material dependency image into the GLB. Only source-approved standard-preview bindings are connected to generic glTF slots. Layered/specular/packed/decal/etc. images remain embedded with exact T6 provenance and generated texture indices.

Current state:
- full staged material-image portability: **P6**;
- compound “embedded but not fake-PBR-bound” regression: **P3/P6**;
- faithful Treyarch shading using generic glTF alone: intentionally **not claimed**.

---

# 6. Lightmaps

## 6.1 T6 ownership structure

Direct T6 structures establish:

- `GfxWorld.lightmapCount`;
- `GfxWorld.lightmaps`;
- `GfxLightmapArray.primary`;
- `GfxLightmapArray.secondary`;
- each entry references exact `GfxImage` assets.

World surfaces already retain `lightmapIndex`, and the world decoder already carries the dedicated lightmap UV independently of ordinary material UV sets.

## 6.2 Exact join manifest

`tools/t6_world_lightmap_manifest_v1.py` defines:

```text
GfxSurface.lightmapIndex
  -> GfxLightmapArray[index]
  -> primary GfxImage + secondary GfxImage
```

and records the exact glTF texture-coordinate set containing the lightmap UV.

`tools/test_t6_world_lightmap_manifest_v1.py` has been independently executed against the current algorithm and passes its deterministic and fail-closed cases.

Current algorithm state: **P3**.

## 6.3 Exact catalog extraction

Stock OpenAssetTools at pinned commit `7d027e8f89118196713e955b0e11f8404149c54d` declares T6 GfxWorld but leaves its ObjWriter GfxWorld dumper commented out.

A minimal patch is retained under:

`tools/t6_gfxworld_lightmap_oat_patch/`

It emits only exact loaded T6 data:

```text
lightmapCount
lightmaps[i].primary->name
lightmaps[i].secondary->name
```

and deliberately avoids unstable process pointers or guessed shader semantics.

The patch source is archived and integration instructions are pinned, but **it has not yet been promoted to retail proof until it is compiled/run against a retained T6 GfxWorld and the output is archived**.

## 6.4 Sentinel and shader boundaries

Inherited renderer evidence uses lightmap index `31` as no-lightmap. The manifest preserves this sentinel, but the strongest explicit sentinel evidence is currently inherited renderer code rather than a dedicated retained T6 sentinel proof. Keep that distinction visible until T6 retail proof is archived.

Primary and secondary are bound separately by the inherited renderer. Their exact channel/shader composition remains **P0/P1** and must not be flattened by guesswork.

Current lightmap state:
- T6 array ownership: **P2**;
- surface/index/UV side on Nuketown: **P4**;
- join algorithm: **P3**;
- exact Nuketown primary/secondary catalog: **pending P4**;
- pair image staging/embedding: pending;
- primary/secondary shader meaning: **P0/P1**.

---

# 7. Reflection probes / environment data

T6 GfxWorld structure contains reflection-probe arrays/textures and surfaces retain reflection-probe indices in current mappings.

Current state: structural knowledge ahead of export closure.

P8 requires exact probe image catalog, cubemap/array decode, per-surface/probe assignment, blending/runtime behavior, Blender/wgpu representation, and cross-map validation.

---

# 8. Static XModels and map placement

Retained Nuketown assembly work established a broad static path, including complete placement coverage for the retained archive and hundreds of model identities/LODs. Earlier coordinate/scale/accessor defects were corrected rather than hidden.

Current state:
- rigid XModel mesh decoding/export: **P4/P6 on tested fixtures**;
- retained Nuketown static assembly: **P4/P6/P7 for that output**;
- universal all-map static-model claim: pending cross-map **P5**.

Special model classes/edge cases remain explicit additions rather than fallback approximations.

---

# 9. Blended/skinned XModels

The retained retail `german_shepherd` census records:

- 56 bones;
- 3 surfaces;
- 5,731 vertices;
- 7,123 triangles;
- 1,177 rigid vertices;
- 4,554 blended vertices;
- 0 unweighted vertices;
- overall influence histogram: 2,353 one-bone, 1,149 two-bone, 1,340 three-bone, 889 four-bone;
- native `vertsBlend` word consumption of 1/3/5/7 words for 1/2/3/4-influence blended vertices.

Fixture expectation:

`manifests/xmodels/german_shepherd_skin_expectation_v1.json`

Generalized exporter already exists:

`tools/t6_xanim_skinned_gltf_export_v4.py`

It validates native rigid + 1/2/3/4-influence blended rows, rejects unweighted vertices and malformed joints/weights, and can export a bind-pose skinned model without an XAnim.

A dedicated synthetic validator regression now exists:

`tools/test_t6_xanim_skinned_gltf_export_v4.py`

Its skin-row cases have been independently exercised against the current validation algorithm.

Current state:
- shepherd retail census / blend-stream structure: **P4**;
- generalized skin-row validation: **P3**;
- generalized v4 export implementation: exists, but full exporter integration/fixture proof still needs retained deterministic artifacts;
- shepherd normalized mesh+skeleton sidecars and exported glTF/GLB: **not yet archived**;
- independent shepherd consumer validation: **pending P7**.

**Next shepherd proof:** regenerate normalized mesh and skeleton from the exact owning retail fastfile, run v4 in bind-pose mode, archive source/output hashes and counts, then independently load in Blender/another glTF implementation. Do not claim shepherd export P4/P7 before those artifacts exist.

---

# 10. Skeletons, bind transforms, inverse bind matrices

For the retained animated Nuketown display-glass fixture:

- 34-joint hierarchy reconstructed;
- inverse bind matrices validated;
- reconstructed hierarchy matches XModel global bind matrices;
- `globalBind * inverseBind` reached identity within the validated float path;
- triangle/joint indices are valid;
- rigid weights sum to one.

Current state: **P4/P7 on that retail fixture**.

P8 requires materially different blended character/viewhand hierarchies and any pathological parent/root cases.

---

# 11. XAnim

A real retail animated Nuketown map object (`fxanim_mp_nuked2025_display_glass_mod`) survives into standard glTF with retail mesh, 34-joint skin, three surfaces, and 66 animation channels.

Important recovered rule for the validated non-root translation path:

```text
glTF local translation
  = XModel bind-local translation
  + XAnim translation delta
```

Rotations use the decoded local quaternion on the proven path.

Current state:
- retained rigid animated map fixture: **P4/P6/P7**;
- generalized XAnim decoding has multiple retained manifests/tools;
- blended character + XAnim combined retail proof: pending;
- root translation, deltaPart model binding, notetracks, special compression branches, and all variant forms remain independently tracked.

`tools/t6_xanim_skinned_gltf_export_v4.py` intentionally rejects bound deltaPart and animated root translation until those model-binding semantics are separately source-closed.

---

# 12. Dynamic/animated map objects

Display glass proves a real retail map XModel + XAnim path. Full map dynamics are broader.

P8 still requires automatic entity/asset linkage, movers/doors/destructibles, runtime state, FX attachments, triggers, and any non-XModel animation systems used by maps.

---

# 13. Collision / clipMap

Primary clipMap decoding has extensive retained and cross-map proof work in `manifests/maps/`, including PVS, static-model constraints, dynamic entity collision, and normalized outputs.

Current state: strong partial/cross-fixture coverage; not yet declared globally P8.

Remaining work includes all primitive/brush/tree/partition variants, gameplay metadata, runtime-query parity where feasible, and explicit separation of render/collision semantics.

---

# 14. MapEnts / AddonMapEnts / GameWorld

Entity data is preserved and partially decoded; selected data can already be represented as scene empties/metadata.

Full closure still requires key/value and string-model coverage, target/parent/script links, static/dynamic asset linkage, AddonMapEnts patch behavior, GameWorld dynamic structures, movers/destructibles/triggers, and runtime semantics.

---

# 15. Lighting beyond baked lightmaps

Still open or only structurally known:

- primary lights;
- sun parameters;
- light grid / probe-like volume data;
- shadow metadata;
- emissive interaction;
- dynamic lights;
- fog/atmosphere and related renderer state.

Current state: mixed **P0–P2**, not export-closed.

---

# 16. Special surface/material behavior

Explicit separate closure targets include:

- alpha test/cutout;
- transparent glass;
- distortion/refraction;
- decals and layered decals;
- emissive;
- scrolling/animated UVs;
- water;
- reflection/environment sampling;
- packed gloss/specular/opacity channels;
- terrain/layer blends;
- sampler-state edge cases;
- technique-specific vertex/pixel constants.

Current policy is to preserve exact technique set, textures, samplers, constants, flags, and component graph before reproducing renderer behavior.

---

# 17. Weapons / attachments / equipment / camos / tracers / viewhands

MP definition work separates normal player weapons, equipment, alternate/attachment variants, and scorestreak/internal/helper definitions while respecting patch overrides.

Definition inventory/classification is much farther along than complete first-person reconstruction.

Future ledger subdivision must cover WeaponDef, Attachment, Camo, Tracer, weapon/viewhand XModels, XAnims, materials, FX, and audio dependencies independently.

---

# 18. Characters / AI / animals / vehicles / props

The shepherd is now the key retained blended-model fixture. Broader model/animation inventories exist, but full semantic grouping/runtime linkage remains open.

P5/P8 requires representative player bodies, viewhands, AI, animals, vehicles, attachment/cloth edge cases, heads/facial assets where applicable, and physics/destruction-linked props.

---

# 19. FX

FX assets are inventoried in MP work, but a faithful FX graph/renderer is not yet closed.

Future work must separately prove element graphs, sprites/materials, model emitters, trails/beams, decals, lights, timing/randomization, spawn transforms, physics/collision interactions, and map/entity references.

---

# 20. Audio

SABS/SABL preservation is in scope, but bank/event/runtime semantics are not yet globally solved.

P8 requires bank/index structures, codec extraction, aliases/events, spatial/volume/pitch/randomization metadata, weapon/FX/entity linkage, dialogue/music categories, and patch/DLC precedence.

---

# 21. UI / scripts / gameplay data / every remaining XAsset class

These remain part of the **all of T6** target even when the current map exporter does not need them.

The ledger must eventually contain dedicated closure matrices for script/string/localization/UI/menu/font/rawfile and gameplay-definition classes plus every other T6 XAsset identity encountered by the complete zone census.

Nothing becomes “solved” merely because it is outside the map path.

---

# 22. Production world pipeline

Current strongest production entry point:

`tools/t6_oat_world_textured_export_pipeline_v3.py`

It promotes:

1. audited world normalization / geometry-only GLB;
2. OAT material manifest v2 with generated/layered component reconstruction;
3. semantic-aware DDS stage v2;
4. portable textured GLB v2 embedding every exact material dependency image;
5. optional exact world lightmap manifest v1.

The lightmap pair images are not yet shaded or folded into generic glTF because the exact retail pair catalog and primary/secondary shader composition remain separate proof boundaries.

---

# 23. Durable checkpoint chain

Important recent checkpoints include:

- `d463e73` — rigid T6 XModel render normalizer
- `e21e78a` — compact display-glass render proof
- `80d6dee` — animated rigid-mesh glTF v3 exporter
- `43f047d` — full retail animated glTF proof
- `9289d04` — generated/layered material identity decoder
- `5348726` — layered grammar regression
- `90e98de` — Nuketown layered-material retail proof
- `ef33fd8` — OAT material manifest v2 compound reconstruction
- `3ae75a4` — strict compound adapter regression
- `70ff35e` — OAT layered world pipeline v2
- `2307ee3` — layered world-format rule
- `9e9559f` — world-format family regression
- `2dba109` — targeted format-4/5/7/8 scanner
- `b59cc0f` — scanner regression
- `599edab` — semantic-aware DDS/BC5 stage v2
- `585f781` — DDS v2 regression
- `ce21547` — portable all-dependency textured GLB v2
- `f9fc6c1` — portable dependency regression
- `20243a8` — world lightmap pair manifest v1
- `d1a7990` — lightmap manifest regression
- `2634316` — production OAT world pipeline v3
- `186ec46` — T6 proof standard
- `e9e68b6` — initial whole-project closure ledger
- `21cdb07` — hardened GfxWorld lightmap catalog JSON output
- `15c75c3` — pinned OAT lightmap patch integration/proof instructions
- `57d0221` — exact OAT ObjWriter registration diff
- `a67f5ab` — skinned XModel v4 skin-row regression
- `81741bb` — root README promoted to current proof/pipeline state

Historical commits are durable evidence checkpoints, not substitutes for current validation.

---

# 24. Immediate queue

1. Compile/apply the pinned T6 GfxWorld lightmap OAT patch against the retained retail extractor environment.
2. Emit and archive the first real `t6-gfxworld-lightmap-catalog-v1` for Nuketown.
3. Join Nuketown surfaces to exact primary/secondary image identities and create a P4 proof manifest with source/output hashes.
4. Stage/embed both exact lightmap image sets as unbound T6 dependencies; do not guess the shader combination.
5. Trace primary/secondary lightmap sampler/channel/shader semantics and validate representative surfaces.
6. Run `t6_world_format_target_scan_v1.py` over additional retail MP maps, then Zombies/SP/DLC as inputs become available; acquire P4 fixtures for 4/5/7/8.
7. Promote every newly found world layout through P4 -> P5 before calling world decoding universal.
8. Regenerate `german_shepherd` normalized mesh+skeleton from exact retail bytes, export through skinned v4, hash it, and independently validate it.
9. Add a materially different human/viewhand blended fixture for P5 skinning coverage.
10. Continue world fidelity: reflection probes, layered shader math, light grid/primary lights, glass/alpha/decal/emissive/water/special techniques.
11. Repeat this same proof discipline across FX, audio, weapons, characters, vehicles, scripts/UI/gameplay data, and every remaining T6 XAsset class.

---

# 25. Definition of project completion

The intended T6 archival/reconstruction project is complete only when:

- base, patch, DLC, MP, Zombies, and SP source sets used by the project have explicit provenance;
- every encountered serialized variant has retained fixtures and deterministic decoders;
- every meaningful T6 XAsset class has a closure entry and no hidden unsupported branch;
- world geometry/materials/lightmaps/probes/lights/collision/entities/dynamics can be reconstructed faithfully;
- rigid and blended XModels, skeletons, XAnims, images/materials, FX, audio, and gameplay definitions remain linked to exact source identities;
- production exporters consume the strongest proof-backed decoders;
- independent consumers validate the exported forms;
- the declared archival/reconstruction scope has no unresolved semantics that materially affect fidelity.

Until then, every newly encountered structure becomes a new explicit ledger item rather than an undocumented exception.
