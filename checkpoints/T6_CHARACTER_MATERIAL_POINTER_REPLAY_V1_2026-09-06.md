# T6 character Material pointer replay v1 — 2026-09-06

This checkpoint hardens character Material* identity admission on `reversal/nonmap-assets`.

## Bug closed

`t6_character_material_binding_plan_v2.py` previously adapted every non-inline row in a durable `t6-xmodel-surface-material-assignments-v1` manifest to `exact-packed-virtual-material-owner` without independently replaying the retail pointer path. That could turn a historical packed-token correspondence into an exact binding merely because the manifest named a material.

The adapter now fails closed. A packed Material* is admitted only after an explicit `loaderReplay` reproduces:

1. a source-backed `Sys_DecodePointer` / `RtlDecodePointer -> Sys_DecodePointer` result;
2. `DB_ConvertOffsetToAlias` zone/segment arithmetic;
3. the exact resolved VIRTUAL pointer slot; and
4. a Material object established by retail inline-sentinel replay at that slot.

No material-name, surface-order, adjacency, visual, or token-shape inference is accepted.

## Inline and insert semantics

The reusable `t6_material_pointer_replay_v1.py` models:

- `0` as null;
- `-1`, `-2`, `-3` as inline Material* sentinels;
- `-3` as `DB_InsertPointer` allocation before inline load and insert-slot backfill after the object is loaded;
- repeated packed aliases as references to the same replayed pointer slot/object;
- decoded values `< 8`, unknown segment bases, unpopulated targets, raw runtime tokens without a source-backed decode, and unaccepted decoder evidence as fail-closed states.

## Synthetic regressions

The isolated regressions pass for:

- inline Material owner registration;
- packed decoded-pointer resolution;
- repeated aliases;
- `-3` insert allocation -> inline load -> owner-slot write -> insert backfill ordering;
- invalid target rejection;
- raw runtime-token rejection;
- rejection of synthetic decoder evidence in production mode; and
- rejection of historical packed rows that lack `loaderReplay`.

## Retail SEAL6 canary

The retained retail manifest `manifests/nonmap/retail/seal6_smg_surface_material_assignments_v1.json` is locked as the canary:

- 42 Material* handles;
- LOD surface counts 14 / 10 / 9 / 9;
- 13 historically named unique materials;
- 4 inline-following handles;
- 38 packed handles.

All 38 packed rows predate the strict loader-replay schema and contain no `loaderReplay` record. The corrected adapter therefore rejects the existing canary at surface 0 with `loader-replay-missing` instead of promoting any of them. False packed promotions: **0**.

This does not invalidate the retained historical owner ledger; it narrows its proof class. The ledger can supply candidate owner slots, but each packed row must still be reproduced through exact retail decode + alias arithmetic before it is exact under the current standard.

## Corpus proof boundary

The broader 30-body checkpoint remains unchanged:

- 390 LOD0 surfaces;
- 146 inline Material identities exact;
- 244 packed aliases pending exact VIRTUAL owner replay.

No packed Material identity is newly promoted by this checkpoint.

## Next target

Generate source-backed `loaderReplay` records for the SEAL6 packed handles from retail decoder/zone state and exact owner-slot cursor replay, then require the complete 42-handle canary to pass before generalizing across the 30-body corpus.
