# T6 Reverse-Engineering Proof Standard

**Project:** Call of Duty: Black Ops II / Treyarch T6 asset and runtime-format reconstruction  
**Repository:** `lizardpeter/bo2-t6-assets`  
**Established:** 2026-09-01

This document defines what the project is allowed to call **solved**.

The goal is not merely to produce files that look plausible. The goal is to recover T6 formats and relationships in a way that is reproducible, source-auditable, regression-tested, and portable to future exporters/renderers without repeating reverse engineering.

## Non-negotiable rule

No inference is silently upgraded into fact.

A decoder may support a layout synthetically before that layout has been observed in a retained retail fixture. A preview shader may look visually correct before the original shader composition is understood. Those are useful milestones, but they are different proof states and must remain labeled differently.

## Proof levels

Every independently meaningful T6 format, field, relationship, or algorithm should be assigned one of these states.

### P0 — Unknown

The structure/semantic is not understood well enough to consume safely.

Requirements:
- preserve original bytes/assets when possible;
- fail closed rather than inventing a meaning;
- record the blocker and the fixture needed to advance it.

### P1 — Structural hypothesis

A plausible structure or semantic has been inferred from offsets, counts, neighboring generations, decompiler output, statistical relationships, or observed runtime behavior.

Requirements:
- hypothesis written down explicitly;
- no destructive conversion based only on the hypothesis;
- original evidence retained.

### P2 — Formula/source-known

The relevant engine/decompiler/tool source or an equivalent exact formula has been recovered and the field/algorithm meaning is source-closed at the structural level.

Examples:
- generated layered-material numeric tokens are parsed as BSP material indices;
- layered `n` markers are validated against `Material_HasNormalMap`;
- layered `worldVertFormat` is determined by layer count plus normal-map count.

Requirements:
- stable source reference or exact recovered algorithm documented;
- implementation matches that algorithm;
- assumptions outside the recovered algorithm remain explicit.

### P3 — Synthetic regression proven

The decoder/exporter has deterministic tests that exercise the recovered rule, including negative/fail-closed cases.

Requirements:
- committed regression test;
- malformed/ambiguous inputs are rejected when appropriate;
- deterministic output is checked when the format permits it.

P3 does **not** prove that a particular retail game build actually uses every synthetic variant.

### P4 — Retail byte proven

The format has been decoded directly from retained retail T6 bytes/assets and validated against independent constraints.

Good P4 evidence includes several of:
- exact serialized byte ranges and hashes;
- bounds/count invariants;
- independent parser/loader acceptance;
- pointer/array relationships;
- round-trip or reconstruction checks;
- matching known source formulas;
- multiple retail fixtures/maps/assets.

A format observed in only one retail fixture is P4 for that observed form, not automatically universal across all T6 content.

### P5 — Cross-fixture proven

The same decoder has been validated against materially different retail fixtures: different maps, zones, model classes, animation shapes, DLC/base content, or other relevant variants.

Requirements:
- fixture identities recorded;
- no fixture-specific hard-coded offsets masquerading as a generic decoder;
- failures become explicit blockers rather than silent fallback.

### P6 — Export integrated

The proven data is consumed by the normal one-command archival/export path with provenance retained.

Requirements:
- production pipeline uses the strongest proven decoder rather than an older approximation;
- output carries enough metadata to trace back to T6 identities;
- unknown semantics remain present in extras/manifests or preserved sources rather than being discarded.

### P7 — Independent consumer validated

At least one independent consumer can load/use the result correctly.

Examples:
- glTF/GLB accepted by an independent loader;
- Blender imports with sane bounds, materials, skinning, and animation;
- a separate verifier reconstructs bind matrices or validates weights;
- a second implementation agrees on decoded values.

### P8 — T6-closed

The project may call a subsystem **fully solved** only when all material retail variants needed by T6 are P5+ and the complete intended archival/export path is P6/P7, with no known semantic gaps that affect faithful reconstruction.

A visually adequate approximation is not P8.

## Required artifacts for durable progress

Whenever practical, a solved or advancing subsystem should leave all of the following behind:

1. **Decoder/normalizer** under `tools/`.
2. **Regression** under `tools/test_*.py`.
3. **Proof manifest** under `manifests/`, including hashes/counts/fixture identity where available.
4. **Research note or ledger entry** under `research/` explaining the recovered meaning and remaining boundary.
5. **Production integration** once the proof level permits it.
6. **Source references** pinned to repository commit/revision when external recovered engine/tool source materially established the rule.

## Fail-closed policy

A generic exporter must stop or emit an explicit unresolved record when it encounters a representation outside its proof boundary.

Forbidden behavior includes:
- guessing vertex strides because one map happens to render;
- choosing textures from filename suffixes when exact semantics are available;
- silently flattening Treyarch layered materials into arbitrary PBR mixes;
- silently merging primary/secondary lightmaps before their shader meaning is closed;
- discarding unknown XAsset fields because a preview does not need them;
- treating patch-zone asset counts as additive when the patch overrides an existing identity.

## Determinism policy

For archive-oriented transforms, identical inputs should produce byte-identical manifests and, where practical, byte-identical exported GLB/glTF outputs.

Tests should compare complete serialized output or SHA-256 where feasible. If nondeterminism is unavoidable, the reason must be documented.

## Provenance policy

Every reconstructed artifact should retain enough information to answer:

- Which T6 zone/container supplied it?
- Which XAsset identity/type supplied it?
- Which base/patch layer won?
- Which exact source bytes or source asset names were consumed?
- Which decoder/tool version produced the representation?
- Which semantics were exact, which were derived, and which remain unresolved?

## Cross-generation source policy

IW3/T4/T5/IW4/IW5/QOS source and decompilations are valuable for recovering inherited engine behavior, but they are not automatically proof of T6 behavior.

When a rule is learned from an inherited engine source, it stays P1/P2 until T6 structure or retained retail evidence is consistent with it. This distinction is especially important for renderer fields, sentinels, and shader composition.

## Source references currently used for world/material work

Pinned references used by the current layered-material and lightmap research include:

- OpenAssetTools T6 asset structures, commit `7d027e8f89118196713e955b0e11f8404149c54d`, especially `src/Common/Game/T6/T6_Assets.h`.
- KisakBlack recovered renderer/material code, commit `2a7785269d2f969ecc1ce2931679a8a39536f5dd`, especially `src/gfx_d3d/r_material_load_obj.cpp`, `r_draw_bsp.cpp`, and related headers.

These references establish structure/algorithm evidence; retained T6 fixture manifests remain the authority for retail-byte proof.

## Closure discipline

When a new format variant is found:

1. preserve the fixture first;
2. add it to the ledger as P0/P1;
3. decode only what evidence supports;
4. add deterministic positive and negative tests;
5. promote to P4 only after direct retail-byte validation;
6. add a second materially different fixture before claiming broad/universal support;
7. integrate into the normal pipeline;
8. keep the original fixture and proof manifest indefinitely.

This is the standard for the remainder of the T6 project.
