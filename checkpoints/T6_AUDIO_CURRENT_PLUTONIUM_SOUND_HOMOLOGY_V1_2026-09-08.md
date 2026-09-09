# T6 current-Plutonium sound homology v1 — 2026-09-08

## Status

A narrowly relocation-aware transfer test from the exact SHA-pinned dedicated server into the exact current Plutonium client has completed. The result is a clean **10/10 negative**.

This is useful because it rejects a tempting but unsafe shortcut: the current client cannot be treated as the server code with only relocated addresses or displacements.

## Exact identities

Dedicated server:

- bytes: **13,711,872**
- SHA-256: `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`

Current Plutonium client, production revision **5346**:

- bytes: **13,263,640**
- SHA-256: `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`
- exact historical retail identity: **false**

## Exact comparison rule

Each already-closed server function was disassembled instruction-by-instruction with Capstone. The probe wildcarded only bytes demonstrated to encode location-sensitive values:

- relative control-transfer immediates;
- absolute immediates that point inside the server image;
- absolute no-base/no-index memory displacements.

Opcode bytes, register encoding, stack/layout instructions, constants not proven to be image pointers, and all other bytes remained exact.

The client `.text` section was then searched for a complete match under that mask. The matcher did not permit instruction substitution, reordered blocks, fuzzy edit distance, or partial promotion.

## Result

All ten targets had zero matches:

- `SD_PreUpdate` — 0
- `SD_UpdateVoice` — 0
- `SD_MixSetParam` — 0
- `SD_DecoderAllocate_generic` — 0
- `SD_DecoderAllocate_wrapper` — 0
- `SD_SourceInitStream` — 0
- `SD_StreamBufferPreload` — 0
- `SD_StreamAllocate` — 0
- `SD_VoiceSetParam` — 0
- `SD_VoiceStart` — 0

Summary: **0 unique / 0 ambiguous / 10 zero**.

## Durable proof

- workflow: `.github/workflows/t6_current_plutonium_sound_homology_probe_v1.yml`
- workflow commit: `0ec27bcd08bbb971cc5095c76a019ba8e73358f1`
- green run: `34306152554`
- job: `102323153145`
- artifact: `T6_CURRENT_PLUTONIUM_SOUND_HOMOLOGY_PROBE_V1`
- artifact ID: `10086706813`
- artifact ZIP SHA-256: `2b616a0858017bcba9a6d7c5852cdf770a99ec5b8a70ef04412359f94b0293f3`
- result JSON SHA-256: `025a390138ded2342c8631835a7452ac381c81cc31bd5394c20f774251e09f9a`
- compact manifest: `manifests/audio/T6_CURRENT_PLUTONIUM_SOUND_HOMOLOGY_PROBE_V1.json`

## Consequence

The current-client path now moves to **client-native ownership anchors** rather than progressively weakening server signatures. The next targets are the client's own XAudio2 imports, RTTI/type descriptors, vftables, callback implementations and direct code cross-references.

## Proof boundary

This proves only that none of these ten server bodies survives in the current client under the exact relocation-aware rule above. It does not prove analogous sound functionality is absent, and it does not establish historical retail identity, current-to-retail equivalence, or retail addresses.
