# T6 Universal Exporter Architecture v1

## Goal

Build one deterministic BO2/T6 exporter that can reconstruct **every retained map,
XModel, material, image, animation and scene dependency** from authoritative retail
containers without guessed substitutions.  Nuketown is a high-value fixture, not a
special-case production path.

This document is subordinate to `research/T6_PROOF_STANDARD.md` and
`manifests/T6_100_PERCENT_CLOSURE_V1.json`.  "Looks right" is never a replacement
for source closure, and a newer output may not silently discard an older proven
capability.

## Non-negotiable rules

1. **No map-name logic in production decoders/exporters.** Map/model names may occur
   in fixture manifests, source selection and output naming, never as decoding rules.
2. **Retail identity beats filename similarity.** Material, GfxImage, streamed-part,
   XModel and XAnim joins use exact retained identities/pointers/hashes and source
   precedence. Same-name fallback is not a production rule.
3. **Source precedence is one reusable subsystem.** Base/common/patch/map/DLC layers
   are resolved once and every XAsset class consumes the same winning-source graph.
4. **Decode once into canonical IR.** glTF, Blender and wgpu adapters consume the same
   normalized T6 asset graph; they do not independently reinterpret FastFiles.
5. **Unsupported semantics are preserved, not approximated silently.** Exact T6
   render state, layered dependencies, lightmaps, probes and shader metadata remain
   in the IR/scene contract until a faithful playback adapter exists.
6. **Every export is deterministic and self-auditing.** Inputs, container hashes,
   asset identities, decoder revisions, dependency owners and unresolved fields are
   recorded in a machine-readable export state.
7. **Regression is a release failure.** A candidate must satisfy the fixture's
   retained non-regression contract before it may replace the previous accepted
   artifact.

## Production pipeline

```text
retail containers
  FF / IPAK / IWD / SABS / SABL
          |
          v
[1] container + zone catalog
    - hash-pinned source bytes
    - XAsset inventory
    - base/common/patch/map/DLC precedence
          |
          v
[2] canonical T6 asset graph / IR
    - GfxWorld geometry + surface identities
    - XModel geometry/LODs/skin/skeleton
    - XAnim tracks/runtime binding metadata
    - Material identity + texture table + technique/render state
    - GfxImage identity + sampler + streamed-part hashes
    - lightmaps/reflection probes/environment
    - placements/dynamic objects/FX/collision/gameplay metadata
          |
          v
[3] dependency resolver
    - exact material owner
    - exact image owner
    - exact IPAK (nameHash,dataHash) payload
    - override provenance
    - unresolved reason, never guessed substitute
          |
          v
[4] renderer-neutral scene contract
    - normalized geometry
    - exact transforms
    - material dependency graph
    - render state
    - complete image payload archive
    - lightmap/probe/environment dependencies
          |
          +-------------------+------------------+
          v                   v                  v
     archival GLB       Blender adapter       wgpu adapter
     + T6 extras        faithful nodes        faithful runtime
```

## Existing generic components to keep

The repository already contains substantial reusable infrastructure.  The universal
exporter should compose/refactor these rather than replace them with fixture scripts:

- `tools/t6_zone_core.py`
- `tools/t6_world_export_pipeline_v1.py`
- `tools/t6_oat_world_textured_export_pipeline_v4.py` and later generic revisions
- `tools/t6_world_mesh_normalize_v1.py`
- `tools/t6_world_gltf_export_v1.py`
- `tools/t6_oat_material_manifest_v3.py` and later generic revisions
- `tools/t6_dds_texture_stage_v2.py`
- `tools/t6_xmodel_mesh_normalize_v1.py`
- `tools/t6_xanim_normalize_v1.py`
- `tools/t6_xanim_skinned_gltf_export_v4.py`
- world vertex-format registry / layered-material parsers / lightmap archival tools

Nuketown-specific tools remain useful as retained fixtures and forensic probes, but
new production behavior should migrate into reusable modules and be validated back
against Nuketown plus additional maps/models.

## Canonical export-state contract

Every production artifact should eventually emit one normalized state document with
at least:

```text
format: t6-export-state-v1
asset:
  type
  name
  source zone/container
parents:
  prior proven state ids/hashes
geometry:
  exact counts + structural fingerprint
materials:
  exact material identity set
  resolved render-state set
images:
  exact GfxImage identity set
  resolved payload identity set
  unresolved identity/reason set
placements:
  exact model identity + transform set
animations:
  exact XAnim identity + decoded/runtime-binding state
capabilities:
  proof level / closed-open state per semantic family
outputs:
  deterministic hashes
```

The state is **monotonic evidence**, not a convenient summary.  A downstream stage
must name the states it inherits.  Rebuilding from an older/raw source while omitting
a stronger proven parent is a lineage failure even if the new GLB parses correctly.

## Non-regression system

`tools/t6_export_nonregression_gate_v1.py` is the first generic release guard.
Fixture-specific expectations live in contracts such as:

`manifests/maps/mp_nuketown_2020/T6_NUKETOWN_EXPORT_NONREGRESSION_CONTRACT_V1.json`

The current v1 gate checks observable GLB invariants/floors.  The next revision should
also compare normalized export-state identity sets and parent lineage so that counts
alone can never hide a dropped/replaced exact binding.

Required release checks for a mature exporter:

- exact geometry/placement fingerprint retained;
- all previously proven material-slot identities retained;
- all previously proven color/normal/dependency image identities retained;
- no new generic/placeholder primitive bindings;
- all previously proven render-state identities retained;
- unresolved set may shrink; it may grow only when declared source scope grows;
- deterministic rebuild equality;
- independent GLB consumer validation;
- Blender/wgpu adapter validation for renderer semantics in scope.

## Migration away from one-off Nuketown repair chains

### A. Generalize image ownership and IPAK resolution

Replace map/base-specific extraction scripts with one resolver that accepts the source
precedence graph and resolves `(GfxImage.hash, streamedParts[n].hash)` against every
eligible IPAK.  Record exact owner and rejected same-name variants.

### B. Generalize Material -> image binding

One Material decoder/resolver must serve GfxWorld and XModels. World/static should not
have separate texture-binding implementations. Semantic 2/5/8/10 handling, sampler
state, sRGB/linear interpretation and packed/runtime images belong here.

### C. Generalize XModel export

XModel geometry, material slots, LODs, skinning and animation binding are exported
once per XModel identity. Map scene composition instances those canonical model assets;
it does not rebuild a second static-material universe.

### D. Generalize scene composition

GfxWorld groups and placed XModels are top-level scene instances unless retail data
proves hierarchy. No artificial mega-root is needed for GLB correctness. Dynamic,
animated, destructible and FX placements join through the same scene graph.

### E. Generalize T6 render playback

Do not translate only what generic glTF happens to support. Archive exact T6 state,
then make Blender/wgpu adapters consume it: alpha test/blend/cull/depth/write masks,
polygon offset, stencil, emissive/unlit paths, layered/special techniques, lightmaps,
probes, fog/exposure/sky.

## Fixture matrix, not one-map confidence

A universal claim requires a retained corpus that intentionally exercises different
branches:

- all nine `MaterialWorldVertexFormat` values;
- ordinary + 2/3/4-layer world materials;
- alpha mask/blend, double-sided, emissive/unlit and decal families;
- BC1/BC2/BC3/BC5 plus every other retail-observed image format;
- cubemap/array/mip behavior;
- rigid and 1/2/3/4-influence XModels;
- static and animated placements;
- every XAnim delta-union/runtime-binding branch;
- primary-only, secondary-only and dual-role lightmaps;
- reflection/environment/fog/sky/light variants;
- MP, Zombies, base, patch and DLC override cases.

Nuketown remains one regression fixture in that matrix.

## Immediate engineering order

1. **Stop regressions first:** enforce non-regression on every user-facing artifact.
2. **Create normalized export-state + lineage manifests.** This removes reliance on
   stage-specific counts and prevents bypassing stronger ancestors.
3. **Extract generic IPAK/image resolver from the successful Nuketown map/base code.**
4. **Use the same Material/image resolver for world and XModel materials.**
5. **Make the scene composer instance canonical XModels and retain flat retail-derived
   placement structure.**
6. **Move v10/v11/v12 material-slot/render-state logic into generic Material/XModel
   stages and validate on multiple fixtures.**
7. **Close remaining shader/lightmap/environment gates and run the full retained corpus.**

## Definition of done

The exporter is "perfect" for the declared T6 scope only when every gate in
`manifests/T6_100_PERCENT_CLOSURE_V1.json` is closed, the entire hash-pinned target
corpus passes the same production path, and no map/model needs an identity guess or a
fixture-only repair to render faithfully.
