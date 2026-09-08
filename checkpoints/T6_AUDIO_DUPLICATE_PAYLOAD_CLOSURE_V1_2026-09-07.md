# T6 audio duplicate payload closure v1 — 2026-09-07

## Status

The duplicate physical-audio ambiguity is closed for the exact 116-bank archive universe.

The earlier audio closure had already proven that all duplicate physical IDs agreed on parsed metadata and the stored 128-bit checksum field. That was deliberately not called payload-byte equality. This checkpoint closes the stronger statement by hashing the exact table-declared payload span of every duplicated occurrence.

## Exact result

Source physical manifest:

- workflow run `34177204458`
- artifact `T6_AUDIO_PHYSICAL_ID_MANIFEST_V1`
- artifact digest `sha256:da4e9a19922b283d111a23af7064c5e3d7afc40a4d1e063c8dddebb1050a6caa`
- physical entries: **25,446**
- unique physical identifiers: **24,642**

Duplicate-payload closure:

- workflow run `34181586963`
- artifact ID `10039115375`
- artifact `T6_AUDIO_DUPLICATE_PAYLOAD_CLOSURE_V1`
- artifact digest `sha256:a7c31bc4bb970df381c924edf012a96ecf4006fd9dc8ef97563fe40ebb01418f`
- full result JSON SHA-256 `7da24e871aac905d680bad1c2deca7aa9d3d254eda9dd91d49d1ec6559130a7d`

Population:

- **670** identifiers occur in more than one physical bank entry
- **1,474** total occurrences of those duplicate IDs
- **804** extra occurrences beyond one canonical occurrence per ID
- maximum multiplicity **7**

Byte comparison:

- **670 / 670 duplicated IDs have exactly one payload SHA-256 value**
- **0 payload-byte-divergent duplicate IDs**
- **0 divergent duplicate occurrences**

Therefore every duplicate physical identifier in this archive is backed by byte-identical encoded payload bytes across all of its physical occurrences.

## Proof method

Committed implementation:

- `tools/t6_audio_duplicate_payload_closure_v1.py`
- `tools/test_t6_audio_duplicate_payload_closure_v1.py`
- `.github/workflows/t6_audio_duplicate_payload_closure_v1.yml`

For every duplicated occurrence the workflow:

1. identifies the exact source SABS/SABL and entry index from the retained physical manifest;
2. extracts the exact source bank from the public retail archive with ZIP CRC verification;
3. requires the full source-bank SHA-256 to equal the retained manifest identity;
4. reads the exact `dataOffset` and `dataBytes` span already validated by the T6 bank grammar;
5. computes SHA-256 over those payload bytes;
6. requires exact set equality over all **1,474** duplicated occurrences before aggregation;
7. groups by 32-bit physical identifier and compares the resulting payload SHA-256 values.

The full artifact preserves every identifier, bank path, bank SHA, entry index, data offset/size, parsed audio metadata, stored checksum and computed payload SHA-256.

A compact durable summary is also recorded at:

`manifests/audio/T6_AUDIO_DUPLICATE_PAYLOAD_CLOSURE_V1.json`

## What this promotes

Previous safe statement:

> Duplicate physical IDs are stored-checksum/metadata identical.

New authoritative statement for this archive:

> All **670** duplicated physical IDs are **payload-byte identical** across every one of their **1,474** physical occurrences.

This means bank duplication does not introduce multiple encoded-audio payload variants for the same physical identifier in the current complete 116-bank corpus.

## What this does not prove

This checkpoint does **not** establish:

- retail runtime bank precedence;
- which duplicate bank occurrence a runtime lookup returns first;
- SndAlias variant-selection semantics;
- `secondaryName` playback/fallback order;
- randomization, sequence, probability or context behavior;
- stop-on-play behavior;
- spatialization, pitch, volume, ducking or reverb runtime semantics;
- equivalence outside the exact 116-bank archive universe.

Because the payload bytes are identical, runtime bank precedence among these duplicate physical occurrences no longer matters for decoded audio content, but precedence may still matter for non-payload state not represented by these physical entries.

## Durable boundary

Do not regress this result to checksum-based inference. The authority comes from direct SHA-256 comparison of the exact encoded payload spans after source-bank identity verification.
