# T6 Non-Map Extraction Track

**Branch:** `reversal/nonmap-assets`  
**Started:** 2026-09-05  
**Goal:** eventually extract every Black Ops II / T6 asset class without guessed data, silent substitution, or progress that exists only in a chat transcript.

This track is intentionally separate from the world/map reconstruction lane. It may consume the same source containers and proof standards, but it should not make map-specific assumptions part of general model/animation/material extraction.

## Permanent rules

1. **Retail bytes are authoritative.** Every promoted asset retains container/zone identity and source hashes where available.
2. **Fail closed.** Unsupported pointer ownership, compression, material semantics, animation branches, or asset classes become explicit blockers.
3. **No fake fallback assets.** Missing textures, skeletons, animations, sounds, FX, etc. are not replaced with plausible substitutes.
4. **Reuse exact upstream work where it is already stronger.** Pinned OpenAssetTools dumpers are preferred for supported T6 classes; custom reversal work focuses on unsupported or incomplete classes.
5. **Chat state is never the only state.** Every meaningful improvement is committed, manifested, or written into the proof ledger.
6. **Keep native and exchange forms separate.** Lossless normalized sidecars remain the archival representation; glTF/GLB/DDS/WAV/etc. are consumers, not replacements for native semantics.

## Exact T6 XAsset enum baseline

Pinned OpenAssetTools `T6.h` at commit `7d027e8f89118196713e955b0e11f8404149c54d` confirms the full T6 enum used by `tools/t6_raw_xasset_inventory.py`, including the otherwise poorly supported slots:

- `AITYPE`
- `MPTYPE`
- `MPBODY`
- `MPHEAD`
- `CHARACTER`
- `XMODELALIAS`

This is important: these are real enum identities, not a local indexing mistake. However, the same pinned OAT T6 `ContentLoaderT6.cpp` has **no loader cases** for those six types and falls through to unsupported-asset handling if one is encountered. OAT's typed `XAssetHeader`/asset aliases also do not expose them.

Therefore the project must distinguish:

- **enum-defined** — the engine asset ID is real;
- **observed-in-retail-zone** — the asset type actually appears in a retained zone inventory;
- **struct/serialization-known** — we can walk it exactly;
- **export-usable** — a deterministic standalone representation exists.

Do not infer that an enum-defined slot is populated merely because the enum exists.

## Current strongest model/animation path

The repository already has substantial source-backed work:

- `tools/t6_xmodel_mesh_normalize_v1.py`
  - native 32-byte packed vertices;
  - rigid vertices;
  - native 1/2/3/4-influence `vertsBlend` buckets;
  - triangles and LOD spans;
  - strict unsupported-branch rejection.
- `tools/t6_xmodel_skeleton_normalize_v2.py`
  - ScriptString bone names;
  - hierarchy and bind transforms;
  - packed VIRTUAL reusable-owner resolution by allocation replay rather than name guessing.
- `tools/t6_xanim_normalize_v1.py` and the retained XAnim proof chain.
- `tools/t6_xanim_skinned_gltf_export_v7.py`
  - root ordinary animated translation = decoded XAnim translation;
  - non-root ordinary animated translation = XModel bind-local translation + XAnim delta;
  - dedicated native `deltaPart` root-motion path;
  - strict no-fabricated-endpoint policy.

A retained `german_shepherd` fixture already proves a materially blended 56-bone retail XModel family. The remaining task is not to reinvent skinning; it is to make model discovery, dependency linkage, animation families, materials/images, and semantic character ownership automatic across the retail corpus.

## New production wrapper

`tools/t6_character_bundle_pipeline_v1.py` is the first non-map orchestration layer.

Given an exact retail XModel record and optional normalized XAnims it emits:

1. normalized mesh JSON;
2. normalized reusable-owner-aware skeleton JSON;
3. bind-pose glTF;
4. one animated glTF per supplied XAnim;
5. a SHA-256-pinned `t6-character-bundle-v1` manifest tying the outputs to the expanded retail source;
6. optional exact material/image dependency sidecar references without rewriting or guessing them.

It intentionally fails when any underlying proof-backed decoder rejects the fixture.

## Coverage accounting

`tools/t6_nonmap_asset_coverage_v1.py` consumes raw zone inventories and keeps every known T6 XAsset type explicit.

Status meanings:

- `usable` — this repository has a retained production-oriented path;
- `oat-dumpable` — pinned OAT can dump the class, but this repository still needs hash-pinned retention/regression before promotion;
- `partial` — some exact work exists, but the standalone asset is not closed;
- `inventory-only` — the enum identity can be counted but no standalone decoder is retained here;
- `open` — no meaningful extraction path yet;
- `handled-by-map-track` — deliberately owned by the parallel map/world lane.

The report separately lists OAT-dumpable classes awaiting local promotion so we do not waste reversal time rebuilding a working upstream dumper.

## Pinned OAT-first opportunities

At the pinned OAT revision, useful T6 dump coverage includes model/animation/material/image plus substantial non-map data such as:

- physics presets and constraints;
- technique sets/shader bytecode;
- sound banks;
- fonts/font icons;
- localization;
- weapon variants, attachments, unique attachments, and camos;
- sound-driver globals;
- raw files and string tables;
- leaderboards/key-value pairs;
- vehicles;
- tracers;
- ZBarrier definitions.

Script parse trees are binary/partial, and QDB/Slug are retained through raw-file-style output. Unsupported OAT classes remain direct reversal candidates rather than being silently ignored.

## Immediate non-map queue

1. **Corpus census first.** Run raw XAsset inventories over `common`, MP common/patch, representative MP zones, Zombies common/zones, and SP zones. Establish whether the six enum-defined AI/MP character slots occur in retail fastfiles at all.
2. **Character-family discovery.** Build an XModel/XAnim identity census by zone and naming family; locate player bodies, heads, viewhands, first-person weapons, third-person weapons, AI, animals, and vehicles without relying solely on filename heuristics.
3. **Dependency graph.** Connect XModel -> materials -> images and XAnim -> bone/rig compatibility in a lossless manifest so a character bundle can become self-contained.
4. **Promote one human fixture.** Alongside `german_shepherd`, retain a materially different human/player model with textures and several real animations as the P5-style character benchmark.
5. **Viewhands + weapon bundle.** Resolve a complete first-person rig, weapon model, attachments, animation set, materials/images, weapon definition, FX references, and audio references.
6. **OAT dump promotion.** Wrap supported OAT classes in deterministic source/output manifests and regressions instead of rewriting their parsers.
7. **Direct unsupported classes.** Prioritize observed classes only. Likely candidates include SoundPatch, FX/ImpactFX, SkinnedVerts, footstep tables, DDL/XGlobals, UI/menu data, and any actually observed AI/MP character slots.
8. **Audio.** Keep SABS/SABL bank preservation, alias/event metadata, codecs, patch precedence, spatialization, and randomization as separate proof gates.
9. **FX.** Preserve full element graphs and timing/material/model/audio dependencies before attempting generic-engine playback.
10. **Whole-game closure.** Feed this track's results back into the canonical proof ledger and 100% closure manifest; no subsystem is declared complete merely because maps render.

## Checkpoint discipline

Every future non-map checkpoint should contain, where applicable:

- source container/zone name and hash;
- XAsset type/index/internal identity;
- raw source span/hash or exact OAT provenance;
- decoder/exporter revision;
- normalized output hash;
- dependency identities and source layers;
- explicit unsupported fields/branches;
- independent consumer validation for exchange formats.

That makes this lane resumable from Git alone even if no previous chat context is available.
