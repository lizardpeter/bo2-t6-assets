# Black Ops II (T6) Asset Archive

Private archival/research repository for the ongoing Call of Duty: Black Ops II (T6) asset extraction and reconstruction project.

## Goals

- Preserve exact source provenance (`common_mp` -> `common_patch_mp` -> `patch_mp`).
- Keep extracted/decoded assets separate from reconstruction tooling and manifests.
- Store human-readable manifests, classifications, hashes, and scripts in normal Git.
- Store large binary assets through Git LFS when added from a local clone.
- Never treat patch-layer counts as additive when they override base XAssets.
- Preserve proof boundaries: inferred identities are labeled as such until exact serialized definitions are recovered.

## Current verified checkpoint

Stage 18C classifies all 172 top-level `common_mp` weapon definitions:

- 39 standard player weapon families
- 15 selectable equipment definitions
- 47 alternate/attachment variants
- 71 scorestreak/internal/helper definitions

`common_patch_mp` contains 81 weapon definitions, all of which are names already present in `common_mp`; it is therefore an override/update layer for those names rather than 81 additional guns.

The clean final multiplayer loadout catalog currently contains 40 weapon families (including the patch-era Peacekeeper) plus 15 equipment items = 55 player-facing rows.

## World/map export checkpoint

The source-closed world pipeline now has a deterministic geometry-only reference path and a conservative textured path.

Geometry path:

```text
GfxWorld sidecars
  -> serialized vd0/vd1 byte audit
  -> exact material-pointer resolution
  -> normalized shared world vertex groups
  -> glTF 2.0 / GLB
```

The generic world decoder/exporter handles all nine known T6 `MaterialWorldVertexFormat` layouts (0-8) in synthetic regression coverage. Retail byte proof remains deliberately narrower: formats already observed and byte-audited in retained retail fixtures are considered proven for those fixtures only; formula/regression coverage does not upgrade an unseen retail format to retail proof.

The textured path adds:

```text
material_texture_mapping.csv
  -> exact semantic material manifest
  -> exact sourceTexture TGA staging
  -> deterministic PNGs
  -> exact material-name join
  -> source-approved colorMap / normalMap glTF preview bindings
```

Non-core Treyarch semantics such as `specularMap`, packed `colorGloss` / `colorOpacity`, and layered/compositor materials are retained in `extras.T6.materialDependencyGraph` rather than silently translated into generic PBR channels. The untextured reference GLB is kept beside the textured GLB so geometry can always be compared independently from material reconstruction.

### One-command textured world export

From a Windows clone, after the required raw world sidecars and exact material/texture mapping have been produced:

```bat
py tools\t6_world_textured_export_pipeline_v1.py ^
  --map <map_name> ^
  --surfaces <gfxworld.surfaces.json> ^
  --vd0 <gfxworld.vd0.bin> ^
  --vd1 <gfxworld.vd1.bin> ^
  --indices <gfxworld.indices.bin> ^
  --materials <materials.json> ^
  --catalog <material_catalog.json> ^
  --prefix <prefix_walk.json> ^
  --asset-pointer-base <virtual_base> ^
  --material-texture-mapping <material_texture_mapping.csv> ^
  --texture-root <directory_with_exact_TGA_basenames> ^
  --out-dir <output_directory> ^
  --write-gltf
```

The command retains the audit proof, resolved surfaces, normalized world JSON, geometry-only GLB, material manifest, texture-stage manifest, staged PNGs, textured GLB, optional embedded `.gltf`, and SHA-256 pipeline manifests.

Current regressions for this layer:

```bat
py tools\test_t6_texture_stage_v1.py
py tools\test_t6_world_textured_gltf_export_v1.py
py tools\test_t6_world_textured_export_pipeline_v1.py
```

The all-format pipeline test intentionally exercises world vertex formats 0-8 synthetically. It validates serializer/tool integration; it is not a substitute for a retail byte fixture.

## Repository layout

```text
assets/                  # decoded/exported assets; large binaries via Git LFS
manifests/               # inventories, hashes, dependency graphs, classifications
tools/                   # collectors, decoders, verification scripts
source-containers/       # optional original FF/IPAK/etc. sources via Git LFS
research/                # notes and proof-boundary documentation
```

## Large-file policy

Do not commit large `.ff`, `.ipak`, `.bin`, model, texture, audio, archive, or other binary payloads to ordinary Git history. `.gitattributes` defines the intended Git LFS classes. A local clone with Git LFS installed is required to upload the binary archive itself.

This repository is intentionally separate from `bo2-pc-server-decompile`.