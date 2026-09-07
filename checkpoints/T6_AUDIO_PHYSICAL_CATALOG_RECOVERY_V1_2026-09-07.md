# T6 physical audio catalog recovery v1

Date: 2026-09-07

## Why this checkpoint exists

The September whole-project ledger understated previously completed T6 audio work. Retained user-source artifacts from 2026-08-23 contain both the physical SABS/SABL cataloger and a completed catalog run over the then-current full-game sound directory.

The source script itself remains in the retained File Library as `bo2_audio_cataloger.py`; it is not reconstructed or paraphrased into Git by this checkpoint. This file preserves the exact completed-run facts so the work is not forgotten while the original source artifact is rematerialized into the repository later.

## Retained completed physical-bank run

Retained `catalog_metadata.json` reports:

- schema: `bo2_audio_catalog_v1`
- game: Call of Duty: Black Ops II
- engine generation: T6
- source sound directory: `C:\Users\dgera\Downloads\Plutonium\pluto_t6_full_game\sound`
- bank files found: **116**
- bank files parsed: **116**
- bank files failed: **0**
- physical audio entries documented: **25,446**
- names resolved through the optional Names.xml mapping: **25,332**
- unresolved exact 32-bit identifiers: **114**
- elapsed time: 1.304 s

The retained text report independently records observed physical-entry format counts:

- **20,700 FLAC**
- **4,746 PCMS16**

for exactly 25,446 entries total.

No parse error occurred in that run.

## Physical format parsed by the retained tool

The retained `bo2_audio_cataloger.py` explicitly validates:

- magic `0x23585532` (`2UX#` on disk)
- T6 bank version `0x0E`
- audio entry size `0x14` / 20 bytes
- checksum entry size `0x10` / 16 bytes
- dependency entry size `0x40` / 64 bytes

For every physical entry it records, from the bank bytes:

- exact 32-bit identifier
- data offset
- data size/end
- whether the data span remains inside the physical bank
- sample count
- sample-rate selector and resolved rate
- channel count
- loop byte
- format code/name
- duration derived from sample count/rate
- raw 16-byte stored checksum record
- containing bank identity
- bank dependency strings

The parser has named format cases for:

- `0x00` PCMS16
- `0x04` XMA4
- `0x05` MP3
- `0x08` FLAC

Only FLAC and PCMS16 were present in the retained completed 116-bank run described above. Parser support for a named format code is not by itself retail-observed proof of that format.

## Name provenance boundary

Resolved path names are **not** serialized plaintext names in each bank entry. The physical bank stores a 32-bit identifier. The retained tool optionally joins that identifier to the public Black Ops II Sound Studio `Names.xml` database.

Therefore:

- the 25,446 physical entries and their numeric/byte metadata are bank-derived;
- 25,332 resolved path strings are external name-database joins;
- 114 entries remain correctly preserved by exact 32-bit identifier;
- an unresolved name never means the physical sound is missing;
- filename-based mode labels are convenience metadata only and are not used to parse the bank.

## Retained FastFile alias-link work

A second retained source artifact, `bo2_fastfile_alias_cataloger.py`, goes substantially further:

- decrypts/decompresses retail-style PC T6 FastFiles (`TAff0100`, version `0x93`, `PHEEBs71`);
- parses serialized `SndBank -> SndAliasList -> SndAlias` structures;
- preserves every zone-specific alias variant occurrence;
- computes the T6 `SND_HashName` name hash;
- treats non-zero `SndAlias.assetId` as the exact join key into the physical SABS/SABL catalog;
- retains `assetId == 0` instead of calling it missing audio;
- creates semantic-variant groups while excluding serialized pointer/source-location noise;
- resolves alias names first from validated inline names and then from matching hashed short strings in scanned FastFiles;
- emits compact alias, occurrence, unique-variant and scan-summary outputs.

The retained File Library currently exposes the source tool but not the completed `bo2_alias_scan_summary.json` values. Consequently this checkpoint does **not** invent alias coverage counts or claim the alias graph globally closed. The tool/source progress is preserved here, while numerical alias-run promotion waits for the actual retained summary or a fresh rerun.

## Current audio closure interpretation

The old ledger statement that SABS/SABL work was mainly preservation-only is obsolete.

What is now safely known to have been completed previously:

1. deterministic T6 SABS/SABL physical table parsing;
2. a zero-failure 116-bank physical catalog run over the retained full-game sound directory;
3. exact metadata recovery for 25,446 physical audio entries;
4. nearly complete optional external-name resolution for that physical population;
5. an implemented FastFile SndAlias parser/joiner reaching from alias definitions toward physical bank payload IDs.

Still not T6-closed:

- source-hash/provenance pinning of every bank in the retained catalog run;
- rematerializing the original cataloger source into this Git repository;
- a retained/fresh numeric alias scan summary;
- exact semantics for every SndAlias flag/playback field that the parser preserves numerically;
- sound event/alias runtime selection, randomization and context rules;
- spatialization/volume/pitch/mix/runtime behavior;
- exhaustive campaign/localization/DLC bank completeness against a canonical retail source universe;
- normalized extraction/decoding validation for every observed codec branch;
- weapon/FX/entity/dialogue/music runtime linkage and independent-consumer validation.

This is therefore a **recovered progress checkpoint**, not a P8 audio closure claim.
