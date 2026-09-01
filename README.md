# Black Ops II (T6) Asset Archive

Private archival/research repository for the ongoing Call of Duty: Black Ops II / Treyarch T6 asset extraction, reverse engineering, validation, and reconstruction project.

The long-term target is **all of T6**, not merely a visually plausible map converter. Every format and relationship is advanced through retained evidence, deterministic decoders/tests, explicit proof boundaries, and production integration.

## Proof discipline

Read these first:

- `research/T6_PROOF_STANDARD.md` — defines P0 through P8 and what the project is allowed to call “solved”.
- `research/T6_REVERSE_ENGINEERING_LEDGER.md` — permanent subsystem-by-subsystem closure ledger for world formats, materials, images, lightmaps, XModels, XAnim, collision, entities, lighting, FX, audio, weapons, characters, UI/scripts, and remaining T6 XAsset classes.
- `research/T6_PROGRESS_2026-09-01_LIGHTMAP_V4.md` — exact checkpoint for the current world/lightmap v4 and retail-shader work.

The central rule is:

> Formula support, a synthetic regression, a retail byte fixture, cross-fixture proof, export integration, and independent consumer validation are different milestones. Do not silently promote one into another.

Unknown or ambiguous data fails closed and remains preserved for later work.

## Repository goals

- Preserve exact source provenance (`base -> common patch -> patch`) instead of treating patch-layer counts as additive.
- Preserve original FF/IPAK/SABS/SABL/IWD sources and hashes where available.
- Keep decoded assets separate from tools, proof manifests, and retained source containers.
- Store human-readable manifests, classifications, hashes, dependency graphs, and research notes in normal Git.
- Store large binary assets through Git LFS when added from a local clone.
- Keep generated exports deterministic where practical.
- Never discard unresolved Treyarch semantics merely because a generic preview format cannot represent them.
- Keep enough provenance that a future decoder can reproduce an export without re-discovering the original T6 relationship.

## Current world/map checkpoint

### Geometry

The generic world decoder/exporter supports all nine known T6 `MaterialWorldVertexFormat` layouts in synthetic regression coverage.

Retained retail byte proof is deliberately narrower. The current machine-readable census is:

`manifests/world/T6_WORLD_VERTEX_FORMAT_CENSUS_V1.json`

Nuketown currently retail-proves formats:

```text
0  TEX_1_NRM_1
1  TEX_2_NRM_1
2  TEX_2_NRM_2
3  TEX_3_NRM_1
6  TEX_4_NRM_1
```

Formats `4`, `5`, `7`, and `8` have source/formula + synthetic coverage but still require retained retail fixtures before they may be called retail-byte-proven. `tools/t6_world_format_target_scan_v1.py` exists specifically to find materials/maps that should exercise those variants.

### Layered/generated materials

Generated world materials such as:

```text
*22n_14(wpc/base:wpc/decal)
```

are no longer treated as opaque names.

The current source-closed reconstruction knows that:

- numeric tokens are component BSP material indices;
- `n` denotes the component's real-normal-map expectation;
- `$identitynormalmap` is not treated as a real normal map;
- component names in parentheses preserve exact layer identities/order;
- generated texture tables concatenate component texture tables in layer order;
- layer count + real-normal count determines the layered world vertex format.

Nuketown retains a dedicated layered-material proof under:

`manifests/maps/mp_nuketown_2020/layered_material_fixture_proof_v1.json`

The exact layered pixel-shader/blend composition is **not** silently approximated into generic PBR. All exact dependencies remain preserved for a future Treyarch-aware Blender/wgpu shader.

### DDS / texture dependencies

`tools/t6_dds_texture_stage_v2.py` stages the currently source-closed DDS subset and determines BC5 normal reconstruction from exact Material semantics, including layered normal maps that are deliberately unbound in generic glTF.

`tools/t6_oat_material_manifest_v3.py` preserves exact T6 `GfxImage` identity separately from the exact OpenAssetTools disk filename. OAT's pinned image writer replaces `*` with `_` for the output filename; v3 also rejects non-injective filename aliases rather than silently merging distinct T6 assets.

`tools/t6_world_textured_gltf_export_v2.py` embeds every exact staged material dependency image into the GLB. Only independently safe standard-preview bindings are connected to generic glTF material slots. Non-core Treyarch dependencies remain embedded and indexed in `extras.T6` instead of being guessed away.

### Lightmaps

T6 `GfxWorld` owns an array of `GfxLightmapArray` entries, each containing separate primary and secondary `GfxImage` assets. Surfaces already carry `lightmapIndex`, and the world vertex pipeline already exports the dedicated lightmap UVs.

T6-native code-sampler identities are source-known:

```text
0x4  TEXTURE_SRC_CODE_LIGHTMAP_PRIMARY
     lightmapSamplerPrimary

0x5  TEXTURE_SRC_CODE_LIGHTMAP_SECONDARY
     lightmapSamplerSecondary
```

Current lightmap tools:

- `tools/t6_world_lightmap_manifest_v1.py` — original strict `surface -> lightmap index -> primary/secondary image` join.
- `tools/t6_world_lightmap_manifest_v2.py` — same exact T6 join plus exact OAT image disk-name mapping/collision rejection.
- `tools/test_t6_world_lightmap_manifest_v1.py` / `v2.py` — deterministic synthetic/negative regressions.
- `tools/t6_gfxworld_lightmap_oat_patch/` — pinned OpenAssetTools patch that emits the exact loaded T6 GfxWorld primary/secondary image-name catalog without inventing shader semantics.
- `tools/t6_world_lightmap_glb_embed_v2.py` — losslessly archives exact primary/secondary DDS bytes as untyped GLB bufferViews with SHA-256, T6 sampler identity and surface/UV provenance. It intentionally creates no generic glTF lightmap binding.
- `tools/test_t6_world_lightmap_glb_embed_v1.py` / `v2.py` — archival integrity, determinism, deduplication, corruption, missing-file and identity/disk-bijection regressions.

The next retail promotion is to run the retained GfxWorld dumper on a retail map (Nuketown first), archive its exact pair catalog, run the v4 pipeline, and independently verify the final GLB/raw DDS recovery.

Primary/secondary channel meaning and the exact T6 pixel-shader combine equation remain a separate proof boundary. Older IW/Treyarch-family formulas are not promoted as T6 truth.

### Retail lightmap shader provenance

Pinned stock OpenAssetTools already dumps T6 DX11 shader bytecode losslessly from `MaterialPixelShader::prog.loadDef.program` for exactly `programSize` bytes. Pixel shaders are emitted as:

```text
shader_bin/ps_<MaterialPixelShader.name>.cso
```

The accompanying OAT text dumps provide the exact chain:

```text
Material JSON
  -> techniqueSet
  -> techsets/<name>.techset
  -> techniques/<name>.tech
  -> per-pass pixelShader + sampler bindings
  -> shader_bin/ps_<name>.cso
```

`tools/t6_lightmap_shader_inventory_v1.py` walks that chain and selects only pixel-shader passes that explicitly reference `lightmapSamplerPrimary` and/or `lightmapSamplerSecondary`. It hashes the exact DXBC bytes and preserves material/techset/technique/pass provenance without interpreting shader instructions. `tools/test_t6_lightmap_shader_inventory_v1.py` covers the parser and fail-closed path.

The next shader-semantic step is DXBC instruction disassembly of those retail-selected shaders, followed by cross-technique validation of the observed primary/secondary sample swizzles and combine math.

## Strongest one-command world pipeline

Current production entry point:

```text
tools/t6_oat_world_textured_export_pipeline_v4.py
```

It promotes the strongest current stages into one deterministic path:

```text
raw GfxWorld sidecars
  -> audited normalized world
  -> geometry-only reference GLB

exact OAT Material JSONs
  -> ordinary + generated/layered material manifest v3
     (exact T6 image identity + exact OAT disk filename)

exact DDS assets
  -> semantic-aware DDS stage v2

normalized world + staged dependencies
  -> portable textured GLB v2
     (all exact material dependency images embedded)

optional exact GfxWorld lightmap catalog
  -> surface/lightmap primary+secondary dependency manifest v2
  -> exact raw primary/secondary DDS archive v2 inside final GLB
     (renderer-neutral; no guessed lightmap shader)
```

Example Windows invocation:

```bat
py tools\t6_oat_world_textured_export_pipeline_v4.py ^
  --map <map_name> ^
  --surfaces <gfxworld.surfaces.json> ^
  --vd0 <gfxworld.vd0.bin> ^
  --vd1 <gfxworld.vd1.bin> ^
  --indices <gfxworld.indices.bin> ^
  --materials <materials.json> ^
  --catalog <material_catalog.json> ^
  --prefix <prefix_walk.json> ^
  --asset-pointer-base <virtual_base> ^
  --oat-material-root <OAT_materials_directory> ^
  --dds-root <exact_OAT_DDS_directory> ^
  --lightmap-catalog <optional_gfxworld_lightmap_catalog.json> ^
  --out-dir <output_directory> ^
  --write-gltf
```

If the lightmap catalog is provided, missing lightmap DDS files fail closed by default. `--allow-missing-lightmap-dds` exists only for an explicitly incomplete archival run and records missing identities rather than silently dropping them.

The geometry-only GLB remains beside the textured result so geometry can always be validated independently from renderer/material reconstruction.

## XModel / skinning / XAnim checkpoint

Rigid XModel rendering, skeleton reconstruction, inverse-bind validation, and a real retail animated Nuketown map object have been carried through standard glTF.

`tools/t6_xanim_skinned_gltf_export_v4.py` is the generalized rigid+blended skin exporter. Its skin validation covers native 1/2/3/4-influence rows and fails closed on unweighted vertices or invalid joint/weight data. The non-root XAnim translation rule used by the proven path is:

```text
glTF local translation = XModel bind-local translation + XAnim translation delta
```

A retained `german_shepherd` 56-bone fixture census is recorded in:

`manifests/xmodels/german_shepherd_skin_expectation_v1.json`

Its next proof step is intentionally explicit: regenerate the normalized mesh/skeleton from the exact retail owning fastfile, export bind-pose skin through v4, retain hashes, and independently load/validate it before promoting the fixture further.

## Weapon-definition checkpoint

Stage 18C classifies the 172 top-level `common_mp` weapon definitions into player weapon families, equipment, alternate/attachment variants, and scorestreak/internal/helper definitions. Patch-zone duplicate names are tracked as overrides rather than additional weapons.

Weapon work remains one subsystem inside the larger T6 ledger; complete first-person weapon/viewhand/XAnim/material/FX/audio linkage is not yet declared T6-closed.

## Repository layout

```text
assets/                  decoded/exported assets; large binaries via Git LFS
manifests/               retained proofs, censuses, hashes, dependency graphs
research/                proof standard, closure ledger, reverse-engineering notes
tools/                   collectors, decoders, exporters, regressions, OAT patches
source-containers/       optional original FF/IPAK/SABS/SABL/IWD sources via Git LFS
```

## Large-file policy

Do not commit large `.ff`, `.ipak`, `.bin`, model, texture, audio, archive, or other binary payloads to ordinary Git history. `.gitattributes` defines the intended Git LFS classes. A local clone with Git LFS installed is required to upload large archival payloads.

## Completion criterion

This repository is not “done” when one map looks correct. The project is complete only when the closure ledger reaches the declared T6 archival/reconstruction scope with retained retail fixtures, cross-fixture validation, production integration, and independent-consumer validation for every material format/asset class that matters.

This repository is intentionally separate from `bo2-pc-server-decompile`.