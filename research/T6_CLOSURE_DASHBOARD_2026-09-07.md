# T6 whole-project closure dashboard — 2026-09-07

This dashboard answers a different question from map-export readiness:

> How close is the **entire BO2/T6 asset reversal** to the repository's strict P8 completion criterion?

It is deliberately conservative. It includes systems that are not needed merely to make Nuketown or another map look good: FX, audio, dynamic GameWorld state, weapons/viewhands, characters/AI/vehicles, UI/scripts/gameplay definitions, and every remaining XAsset class.

The percentages below are **engineering completion ranges, not proof-level arithmetic**. P0–P8 remains the authoritative proof language. A subsystem can have a high structural/extraction percentage while still be materially below P8 because cross-fixture proof, production integration, runtime semantics, or independent validation is missing.

## Current headline

| Scope | Current estimate | Meaning |
|---|---:|---|
| Source/container discovery + structural extraction foundation | **~90–95%** | The hard foundational problem of finding, validating, expanding, inventorying, and source-pinning retail content is largely solved. |
| Generic retail map extraction | **~90–95%** | Existing 2026-09-07 all-map readiness checkpoint; rare map/DLC families and ownership tails remain. |
| Generic fail-visible map/Blender reconstruction | **~85–90%** | Exact shader/DAG machinery is strong; runtime/global inputs and special families remain. |
| Broad useful normalized asset extraction across T6 | **~75–85%** | Most major content families now have working paths, but not every variant/class is yet production-closed. |
| Strict whole-project **P8** closure | **~55–65%** | Every relevant T6 class and semantic relationship must reach retail proof, cross-fixture closure, production integration, and independent validation. |

A useful single answer to “how close are we to fully reversed?” is therefore:

**roughly 60% to the strict all-of-T6/P8 finish, while the reusable extraction foundation is already around 90% complete.**

This is not a contradiction: the remaining work is the wide semantic/runtime long tail, not another basic FastFile/mesh/animation breakthrough.

## Why the foundation score is high

Since the older 2026-09-01 ledger audit, major reusable infrastructure has materially advanced:

- complete ZIP64-aware public retail archive inventory;
- complete **215/215 FastFile** CRC-verified, SHA-pinned, decrypted/inflated census;
- exact source-derived GfxWorld/placement/material workflows across multiple MP and Zombies maps;
- all known world vertex-format family implementation, with additional retained cross-map byte fixtures beyond the original Nuketown subset;
- native Material → TechniqueSet → Technique → shader dependency recovery;
- exact DXBC/RDEF resource ABI tooling;
- source-pinned DXBC disassembly;
- generic shader IR/symbolic-DAG lowering and real-Blender node compilation;
- exact generated-material final-output compilation for the retained Nuketown corpus;
- exact lprobe lit/glass/reflection/fog/HDR arithmetic work;
- exact XModel tangent transport;
- generalized rigid + blended skinning and XAnim tooling;
- substantial character/material/animation recovery work;
- complete startup `shadowoverlay` family closure across SP/MP/Zombies plus exact pixel-shader arithmetic;
- fail-closed provenance-aware duplicate Technique/TechniqueSet handling rather than guessed zone precedence.

The 2026-09-07 map-readiness checkpoint already estimates generic retail map extraction at **90–95%**, generic fail-visible Blender export at **82–90%**, and per-map retail-render parity at **75–85%**. Those figures are map/renderer scoped and therefore must not be reused as the whole-project P8 percentage.

## Whole-project subsystem assessment

### 1. Source containers / FastFiles / provenance — advanced

Strong now:

- source archive traversal and ZIP64 range access;
- exact container metadata and CRC verification;
- SHA-pinned FastFile inputs;
- source-closed T6 decrypt/inflate;
- complete 215-FastFile census for the referenced retail archive;
- broad XAsset inventory infrastructure;
- exact physical-root provenance retained in newer native dependency tools.

Remaining:

- source-close runtime duplicate-XAsset winner semantics instead of merely preserving all divergent copies;
- generalize winner provenance to every XAsset type and every base/patch/DLC family;
- ensure every non-FastFile source container in the final corpus has equivalent archival/provenance coverage.

### 2. GfxWorld / static map geometry — very advanced

Strong now:

- reusable geometry extraction;
- surface/material pointer relationships;
- shared vertex groups;
- primary/secondary vertex streams;
- native UV families and lightmap UV transport;
- exact placement and large static-model reconstruction;
- multiple retained MP/Zombies structural canaries;
- real output validation.

Remaining:

- exhaustive campaign/DLC map corpus closure;
- any genuinely new rare world/layout variants;
- P5/P7/P8 promotion across the entire map set rather than selected fixtures.

### 3. Materials / TechniqueSets / Techniques / shaders — advanced, still a major semantic tail

Strong now:

- exact native dependency chains;
- exact state serialization;
- exact shader bytes and hashes;
- DXBC reflection/resource ABI;
- symbolic shader DAGs;
- generated shader compilation;
- real Blender validation for solved families;
- cross-map resource ABI evidence over thousands of shaders;
- fail-closed duplicate parent/child provenance handling.

Remaining:

- exact runtime winner rule for divergent duplicate assets;
- finite ordinary/special shader-family tail;
- water, distortion, TV/raw-normal/burning/shadow and other special families where not individually closed;
- exact sampler/filter/mipmap behavior where Blender differs from D3D11;
- framebuffer/destination blending and other state Blender cannot directly express;
- complete runtime/global code-resource providers or exact baking equivalents.

### 4. Images / textures — strong but not universal

Strong now:

- exact GfxImage identity provenance;
- IPAK location work;
- major BC/RGBA families;
- normal-map semantics;
- embedded exact dependencies in portable outputs.

Remaining:

- every T6 image format;
- complete mip-chain semantics;
- arrays/cubemaps/reflection probes;
- exact sRGB/linear behavior everywhere;
- remaining platform/storage edge cases and archival representation.

### 5. Lightmaps / reflection / lighting / renderer globals — medium/advanced, high-value remaining area

Strong now:

- surface lightmap indices and UVs;
- primary/secondary image ownership structure;
- cross-map DXBC resource bindings;
- reflectionProbeSampler ABI;
- substantial lightprobe/lprobe shader arithmetic;
- generated Blender replay infrastructure.

Remaining:

- universal exact lightmap catalog/image closure;
- complete primary/secondary channel equation families;
- reflection cubemap assignment/LOD behavior;
- model light-grid / SH runtime values and object bindings;
- sun/primary/dynamic light semantics;
- fog/HDR/global constants across all passes;
- renderer-global producer/consumer paths such as the remaining `shadowoverlay` runtime layer.

### 6. XModels / skeletons / skinning — advanced

Strong now:

- rigid meshes;
- LODs;
- skeleton reconstruction;
- inverse-bind validation;
- native rigid and 1/2/3/4-influence skinning;
- exact material dependency work on real characters/props;
- real Blender/glTF validation on retained fixtures.

Remaining:

- exhaustive special model classes and pathological hierarchy cases;
- whole-corpus cross-fixture closure;
- cloth/physics/destruction-linked model edge cases where applicable.

### 7. XAnim — advanced but not P8

Strong now:

- real retail XAnim extraction;
- exact frame counts/rates on retained character work;
- non-root translation semantics on proven fixtures;
- local quaternion handling;
- standard glTF animation export;
- multiple real animation fixtures.

Remaining:

- every compression/variant branch;
- root-translation edge cases;
- deltaPart binding semantics;
- notetracks and secondary animation metadata;
- exhaustive character/viewhand/AI/map-dynamic validation.

### 8. Collision / clipMap — strong partial/cross-fixture

Strong now:

- extensive clipMap decoding;
- PVS and static-model constraints;
- dynamic-entity collision work;
- normalized outputs on retained maps.

Remaining:

- every brush/tree/partition/primitive variant;
- gameplay metadata;
- broad runtime-query parity and P8 corpus validation.

### 9. MapEnts / AddonMapEnts / GameWorld / dynamic map behavior — medium

Strong now:

- entity data preservation and substantial decoding;
- scene metadata/empties on selected paths;
- static asset linkage much farther than the original ledger state.

Remaining:

- full target/parent/script graphs;
- movers, doors, destructibles and triggers;
- AddonMapEnts override behavior;
- complete GameWorld dynamic structures;
- runtime state machines and animation/FX linkage.

### 10. Weapons / attachments / camos / tracers / viewhands — medium

Strong now:

- broad MP definition inventory/classification;
- player weapons separated from equipment, alternate variants and internal/helper assets;
- substantial model/material/animation infrastructure is reusable.

Remaining:

- complete first-person viewmodel/viewhand linkage;
- attachment/camo/tracer semantics;
- weapon FX/audio linkage;
- all animation/state families and cross-mode variants;
- P7/P8 representative validation.

### 11. Characters / AI / animals / vehicles / props — medium/advanced

Strong now:

- real faction/character source relationships;
- exact blended meshes/skeletons;
- multiple exact character animations;
- exact texture payload recovery;
- native Material/TechniqueSet/shader investigation;
- reusable exporter and Blender validation infrastructure.

Remaining:

- exhaustive faction/AI/animal/vehicle corpus;
- complete body/head/viewhand/accessory semantic grouping;
- facial/special animation systems where present;
- runtime character state/linkage and physics/destruction edges.

### 12. FX — early/medium, one of the largest remaining tails

Strong now:

- FX assets are discoverable/inventoried and their referenced Material/model/image infrastructure is increasingly reusable.

Remaining:

- complete element graph semantics;
- sprites, models, beams/trails, decals and lights;
- timing/randomization;
- spawn transforms;
- physics/collision interaction;
- runtime attachment/entity linkage;
- faithful Blender/wgpu/runtime representation.

### 13. Audio — early/medium, one of the largest remaining tails

Strong now:

- SABS/SABL preservation and general source-container handling are in scope.

Remaining:

- bank/index structures universally;
- codec extraction for all variants;
- alias/event semantics;
- spatial/volume/pitch/randomization behavior;
- dialogue/music categories;
- weapon/FX/entity linkage;
- patch/DLC precedence and full corpus validation.

### 14. UI / HKS / scripts / gameplay definitions — medium/advanced but broad

Strong now:

- retail HKS/Treyarch Lua structural decoding is highly developed;
- HUD geometry has direct retail HKS/native-engine provenance and independent fixture validation;
- RawFiles, string tables, DDL and many gameplay data classes are already discoverable.

Remaining:

- full high-level HKS source semantics rather than structural bytecode decode alone;
- every menu/UI behavior;
- script/gameplay relation closure;
- localization/fonts and all remaining RawFile/data variants;
- runtime callbacks/state and P8 cross-fixture validation.

### 15. Remaining XAsset classes / long tail — still material

The complete T6 asset list includes classes that have not yet received the same dedicated P0–P8 matrix as maps, XModels, XAnim, Materials and shaders. “Not currently needed by the exporter” is not completion.

This tail is one reason a strict whole-project estimate must stay well below the map-export percentage.

## Remaining risk is now mostly breadth, not one foundational blocker

The most important project-level change is qualitative:

Earlier work still depended on solving major unknown container/layout/mesh/animation/shader primitives. Today, many of those primitives are reusable and automated. New maps, models and materials increasingly feed existing pipelines and expose a bounded new-family tail rather than forcing a new extractor.

The path from roughly 60% P8 to 100% is therefore expected to be dominated by:

1. exhaustive corpus runs;
2. rare XAsset/layout variants;
3. runtime/global renderer inputs;
4. dynamic entity/GameWorld semantics;
5. FX;
6. audio;
7. first-person weapon/viewhand linkage;
8. remaining character/vehicle/special-model families;
9. all UI/gameplay/remaining XAsset classes;
10. systematic P5/P7/P8 promotion and independent validation.

## Shadowoverlay local status

The `shadowoverlay` branch is much closer than the whole project:

**~90–95% closed for that specific dependency/render-shader path.**

Already authoritative:

- all three serialized startup owners (SP/MP/ZM);
- exact Material;
- exact TechniqueSet;
- exact Technique;
- exact shader bytecode;
- exact RDEF resource layout;
- exact pixel arithmetic.

Still open:

- T6-native renderer-global/equivalent Material slot;
- T6 draw/consumer path;
- exact runtime image supplied through `feedbackSampler`;
- exact T6 producer and values for `filterTap[0]`;
- render-target/scheduling relationship.

The required historical retail MP executable identity is known and SHA-pinned, but its binary bytes are not currently retrievable from the public full-game ZIP, Google Drive, or the indexed File Library. The branch therefore remains correctly fail-closed at the runtime boundary rather than importing T5 behavior as T6 fact.

## Dashboard update rule

Future percentage updates should be tied to actual closure events. Examples that justify movement:

- an entire XAsset family reaches P5/P6/P7;
- a complete map/DLC corpus introduces no new structural family;
- a runtime global-resource provider is source-closed and integrated;
- FX/audio gains a production pipeline rather than only an inventory;
- every remaining asset class has an explicit matrix and no unknown serialized fields for declared scope.

Small one-off fixture wins should update that subsystem's proof state but should not move the whole-project percentage by several points.
