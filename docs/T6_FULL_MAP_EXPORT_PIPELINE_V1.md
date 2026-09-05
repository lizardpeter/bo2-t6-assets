# T6 Full Map Export Pipeline v1

This document records the reusable, fail-closed rules learned while reconstructing `mp_nuketown_2020` (Nuketown 2025). The goal is not a Nuketown-specific exporter. Every rule here is intended to apply to future BO2/T6 maps.

## Preservation contract

1. Preserve original `.ff`, `.ipak`, localization and shared-zone files byte-for-byte and record SHA-256 before deriving anything.
2. Never replace source assets with guessed substitutes when exact retail identities or payloads are unresolved.
3. Every canonical GLB checkpoint must pass a non-regression guard. New content may be added; already-proven geometry, materials, bindings, animation data and source metadata may not silently disappear.
4. Scene reorganization is allowed only when data remains preserved. Example: animation-support XModels may move out of the canonical scene into a preview/support scene without being deleted or modified.

## Full map assembly layers

A complete T6 map is not just one geometry class. The exporter must treat these as separate source layers and merge them deliberately:

1. **GfxWorld** — all serialized render surfaces, including exterior/vista world surfaces.
2. **Static XModel placements** — all serialized DPVS static placements, with exact origin/axis/scale and XModel identity.
3. **Reflection proxies** — preserve but do not render in the canonical scene when the retail-primary selection proof marks them as reflection-only duplicates.
4. **MapEnt / script_model / destructible placements** — gameplay-owned placed models such as Nuketown's parked cars.
5. **Animation-support / FX-animation models** — preserve mesh, skin, animation and transforms, but isolate preview/support geometry from the canonical scene when it obstructs authoring tools.
6. **Sky** — preserve the original retail cubemap and shader metadata. A Blender preview cube is a derived representation, not a replacement for the T6 camera-relative sky shader.
7. **Collision/gameplay data** — keep distinct from visible render geometry unless an explicit debug scene is requested.

## Coordinate and triangle contract

- Do not rotate or flip an entire map to compensate for face visibility.
- T6 world/XModel triangle winding must be validated against stored retail normals.
- When required for glTF front-face convention, convert `[a,b,c] -> [a,c,b]` at the index level.
- Preserve the source coordinate system in provenance metadata and apply one documented T6-to-glTF transform consistently.

## Materials and textures

1. Material identity comes from retail Material records / XModel surface slots / GfxWorld material references, never filename guessing.
2. Texture role resolution prefers the exact shader-role name (`Diffuse_Map`, `Normal_Map`, etc.) over broad semantic ordering when the latter is ambiguous.
3. Standard glTF preview bindings are only for source-closed roles.
4. Preserve every available OAT texture role losslessly, including secondary colors, detail normals, specular/packed maps and generated-layer inputs. Exact DDS bytes may be embedded as T6 metadata when glTF has no faithful core semantic.
5. Missing engine built-ins (`$black`, flat-normal identities, shadow-only identities, etc.) remain explicitly unresolved until source-closed; do not synthesize them silently.
6. Generated/layered Treyarch materials remain a separate shader-reconstruction stage. Preserve all exact inputs before attempting preview compositing.

## Animation contract

- Recover exact XAnim identities and source spans.
- Preserve bone tracks and delta/root-motion tracks separately.
- Do not add duplicate animated models on top of their static/gameplay counterparts in the canonical scene.
- Use dedicated animation preview scenes/states where necessary.
- Animation preview isolation must never alter the underlying mesh, skin, transform or keyframe data.

## Sky contract

For a retail T6 cubemap:

- retain the original DDS cubemap bytes losslessly;
- retain Material/TechniqueSet/constants/sampler metadata;
- decode six 2D faces only as a derived authoring preview;
- use an inward-facing preview cube for Blender if useful;
- mark the cube and face materials as preview-only;
- runtime/Tour should use the original cubemap semantics rather than treating the preview cube as canonical source data.

## Canonical-scene policy

A normal/full-map scene should contain visible retail map content and exclude authoring obstructions such as animation-support helper meshes. Those helpers remain roots of dedicated support/preview scenes so the asset data is still present.

The non-regression guard therefore distinguishes:

- **data loss**: previously proven nodes/material bindings disappear entirely — fail;
- **scene migration**: preserved nodes move to another scene for clean authoring — allowed when explicitly checkpointed;
- **canonical visibility regression**: helper/debug/preview objects re-enter the default scene — fail.

## Required checkpoint artifacts

Each promoted map build should emit:

- canonical GLB;
- source/integration proof with file hashes and counts;
- non-regression report;
- unresolved asset/material/texture list;
- scene-role census;
- optional visual QA render/contact sheet.

Future T6 maps should start from this contract instead of re-learning Nuketown-specific fixes.
