# T6 audio alias → physical bank closure v1

Date: 2026-09-07

## Result

The structural T6 audio path is now closed across the complete referenced public retail archive from serialized FastFile aliases through exact physical SABS/SABL identifiers:

`215 FastFiles → SndBank → SndAliasList → SndAlias.assetId → 116 SABS/SABL banks`

For **every nonzero serialized `SndAlias.assetId` recovered by the complete FastFile census**, an exact 32-bit identifier exists in the physical audio-bank universe.

This checkpoint supersedes the older audio statement that the alias graph still lacked a completed numeric census. Runtime playback semantics remain a separate problem.

Machine-readable summary:

`manifests/audio/T6_AUDIO_ALIAS_PHYSICAL_CLOSURE_V1.json`

## Archive universe

The two independently generated populations use the same ZIP64 archive identity:

- ZIP bytes: **13,675,690,564**
- entries: **534**
- ETag: `"32f227a44-619f0ebe56147"`
- FastFiles: **215**
- physical sound banks: **116**
  - **66 SABS**
  - **50 SABL**

No partial-zone or partial-bank population is promoted here.

## Complete FastFile SndAlias census

Run: **34177086929**

Aggregate artifact:

- ID: **10037696180**
- name: `T6_SNDALIAS_ALL_FASTFILE_CENSUS_V1`
- digest: `sha256:7aa3a37ac803a49d0b629cad446c1475edd682a328d2d39cce07c1fce19eac8a`
- aggregate JSON SHA-256: `5da7ed9c5cd5ea4c2cd69213438103883f6c804db678db6496f781ed86713f5d`

All **8/8 shards** and the aggregate completed green.

Exact census:

- FastFiles CRC-verified, SHA-pinned, decrypted/inflated and scanned: **215 / 215**
- FastFiles with a validated serialized SndBank alias section: **63**
- validated SndBank sections: **63**
- exact physical-bank-base string candidates: **72**
- structurally rejected candidates: **9**
  - all 9 rejection kind: `no_alias_lists`
- alias-definition occurrences: **445,664**
- unique alias IDs: **18,103**
- unique semantic variants: **47,956**
- validated inline alias names: **16,994**
- alias IDs without a validated inline name: **1,109**
- nonzero `assetId` occurrences: **441,570**
- zero `assetId` occurrences: **4,094**
- unique nonzero `assetId` values: **24,481**

The large occurrence count is intentionally not called a unique sound count. Zone-specific copies and semantic variants are preserved rather than collapsed incorrectly.

### Alias parser proof boundary

A physical bank-base string only nominates a possible serialized SndBank section. A section is accepted only after the `SndAliasList` array shape, pointer form, count bounds, inline string/hash relation where present, and per-head alias-ID equality gates pass.

The parser preserves the raw 96-byte SndAlias fields and computes semantic-variant identities without assigning guessed high-level meanings to unknown playback fields.

`assetId == 0` is retained as an explicit serialized state. It is **not** counted as missing physical audio.

## Complete physical SABS/SABL population

Run: **34177204458**

Aggregate artifact:

- ID: **10037689364**
- name: `T6_AUDIO_PHYSICAL_ID_MANIFEST_V1`
- digest: `sha256:da4e9a19922b283d111a23af7064c5e3d7afc40a4d1e063c8dddebb1050a6caa`
- aggregate JSON SHA-256: `d2a7f4f64db7f2dcd346b6d9e1b28eb72efa0e7e7ae98ef35b00e3ad582e7357`

All **8/8 physical-bank shards** and the aggregate completed green.

Every ZIP bank entry was CRC-verified, fully extracted, SHA-256 pinned, and parsed through the exact structural bank table before aggregation.

Exact population:

- banks: **116 / 116**
- physical audio-entry rows: **25,446**
- unique 32-bit physical identifiers: **24,642**
- physical format population:
  - **20,700 FLAC**
  - **4,746 PCMS16**
- invalid payload-range entries: **0**
- identifiers occurring in more than one physical bank location: **670**
- duplicate extra occurrences beyond first copy: **804**
- maximum physical multiplicity of one identifier: **7**

The fresh public-archive run independently reproduces the previously retained 25,446 / 20,700 / 4,746 local catalog totals.

## Exact alias → physical join

Join implementation:

`tools/t6_audio_alias_physical_join_v1.py`

Negative/guardrail regression:

`tools/test_t6_audio_alias_physical_join_v1.py`

Workflow:

`.github/workflows/t6_audio_alias_physical_join_v1.yml`

Run: **34178324098**

Artifact:

- ID: **10038007398**
- name: `T6_AUDIO_ALIAS_PHYSICAL_JOIN_V1`
- digest: `sha256:3ab090b1b4518bd34c5d6808c95b80ca1da540010036188dc82f90a59bda28b5`
- join JSON SHA-256: `e7bd3a6cb3cc2e9060d540b5abc2e37085c106beaab4379a167431b7d1a1a6c4`

The source artifact IDs/digests and exact aggregate JSON hashes are themselves retained inside the join artifact.

### Coverage

- unique nonzero alias `assetId` values: **24,481**
- unique nonzero IDs found physically: **24,481**
- unmatched nonzero IDs: **0**
- **unique nonzero asset-ID coverage: 100%**

Occurrence-weighted:

- nonzero alias occurrences: **441,570**
- physically matched nonzero alias occurrences: **441,570**
- **occurrence coverage: 100%**

This is an exact 32-bit identifier join, not name similarity.

### Physical IDs not reached by SndAlias.assetId

The physical universe contains:

- **161 unique identifiers** not referenced by a nonzero `SndAlias.assetId` in the current complete FastFile census;
- those account for **174 physical entry occurrences**.

They are deliberately called **physical-only relative to this alias census**, not unused/dead audio. Direct runtime references, special systems, localization/loading behavior, or other reference classes remain possible until independently excluded.

### Duplicate physical identifiers

Across all physical banks:

- duplicate identifiers: **670**
- duplicate extra occurrences: **804**
- duplicates referenced by at least one SndAlias: **657**
- alias occurrences referencing those duplicated IDs: **1,896**

For all **670 / 670** duplicate identifiers, every physical occurrence agrees on all of these retained fields:

- stored 128-bit checksum record;
- encoded data byte count;
- sample count;
- sample-rate selector and resolved rate;
- channels;
- loop byte;
- format code/name.

Divergent duplicate identifier count under that identity test: **0**.

This is **not yet a byte-identity claim for the encoded audio payloads themselves**. The compact aggregate does not retain per-entry payload hashes. Payload-byte identity can be promoted later by hashing the referenced spans in the duplicate bank copies.

## Current proof-state interpretation

For the exact referenced 215-FastFile / 116-bank archive universe:

- SABS/SABL structural bank grammar and complete bank-table census: **P5/P6**;
- serialized SndBank/SndAliasList/SndAlias structural census: **P5/P6**;
- exact nonzero `SndAlias.assetId → physical identifier` membership join: **P5/P6**;
- runtime sound-system semantics: **not P8**.

The entire audio subsystem is therefore **not** called solved, but the old structural/index/linkage gap is closed.

## Still open

The remaining audio work is now primarily semantic/runtime rather than basic container discovery:

1. Determine the meaning/conversion of every preserved SndAlias playback field rather than merely retaining its integer encoding.
2. Close runtime alias variant selection, sequence/probability/randomization and context rules.
3. Close bank activation/dependency/patch precedence and how duplicate physical copies are selected at runtime.
4. Close volume, pitch, distance, reverb, envelope, priority, ducking, pan, occlusion and doppler behavior.
5. Close spatialization and mixing buses.
6. Close weapon / FX / entity / dialogue / music consumer linkage and scheduling.
7. Explain the 4,094 zero-asset alias occurrences by source-closed runtime semantics.
8. Classify the 161 physical-only identifiers without assuming they are unused.
9. Hash duplicate encoded payload spans before upgrading duplicate-copy equality from checksum/metadata identity to byte identity.
10. Validate actual FLAC/PCM extraction/decoding through independent consumers across representative banks and modes.

## Proof boundary

No audio runtime behavior is inferred from an alias field name, a repeated physical ID, filename mode prefixes, external Names.xml labels, or engine-family similarity. The closure here is exact serialized structure plus exact 32-bit physical membership across the complete referenced archive. Runtime behavior remains fail-visible until independently source-closed or retail-observed.
