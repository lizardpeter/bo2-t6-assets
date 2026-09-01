# T6 Reverse-Engineering Closure Ledger

**Project:** Call of Duty: Black Ops II / Treyarch T6  
**Purpose:** Permanent, conservative record of what is known, what is proven, what is merely supported synthetically, and what still blocks a faithful whole-game reconstruction.  
**Proof rules:** See `research/T6_PROOF_STANDARD.md`.  
**Last updated:** 2026-09-01

This ledger is intentionally stricter than a feature checklist. A subsystem is not marked solved merely because an exporter produces a visually plausible result.

## Proof-state shorthand

- **P0** unknown
- **P1** structural hypothesis
- **P2** source/formula known
- **P3** deterministic synthetic regression proven
- **P4** retained retail byte/asset proven
- **P5** cross-fixture retail proven
- **P6** normal export/archive pipeline integrated
- **P7** independent consumer validated
- **P8** T6-closed / fully solved for intended scope

A row may list different proof levels for different parts of the same subsystem.

---

# 1. Source containers, XAssets, and provenance

| Area | Current state | Evidence / implementation | Remaining closure work |
|---|---|---|---|
| Source FF/IPAK/SABS/SABL/IWD preservation | Preserved sources are treated as archival truth; preservation is separate from decode completeness | repository source-container policy; SHA-256 manifests where retained | Ensure every retail/DLC source used later is hashed and provenance-linked; preservation alone is not P8 decoding |
| MP base/patch precedence | Proven workflow rule: base -> common patch -> patch; duplicate XAsset names are overrides, not additive assets | Stage 18C weapon classification and repository README | Generalize winning-source provenance to every XAsset class and every zone family |
| XAsset inventory | Broad inventory works for tested MP zones | existing collectors/manifests | Make a complete all-zone/base+DLC census and record unresolved XAsset classes |
| Serialized XAsset walking | Strong for several classes, including XModel/XAnim/clipMap proofs | serialized walker tools/manifests | One generic audited walker/fixture matrix for every T6 XAsset type |

**Closure target:** Every exported asset must identify source container, XAsset type/name/index, winning patch layer, serialized proof range/hash where possible, decoder version, and unresolved fields.

---

# 2. GfxWorld geometry

## 2.1 Base world surface reconstruction

**Current state:** Geometry reconstruction is mature for the retained Nuketown fixture and generic synthetic coverage is broader.

Known/proven pieces include:
- surface/material pointer resolution;
- shared vertex-group reconstruction;
- index/triangle reconstruction;
- T6 coordinate-system conversion for glTF;
- native material identity preservation;
- world lightmap UV extraction;
- secondary `vd1` stream formulas for all known enum layouts;
- deterministic normalized world and glTF/GLB output.

The retained Nuketown proof has zero bad vertex groups for the observed formats and carries exact samples of primary/secondary streams.

## 2.2 `MaterialWorldVertexFormat` closure matrix

Recovered family:

| Format | Structural name | Layer/normal meaning | Synthetic | Retained retail byte proof | Status |
|---:|---|---|---|---|---|
| 0 | `TEX_1_NRM_1` | one texture coordinate family / one normal transform family | P3 | Nuketown observed: 220 groups | **P4 on Nuketown** |
| 1 | `TEX_2_NRM_1` | 2-layer material, 0-1 real normal-mapped layers | P3 | Nuketown observed: 95 groups | **P4 on Nuketown** |
| 2 | `TEX_2_NRM_2` | 2 layers, 2 real normal-mapped layers | P3 | Nuketown observed: 7 groups | **P4 on Nuketown** |
| 3 | `TEX_3_NRM_1` | 3 layers, 0-1 real normal-mapped layers | P3 | Nuketown observed: 17 groups | **P4 on Nuketown** |
| 4 | `TEX_3_NRM_2` | 3 layers, 2 real normal-mapped layers | P3 | no retained retail fixture yet | **P3; NEED P4** |
| 5 | `TEX_3_NRM_3` | 3 layers, 3 real normal-mapped layers | P3 | no retained retail fixture yet | **P3; NEED P4** |
| 6 | `TEX_4_NRM_1` | 4 layers, 0-1 real normal-mapped layers | P3 | Nuketown observed: 1 group | **P4 on Nuketown** |
| 7 | `TEX_4_NRM_2` | 4 layers, 2 real normal-mapped layers | P3 | no retained retail fixture yet | **P3; NEED P4** |
| 8 | `TEX_4_NRM_3` | 4 layers, 3 real normal-mapped layers | P3 | no retained retail fixture yet | **P3; NEED P4** |

The format-selection rule is source/formula-known: layer count selects the texture-coordinate family and each real normal-mapped layer beyond the first increments the normal-transform variant. This is encoded in `tools/t6_world_vert_format_from_material_v1.py` and regression-tested.

**Critical next fixture task:** run `tools/t6_world_vert_format_fixture_scan_v1.py` against additional retail maps and prioritize maps containing predicted formats 4/5/7/8. Preserve the first raw `vd0`/`vd1` fixture for each before changing the decoder.

## 2.3 Universal GfxWorld geometry status

- Generic enum/formula support: **P3**.
- Nuketown observed formats 0/1/2/3/6: **P4**.
- Cross-map universal claim: **not yet allowed**.
- Production geometry pipeline: **P6 for the currently proven inputs**.
- Independent glTF/GLB loader validation has been used on retained world outputs: **P7 for those fixtures**.

**P8 blockers:** retail fixtures for 4/5/7/8; broad base/DLC map census; any newly observed world-layout variants must fail closed and be added here.

---

# 3. World materials and layered/generated materials

## 3.1 Ordinary Material assets

OAT T6 Material JSON exposes exact texture semantics, image asset identities, sampler state, technique-set identity, flags, and related metadata. The native path joins by exact material name; filename suffix guessing is explicitly forbidden when exact semantics exist.

Current state:
- exact ordinary Material -> OAT JSON join: **P4/P6 on tested fixtures**;
- semantic dependency manifest: **P6**;
- conservative standard glTF preview bindings for independently safe roles (`colorMap`, `normalMap` when unambiguous): **P6**;
- non-core Treyarch semantics remain preserved rather than force-fit into PBR.

## 3.2 Generated/layered material identity grammar

Recovered behavior:
- generated identities beginning `*` encode component BSP material indices;
- decimal token -> `R_GetBspMaterial(bspMaterialIndex)` in inherited recovered engine code;
- suffix `n` means the component is expected to have a real normal map;
- `$identitynormalmap` does not count as a real normal map;
- component names in parentheses provide exact material identities in layer order;
- generated texture table is the concatenation of each component Material texture table in layer order;
- layered technique selection determines world vertex format from layer count + real normal-map count.

Nuketown retained evidence:
- 120 unique compound world materials;
- 83 unique numeric layer tokens;
- 83 unique component material identities;
- perfect token <-> component identity mapping in the retained fixture;
- zero token ambiguity;
- 106/106 compounds whose standalone component texture counts were available have generated `textureCount == sum(component textureCount)`.

Current proof:
- grammar/source behavior: **P2**;
- grammar and validation regressions: **P3**;
- Nuketown component graph + count relationships: **P4**;
- OAT component reconstruction and exact generated texture-index order: **P6** in v2 material adapter;
- cross-map proof: **pending P5**.

## 3.3 Layered shader composition

**Not solved yet.**

We have exact component dependencies, UV families, normal-transform count, generated texture-table order, and generated technique-set selection behavior. We do **not** yet claim the full pixel-level blend/compositor math used by every T6 layered technique.

Current state: **P1/P2 depending on individual recovered technique-builder details**.

P8 requires:
- decode generated texture-name namespacing and shader argument binding completely;
- recover blend weights/masks/channel semantics;
- validate representative 2/3/4-layer materials against retail rendering or equivalent shader source;
- implement Treyarch-aware Blender/wgpu reconstruction;
- keep generic glTF fallback conservative.

---

# 4. Texture containers / DDS decoding

Current deterministic first-mip staging supports the source-closed subset already encountered in retained extraction work:
- BC1 / DXT1;
- BC3 / DXT5;
- BC5_UNORM / ATI2 / BC5U / supported DX10 identity;
- supported 32-bit RGBA/BGRA masked forms.

`tools/t6_dds_texture_stage_v2.py` fixes a critical layered-material case: BC5 normal reconstruction is decided by exact Material dependency semantics, not merely whether the texture is bound to core glTF. Unbound layered `normalMap` textures therefore reconstruct positive Z correctly. Mixed normal/non-normal reuse of one BC5 source fails closed.

Current state:
- codec implementation + synthetic regression: **P3**;
- observed retail format subset: **P4 where retained fixtures exist**;
- semantic normal handling integrated: **P6**.

P8 blockers:
- all T6 GfxImage/DDS format variants across base + DLC;
- mip/array/cubemap handling beyond current preview/staging needs;
- exact sRGB/linear policy per image semantic;
- cubemap/reflection-probe integration;
- preserve/represent source mip chains in final archival format where appropriate.

---

# 5. Portable world GLB material dependencies

`tools/t6_world_textured_gltf_export_v2.py` embeds **every exact staged material dependency image** into the GLB. Only independently safe standard-preview entries are connected to generic glTF PBR fields. Layered/specular/packed/decal/etc. images remain available in the GLB with exact T6 provenance and generated texture indices but are not falsely bound.

Current state:
- complete material image portability for staged dependencies: **P6**;
- deterministic regression proving compound dependencies are embedded but not invented as PBR: **P3/P6**;
- exact Treyarch rendering from generic GLB alone: **not solved** because the renderer-specific shader graph is intentionally still open.

---

# 6. Lightmaps

## 6.1 Source structure

T6 `GfxWorld` contains:
- `lightmapCount`;
- `GfxLightmapArray* lightmaps`;
- per-entry `GfxImage* primary`;
- per-entry `GfxImage* secondary`.

T6 surfaces contain `lightmapIndex`. World vertex decoding already supplies the dedicated lightmap UV values independently from material UV0/UV1/etc.

`tools/t6_world_lightmap_manifest_v1.py` defines a strict join:

`GfxSurface.lightmapIndex -> GfxLightmapArray[index] -> primary + secondary GfxImage`

and records the exact glTF texture-coordinate set holding the lightmap UVs.

## 6.2 Sentinel boundary

Inherited renderer evidence treats lightmap index **31** as no-lightmap. The manifest currently preserves that behavior, but because the strongest explicit sentinel evidence currently comes from inherited engine renderer code rather than a dedicated retained T6 sentinel proof, the ledger keeps that distinction visible.

## 6.3 Current state

- T6 ownership/array structure: **P2** from T6 structures.
- manifest algorithm: **P3** with `test_t6_world_lightmap_manifest_v1.py`.
- exact Nuketown primary/secondary image catalog: **not yet retained**.
- surface lightmap UV/index side: **P4 on Nuketown**.
- primary/secondary image staging/binding: **pending**.
- shader meaning of primary vs secondary: **P0/P1; do not merge or guess**.

**Immediate closure task:** extend the raw GfxWorld extraction/walker to emit `t6-gfxworld-lightmap-catalog-v1` from the serialized `lightmaps[]` array, preserving image pointers/names and source proof. Then join Nuketown and stage both image sets without applying guessed shading.

---

# 7. Reflection probes / environment data

Known T6 GfxWorld structure includes reflection-probe arrays and textures. World surfaces already retain `reflectionProbeIndex` in material/surface mapping artifacts.

Current state: **structurally known but not export-closed**.

P8 requires:
- exact probe image identity catalog;
- cubemap/array decoding;
- exact per-surface/probe assignment;
- renderer behavior and blending policy;
- Blender/wgpu representation;
- cross-map validation.

---

# 8. Static XModels and map placement

Nuketown retained assembly proves a broad static-model path:
- 2,992/2,992 archive placements in the full retained assembly;
- 349 model identities exported for that archive;
- 756 LOD GLBs in the retained build;
- playable subset and material-slot proofs preserved separately;
- model placement transforms and map/world scale corrected from earlier broken exports.

Rigid XModel mesh decoding/export is mature enough for production use on retained fixtures.

Current state:
- rigid mesh structure/export: **P4/P6 on tested fixtures**;
- Nuketown static placement assembly: **P4/P6/P7 for retained output**;
- universal all-map static XModel claim: **pending cross-map P5**;
- special model classes/edge cases continue to be added rather than coerced.

---

# 9. Blended/skinned XModels

A retained retail `german_shepherd` XModel fixture established a real 56-bone blended model:
- 5,731 vertices;
- 7,123 triangles;
- 3 surfaces;
- 4,554 blended vertices;
- 1,177 rigid vertices;
- 0 unweighted vertices;
- influence buckets observed across 1/2/3/4 influences;
- native `vertsBlend` consumption pattern recovered for those influence counts.

Current state:
- blended stream structure on the retained fixture: **P4**;
- generic deterministic skinned-XModel GLB exporter: **not yet promoted to the same closure level as rigid v3**;
- additional human/animal/weapon/viewhand fixtures: **needed for P5**.

**High-priority task:** finish the 56-bone shepherd as a fully skinned GLB, independently validate bind pose + weights, then fold blended vertices into the normal XModel exporter without changing the already-proven rigid path.

---

# 10. Skeletons, bind transforms, and inverse bind matrices

For the retained animated rigid display-glass fixture:
- 34-joint hierarchy reconstructed;
- inverse bind matrices validated;
- reconstructed global bind matrices match XModel bind hierarchy;
- `globalBind * inverseBind` reached zero/float-precision identity error in validation;
- triangle/joint indices valid;
- rigid weights sum correctly.

Current state: **P4/P7 on that retail fixture**.

P8 requires cross-fixture validation with genuine blended character/viewhand models and pathological hierarchies if present.

---

# 11. XAnim

A real retail animated map object (`fxanim_mp_nuked2025_display_glass_mod`) is exported as glTF with:
- real retail mesh;
- 34-joint skin;
- three mesh surfaces;
- 66 animation channels.

Important recovered translation rule:

For non-root animated bones, T6 XAnim translation tracks are deltas relative to the XModel bind-local translation. Exported glTF local translation therefore uses:

`XModel bind-local translation + XAnim translation delta`

Rotations use the decoded XAnim local quaternion directly for the validated path.

Current state:
- retained rigid animated map object: **P4/P6/P7**;
- generalized animation decode has strong coverage in existing XAnim tools;
- skinned character animation combined with blended XModel export: **next cross-domain proof**;
- root motion, notetracks, special animation forms, delta variants, and every retail compression branch must remain individually tracked until fixture-covered.

---

# 12. Dynamic/animated map objects

The display-glass proof establishes that at least one real retail dynamic map XModel + XAnim can survive into standard glTF with skeleton and animation intact.

Current state: **P4/P6/P7 for the retained fixture**.

P8 requires:
- automatic entity/asset linkage from maps;
- all animated map-object classes;
- destructibles/doors/movers where represented outside the simple XModel+XAnim pair;
- FX attachment relationships;
- runtime state/trigger semantics where required for a faithful scene/game reconstruction.

---

# 13. Collision / clipMap

Primary clipMap decoding has extensive work and cross-map regression artifacts in the repository. The Blender/world assembler can consume the proven collision representation.

Current state: **strong partial / cross-fixture**, but collision should not yet be called globally P8.

P8 requires:
- full primitive/brush/partition/tree coverage across base + DLC;
- all gameplay-relevant collision metadata;
- parity checks against runtime queries where possible;
- clear separation of render geometry from collision geometry.

---

# 14. MapEnts / AddonMapEnts / GameWorld

Map entity data is preserved and partially decoded. It is useful for entity placement and asset linkage, but not every semantic/runtime relationship is closed.

Current state:
- preservation: strong;
- selected parsing/empties: partial;
- full entity/runtime semantics: **not solved**.

P8 requires:
- entity key/value/string model closure;
- target/parent/script relationships;
- static/dynamic asset linkage;
- AddonMapEnts patch behavior;
- GameWorld dynamic-entity structures;
- movers/destructibles/triggers where applicable.

---

# 15. Lighting beyond baked lightmaps

Still to close:
- primary lights;
- light grid / volumetric or probe-like lighting data;
- sun direction/color and map-global lighting parameters;
- shadow metadata;
- emissive interaction;
- runtime/dynamic lights;
- fog/atmosphere where encoded in renderer/world assets.

Current state: **mixed P0-P2 structural knowledge; not export-closed**.

---

# 16. Special surface/material behavior

Explicit unsolved or partially solved classes include:
- alpha test / cutout;
- transparent glass;
- refractive/distortion materials;
- decals and layered decals;
- emissive materials;
- scrolling/animated UVs;
- water;
- environment/reflection sampling;
- packed gloss/specular/opacity channels;
- terrain/layered blends;
- special sampler states;
- technique-specific vertex/pixel constants.

Rule: preserve technique set, exact textures, sampler state, constants, flags, and component graph now; only reproduce renderer behavior when the corresponding semantics are source/fixture-closed.

---

# 17. Weapons, attachments, equipment, camos, tracers, and viewhands

The MP definition inventory/classification work has separated player weapons, equipment, alternate/attachment variants, and internal/scorestreak definitions. Patch-layer duplicates are treated as overrides.

Current state:
- definition inventory/classification: mature for tested MP source layers;
- asset/model/animation dependency closure per weapon: ongoing;
- complete first-person weapon + viewhands + animation + material + sound + FX reconstruction: **not P8**.

The T6-wide ledger will eventually split this section into individual schemas for WeaponDef, Attachment, Camo, Tracer, weapon XModels, viewhands, XAnims, FX, and sounds.

---

# 18. Characters, AI, vehicles, and world props

Broad model/animation inventories exist, and the shepherd is now a crucial blended-model fixture. Full semantic grouping and runtime linkage remain incomplete.

P8 requires representative fixtures for:
- player bodies;
- first-person arms/viewhands;
- AI characters and animals;
- vehicles;
- cloth/secondary attachments if encoded specially;
- facial/head assets where applicable;
- physics/destruction-linked props.

---

# 19. FX

FX assets are inventoried in MP source work but a full faithful FX renderer/exporter is not yet closed.

Required future decomposition includes:
- effect graphs/elements;
- sprite/material dependencies;
- model emitters;
- trails/beams;
- decals;
- lights;
- timing/randomization;
- spawn/attachment transforms;
- physics/collision interactions;
- map/entity references.

Current state: **inventory/provenance ahead of semantic reconstruction**.

---

# 20. Audio

SABS/SABL containers are preserved in the project scope, but complete audio bank/event/runtime semantic reconstruction is not yet represented here as solved.

P8 requires:
- bank/index structures;
- codec/data extraction;
- aliases/events;
- spatial/volume/pitch/randomization metadata;
- weapon/FX/entity linkage;
- music/dialogue/runtime categories;
- base/patch/DLC precedence.

---

# 21. UI / scripts / gameplay data / other XAsset classes

These remain part of the long-term **all of T6** objective, even when the current map exporter does not need them.

The ledger must eventually have dedicated closure matrices for all remaining T6 XAsset classes, including script/string/localization/UI/menu/font/rawfile-related classes and gameplay definition assets.

Nothing is considered solved merely because it is outside the current map path.

---

# 22. Production world export pipeline

Current strongest production entry point:

`tools/t6_oat_world_textured_export_pipeline_v3.py`

It promotes the strongest current stages:

1. audited raw world normalization / geometry-only GLB;
2. OAT material manifest v2 with source-closed layered component reconstruction;
3. DDS stage v2 with semantic-aware BC5 handling;
4. portable textured GLB v2 embedding every exact material dependency image;
5. optional exact world lightmap manifest v1.

The lightmap pair images are not yet applied or embedded by this v3 path because the raw T6 lightmap image catalog still needs a retained retail extraction fixture and the primary/secondary shader combination remains intentionally unresolved.

---

# 23. Recent closure checkpoints

Recent commits that must remain useful historical checkpoints:

- `d463e73` — rigid T6 XModel render normalizer
- `e21e78a` — compact display-glass render proof
- `80d6dee` — animated rigid-mesh glTF v3 exporter
- `43f047d` — full retail animated glTF proof
- `9289d04` — layered/generated material identity decoder
- `5348726` — layered-name grammar regression
- `90e98de` — Nuketown layered-material fixture proof
- `ef33fd8` — OAT material manifest v2 layered reconstruction
- `3ae75a4` — strict layered adapter regression
- `70ff35e` — OAT layered world export pipeline v2
- `2307ee3` — source-closed layered world-vertex-format rule
- `9e9559f` — all-family world-format regression
- `2dba109` — target scanner for missing retail formats 4/5/7/8
- `b59cc0f` — scanner regression
- `599edab` — semantic-aware DDS/BC5 stage v2
- `585f781` — DDS stage v2 regression
- `ce21547` — portable all-dependency textured world GLB v2
- `f9fc6c1` — portable dependency regression
- `20243a8` — exact world lightmap-pair manifest v1
- `d1a7990` — lightmap manifest regression
- `2634316` — production OAT world export pipeline v3
- `186ec46` — permanent T6 proof standard

Historical commits are evidence checkpoints, not substitutes for current tests.

---

# 24. Immediate queue

Order unless new retail evidence changes priorities:

1. **Emit a retail `t6-gfxworld-lightmap-catalog-v1` directly from serialized GfxWorld.**
2. Join Nuketown surfaces to exact primary/secondary lightmap GfxImages and archive the proof.
3. Stage/embed both lightmap image sets as unbound T6 dependencies; do not guess their shader blend.
4. Trace primary/secondary lightmap shader sampling and channel meaning.
5. Run the targeted world-format scanner over more retail MP maps; acquire first P4 fixtures for formats 4/5/7/8.
6. Promote each newly found world format from synthetic P3 to retained retail P4, then cross-map P5.
7. Finish the `german_shepherd` 56-bone blended-XModel GLB and independent weight/bind-pose validation.
8. Fold blended vertices into the generic XModel exporter.
9. Validate skinned XModel + XAnim together on a real character/animal animation.
10. Expand world fidelity: reflection probes, layered shader semantics, light grid/primary lights, alpha/glass/decal/emissive/water/special techniques.
11. Repeat the same proof discipline across every remaining T6 XAsset family until the ledger contains no P0/P1 gaps that affect faithful archival/reconstruction.

---

# 25. Definition of project completion

The project reaches its intended end state only when:

- all retail base + patch + DLC content needed for T6 is inventoried with winning provenance;
- every encountered serialized variant has retained fixtures and deterministic decoders;
- every significant T6 XAsset class has a closure entry and no hidden unsupported branches;
- world geometry/materials/lightmaps/probes/lights/collision/entities/dynamics can be reconstructed faithfully;
- rigid and blended XModels, skeletons, XAnims, materials, images, FX, audio, and gameplay definitions are preserved and linked;
- production exporters consume the strongest proof-backed decoders;
- independent consumers validate the exported forms;
- unresolved semantics are zero for the declared T6 archival/reconstruction scope.

Until then, the ledger remains open and every newly discovered format becomes a new explicit row rather than an undocumented exception.
