# T6 Lightmap / World Pipeline v4 Checkpoint — 2026-09-01

This checkpoint exists so the current lightmap/world-export state can be reconstructed without conversation history. It follows `research/T6_PROOF_STANDARD.md`; implementation, regression, retail-byte proof, production integration, and renderer-semantic closure are tracked separately.

## Scope

Current goal: preserve and export T6 GfxWorld lightmap dependencies losslessly while refusing to invent the still-unknown primary/secondary pixel-shader composition.

## Permanent commits in this stage

| Commit | Purpose |
|---|---|
| `5e08bea` | lossless raw-DDS lightmap GLB archival embed v1 |
| `6630f05` | v1 archival regression added |
| `dcd0b0a` | corrected split-identity negative fixture |
| `1946ca7` | hardened lightmap GLB archive v2: identity/disk bijection + unique missing accounting |
| `1a3e53d` | archive v2 regression |
| `e81eaac` | production OAT world textured pipeline v4 |
| `d15e1aa` | pipeline v4 orchestration regression |

Earlier prerequisites remain authoritative:

- `1c6f8ae`: exact OAT GfxImage disk-name rule helper (`*` -> `_` only for output filename).
- `4fcf667` + `9f3fe03`: material manifest v3 exact asset/disk mapping + collision rejection/regression.
- `3215ded` + `dd322bf`: lightmap manifest v2 exact asset/disk mapping + collision rejection/regression.
- `a361065`, `96b5cee`, `c00b43d`: T6-native primary/secondary code-sampler contract + regression.
- `21cdb07`, `15c75c3`, `57d0221`: minimal OAT GfxWorld lightmap catalog patch and reproducible integration instructions.

## What v1 established

`tools/t6_world_lightmap_glb_embed_v1.py` appends the exact source DDS payload for each lightmap GfxImage to the existing glTF binary buffer as a four-byte-aligned, untyped bufferView.

For each dependency it archives:

- exact T6 `GfxImage.name` identity;
- exact OAT-emitted disk basename;
- primary/secondary role;
- T6 code texture source;
- T6 sampler accessor;
- lightmap index;
- surface/lightmap UV binding graph;
- payload byte count;
- SHA-256;
- GLB bufferView index.

It deliberately creates **none** of the following:

- a core glTF `image` for the lightmap DDS;
- a core glTF `texture` for the lightmap DDS;
- a material/PBR lightmap binding;
- an assumed RGB/A interpretation;
- an assumed primary/secondary combine equation.

This means the GLB can carry the exact retail payloads before the T6 renderer semantics are solved.

## Regression edge case found during validation

The first v1 regression exposed an important distinction between two different provenance failures.

A test intended to prove:

```text
same T6 GfxImage identity -> two different extracted filenames
```

accidentally reused a filename already owned by a different image identity. The earlier inverse collision check therefore fired first. The fixture was corrected in `dcd0b0a` to use a genuinely distinct alternate filename.

While examining that case, a real v1 implementation edge case was found:

1. with `allow_missing=True`, a shared missing GfxImage could be recorded once per dependency use rather than once per unique asset identity;
2. a missing GfxImage mapped to two different basenames could evade the runtime `embedded_by_asset` comparison because neither file had been embedded.

The historical v1 implementation was retained. The fix was promoted as v2 rather than rewriting the proof checkpoint.

## Hardened archive v2

`tools/t6_world_lightmap_glb_embed_v2.py` adds a pre-I/O bijection requirement:

```text
T6 GfxImage identity <-> OAT disk basename
```

Within one archive:

- one T6 GfxImage identity may map to exactly one disk basename;
- one disk basename may belong to exactly one T6 GfxImage identity.

This catches both:

```text
asset A -> file X
asset A -> file Y
```

and:

```text
asset A -> file X
asset B -> file X
```

before file existence can affect the result.

Missing dependencies are deduplicated by exact GfxImage identity. Archive stats now include:

```text
embeddedGfxImageCount
missingGfxImageCount
accountedGfxImageCount = embedded + missing
uniqueGfxImageCount
```

and validation requires:

```text
accountedGfxImageCount == uniqueGfxImageCount
```

with no identity simultaneously marked embedded and missing.

## v2 regression / local algorithm exercise

`tools/test_t6_world_lightmap_glb_embed_v2.py` covers the hardened semantics.

The same committed core algorithm was additionally exercised locally with a synthetic fixture containing four dependency uses but only three unique GfxImage identities:

```text
all files absent:
  dependency uses       = 4
  unique GfxImages      = 3
  embedded GfxImages    = 0
  missing GfxImages     = 3
  accounted GfxImages   = 3

shared primary present:
  unique GfxImages      = 3
  embedded GfxImages    = 1
  missing GfxImages     = 2
  accounted GfxImages   = 3
```

A split identity correctly fails before I/O:

```text
T6 GfxImage '*shared_primary' maps to multiple disk sources
```

Conservative proof statement: v2 is deterministic-regression-covered / synthetic P3 logic. This is **not** a retail lightmap payload proof.

## Production pipeline v4

`tools/t6_oat_world_textured_export_pipeline_v4.py` promotes the current strongest chain:

```text
raw GfxWorld sidecars
  -> audited normalized world
  -> OAT Material manifest v3
       exact T6 image identity
       exact OAT disk filename
       generated/layered component reconstruction
  -> DDS semantic stage v2
  -> portable textured glTF/GLB v2
  -> optional GfxWorld lightmap catalog
  -> world lightmap manifest v2
  -> lightmap raw-DDS archive v2
  -> deterministic final world GLB / optional glTF
```

With a lightmap catalog, the final v4 GLB therefore contains both:

1. staged material-image dependencies used by the current safe standard-preview path; and
2. exact raw primary/secondary lightmap DDS payloads retained renderer-neutrally in T6 metadata/bufferViews.

The final output still must not claim that generic glTF knows how to shade a T6 lightmap.

`tools/test_t6_oat_world_textured_export_pipeline_v4.py` verifies the orchestration/version chain and that a no-lightmap run never invokes the lightmap archive path.

## Current lightmap proof state

| Item | State |
|---|---|
| T6 `GfxWorld.lightmaps[]` ownership | P2 source-known |
| pair structure `primary` + `secondary` | P2 source-known; independently corroborated by another T6 PC walker |
| T6 primary code texture source `0x4` / `lightmapSamplerPrimary` | P2 |
| T6 secondary code texture source `0x5` / `lightmapSamplerSecondary` | P2 |
| surface `lightmapIndex` + dedicated UV side on retained Nuketown world | P4 |
| strict surface -> pair manifest algorithm | P3 |
| OAT image asset -> disk-name mapping/collision handling | P3 logic, production integrated |
| lossless raw DDS archive algorithm v2 | P3 logic |
| production world pipeline v4 | implementation integrated; retail lightmap fixture still pending |
| exact Nuketown primary/secondary GfxImage catalog | **pending retail P4** |
| exact Nuketown primary/secondary DDS archival GLB | **pending retail P4/P7** |
| primary/secondary image channel meaning | **unknown; P0/P1** |
| exact T6 shader combine equation | **unknown; P0/P1** |

Do not promote the last two rows from older IW/Treyarch-family shader behavior.

## T6-native sampler asymmetry clue

At pinned OpenAssetTools T6 definitions, both primary and secondary are code-sampler sources, but the custom sampler enum contains only:

```text
CUSTOM_SAMPLER_REFLECTION_PROBE = 0
CUSTOM_SAMPLER_LIGHTMAP_SECONDARY = 1
```

`lightmapSamplerSecondary` carries `customSamplerIndex = CUSTOM_SAMPLER_LIGHTMAP_SECONDARY`, while `lightmapSamplerPrimary` has no custom sampler index in the T6 table.

This is a useful structural clue about runtime binding behavior, **not** evidence for RGB/A encoding or lighting math.

## Independent T6 cross-source corroboration

External repository `tonytrawl/WiiU-T6-Studio` at commit `bc9def0c248ee01bf94a1e3c403f01ff7f30e3cb` contains independent T6 GfxWorld research.

Useful corroboration only:

- its PC `mp_raid` GfxWorld walker consumes each lightmap as two 32-bit image references and follows both as images when inline;
- its PC loading notes identify separate primary and secondary runtime texture arrays;
- its Wii U conversion research states that the console conversion keeps only the **secondary** lightmap resident and converts a PC 512x3072 RGBA8 secondary source to a Wii U 1024x1536 BC3 layout.

These facts are **not** imported as proof of PC shader channel semantics. Platform conversion may drop, repack, synthesize, or replace data for reasons unrelated to the PC pixel-shader equation.

## Why older-engine HLSL is not closure

Public IW4 shader reconstructions contain historical formulas using `lightmapSamplerPrimary` and `lightmapSamplerSecondary`, including use of secondary alpha and primary channel(s). They are useful hypothesis generators only.

T6 has changed sampler/runtime structures (including the custom-sampler asymmetry above), so an IW4 formula must not be copied into the T6 Blender/wgpu renderer without direct T6 bytecode/source or retail-output validation.

## Immediate next route to shader closure

The strongest next step is to obtain **actual T6 MaterialTechnique / MaterialPixelShader bytecode** for representative world lightmapped techniques and disassemble it.

Target process:

1. identify one ordinary Nuketown world material with `lightmapSamplerPrimary`/`Secondary` shader arguments;
2. retain its exact Material -> TechniqueSet -> Technique -> pixel-shader provenance;
3. extract the retail T6 pixel-shader bytecode without modification;
4. SHA-256 the bytecode and retain the XAsset/zone provenance;
5. disassemble DXBC/DX11 bytecode;
6. identify the primary/secondary sample instructions and channel swizzles;
7. reconstruct only the observed combine equation;
8. cross-check another materially different world technique;
9. only then implement the T6-aware Blender/wgpu lightmap graph.

If bytecode extraction is blocked by the current OAT dumper, extend the T6 techset/shader dumper minimally and document the patch exactly as was done for GfxWorld lightmap catalog extraction.

## Remaining retail blockers

- compile/run the retained GfxWorld lightmap OAT patch on a retail map (Nuketown first) and archive the exact catalog;
- archive exact source DDS hashes and final v4 GLB hash;
- independent loader/Blender validation of that GLB while verifying raw DDS payload recovery;
- recover T6 pixel-shader semantics;
- repeat across representative MP + Zombies/DLC worlds.

This file is a checkpoint, not a completion claim.
