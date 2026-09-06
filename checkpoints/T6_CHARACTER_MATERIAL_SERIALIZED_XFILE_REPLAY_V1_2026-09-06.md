# T6 Character Material Serialized XFile Replay v1 — 2026-09-06

## Result

The SEAL6 packed `Material*` canary is now closed without weakening the runtime pointer proof boundary.

Retail `faction_seals_mp` / `c_usa_mp_seal6_smg_fb` remains the canary:

- 42 serialized `materialHandles[]` entries
- LOD counts `[14, 10, 9, 9]`
- 13 unique material identities
- 4 inline sentinels
- 38 packed references
- 12 unique packed tokens
- 26 repeated-token backreferences
- 0 guessed packed promotions

The 38 packed rows are admitted only after a source-pinned serialized-XFile pointer replay lands exactly on an independently established `XModel.materialHandles[]` VIRTUAL owner field.

## Source-closed T6 archive pointer layout

Pinned OpenAssetTools revision:

`2ca512abe7cb82d70a94d5ad7846043c3978862d`

Relevant source paths at that revision:

- `src/ZoneCommon/Game/T6/ZoneConstantsT6.h`
- `src/ZoneLoading/Game/T6/ZoneLoaderFactoryT6.cpp`
- `src/ZoneLoading/Zone/Stream/ZoneInputStream.cpp`
- `src/Common/Game/T6/T6_Assets.h`

The source establishes all pieces needed for an offline retail T6 PC archive pointer:

1. T6 PC uses 32-bit words/pointers.
2. `OFFSET_BLOCK_BIT_COUNT == 3`.
3. T6 block order places `XFILE_BLOCK_VIRTUAL` at block index 5.
4. The loader reserves serialized zero for null and therefore decodes a non-inline archive pointer by subtracting one first.
5. The resulting 32-bit value is split into the high 3 block bits and low 29 block-offset bits.

Therefore:

```text
encoded = ((block_index << 29) | block_offset) + 1
block_index = (encoded - 1) >> 29
block_offset = (encoded - 1) & 0x1fffffff
```

This is an **archive serialization rule**. It is not the runtime `Sys_DecodePointer` cookie/obfuscation path and is implemented separately.

## SEAL6 exact owner replay

The durable owner ledger is:

`manifests/nonmap/retail/seal6_smg_material_handle_alias_proof_v1.json`

Its authority explicitly records expanded retail T6 XModel serialization plus exact VIRTUAL pointer-field ownership, with no material-name correlation used for packed resolution. Each promoted packed token has an independently recorded owner model, `materialHandles[]` slot, VIRTUAL owner-field offset, Material identity, and raw Material start.

Representative exact decodes:

```text
0xA0336C39 -> block 5, offset 0x00336C38 -> lmg materialHandles[0]
0xA00F8EBD -> block 5, offset 0x000F8EBC -> assault materialHandles[0]
0xA040A719 -> block 5, offset 0x0040A718 -> shotgun materialHandles[8]
0xA0543C69 -> block 5, offset 0x00543C68 -> smg materialHandles[12]
```

The producer rejects a row if the block is not 5, the decoded offset differs by even one byte from the independent owner field, the owner ledger differs in expanded-XFile identity, the material identity conflicts, or the pinned source revision/evidence is missing.

## Implementation

Added:

- `tools/t6_serialized_xfile_pointer_replay_v1.py`
- `tools/t6_character_material_serialized_proof_v1.py`
- `tools/test_t6_serialized_xfile_pointer_replay_v1.py`
- `tools/test_t6_character_material_serialized_proof_v1.py`

Updated:

- `tools/t6_character_material_binding_plan_v2.py`
- `tools/test_t6_character_material_binding_plan_v2_retail_canary.py`

`binding_plan_v2` now accepts two disjoint strict packed-pointer proof modes:

- runtime: exact `Sys_DecodePointer` + `DB_ConvertOffsetToAlias` replay
- serialized retail XFile: exact 32-bit/3-block-bit/+1 archive decode to an independently established VIRTUAL owner field

It does not fall from one mode into a heuristic version of the other.

## Tests

Local tests passed for:

- representative T6 serialized pointer decodes
- pinned source revision enforcement
- null and inline sentinel rejection as packed archive pointers
- wrong block rejection
- owner-slot mismatch rejection
- material mismatch rejection
- assignment/owner expanded-XFile mismatch rejection
- conflicting owner-ledger record rejection
- repeated owner backreference accounting
- shape-equivalent full 42-row SEAL6 replay: 38 packed rows, 12 unique packed tokens, 26 backreferences

The repository retail canary now performs both halves deliberately:

1. the untouched historical surface manifest still fails closed when used alone;
2. after strict replay proofs are generated from the independent owner ledger, all 42 handles must pass, including all 38 packed rows.

## Broader character boundary

This checkpoint closes the **SEAL6 canary**, not the whole 30-body census by assertion.

The broader authoritative LOD0 character boundary remains:

- 390 LOD0 surfaces
- 146 exact inline material identities
- 244 packed aliases awaiting the same source-backed owner-ledger replay

Next step: build the owner registry for the 30-body corpus from exact XModel/VIRTUAL cursor replay, run this same serialized pointer validator over all 244 packed rows, and promote only those that land on independently established owner fields.
