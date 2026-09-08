# T6 audio zero-asset / Secondary closure v2 — 2026-09-07

## Promotion over v1

This checkpoint supersedes the **coverage** portion of `T6_AUDIO_ZERO_SECONDARY_CLOSURE_V1_2026-09-07.md` while preserving v1 as historical evidence.

V1 classified only the 136 inline-serialized `Secondary` strings. V2 resolves the entire zero-asset Secondary population through pinned native OpenAssetTools after actual T6 loader pointer/backreference fixups, without interpreting the 1,334 raw non-inline 32-bit pointer values.

Runtime playback behavior remains deliberately outside this proof.

## Complete zero-asset source population

The retained structural census remains exactly:

- 215 / 215 FastFiles green;
- 445,664 serialized SndAlias occurrences;
- 18,103 unique alias IDs;
- 47,956 semantic variants;
- 441,570 nonzero `assetId` occurrences;
- 4,094 zero `assetId` occurrences;
- 429 alias IDs with at least one zero variant;
- 294 zero-only alias IDs;
- 135 mixed zero/nonzero alias IDs.

Every nonzero asset ID is already joined to the physical 116-bank population:

- 24,481 / 24,481 unique nonzero IDs physically present;
- 441,570 / 441,570 nonzero occurrences covered;
- zero unmatched nonzero IDs.

Source JSON identities:

- zero census: `6a05d394c591c074570751e68429c47ba6f801701826199780994326ae125fed`
- complete alias census: `5da7ed9c5cd5ea4c2cd69213438103883f6c804db678db6496f781ed86713f5d`
- alias -> physical join: `e7bd3a6cb3cc2e9060d540b5abc2e37085c106beaab4379a167431b7d1a1a6c4`

## Source-closed meaning of assetId == 0

Pinned OAT T6 source commit:

`9dca965366541504b71fa8cfb7ac049cb9b717e1`

establishes:

1. `SndAlias` is zero-initialized;
2. only a non-empty `FileSource` assigns `assetFileName` and `assetId = SND_HashName(assetFileName)`;
3. `Secondary` is loaded independently;
4. OAT writes physical SABS/SABL audio only when both `assetFileName` and `assetId` are nonzero.

Therefore the project may call `assetId == 0`:

> no direct FileSource assigned to that serialized alias variant in the source-supported T6 authoring model

It must not be called “missing audio”.

## Native post-loader Secondary resolution

Reusable tools:

- `tools/t6_oat_zero_secondary_resolver_v1.py`
- `tools/test_t6_oat_zero_secondary_resolver_v1.py`
- `tools/t6_oat_zero_secondary_aggregate_v1.py`
- `tools/test_t6_oat_zero_secondary_aggregate_v1.py`
- `.github/workflows/t6_oat_zero_secondary_all_fastfile_v1.yml`

Key commits:

- resolver `a16c4b4e366e4ca867ab496e3c6448085f9d01fd`
- resolver regression `aa5b2a5cdd87cd3fc83b91e097882f32994e6e9d`
- aggregate `9dde629d157c7765299ca28704d862e90255f5f6`
- aggregate regression `56150f84bf9a9e8a993c4ae9e68dd5822a975d6c`
- all-FastFile native workflow `f8c71715fd34542398386e30a45158b3dffd5c63`

Workflow run `34181062551` is fully green:

- unit gate green;
- native shards 0 through 7 all green;
- aggregate green.

Each zero-bearing FastFile was extracted from the same public ZIP used by the original structural census, ZIP-CRC verified, and SHA-256 checked against the already-retained FastFile SHA before pinned OAT saw it.

The aggregate requires exact set equality over every raw census key:

`(bankName, aliasId, variantIndex)`

so a native shard cannot silently omit or add a zero row.

### Native aggregate identity

- artifact `T6_OAT_ZERO_SECONDARY_ALL_FASTFILE_V1`
- artifact ID `10038932692`
- artifact digest `sha256:08d0b39561327a8736a61f325d99b2cfeb06d88f96454b7a1e99871930df1817`
- aggregate JSON SHA-256 `09cac679a1a243e29cb9cc6de632702ff2ea48953f2a5225ea5023a41c3366aa`

### Exact native result

- 37 / 37 zero-bearing SndBank sections covered;
- 4,094 / 4,094 zero-asset rows covered;
- 2,624 raw-null Secondary pointers remained empty;
- 136 / 136 inline-serialized Secondary strings reproduced exactly;
- **1,334 / 1,334 non-inline Secondary pointers resolved to non-empty post-loader strings**;
- **0 unresolved non-inline Secondary pointers**;
- therefore 1,470 total non-empty Secondary occurrences;
- 44 unique resolved Secondary names.

This closes the serialized-pointer/string-resolution class for this exact archive population.

Raw 32-bit values are retained only as source evidence. They were never reinterpreted as addresses, hashes, string offsets, or guessed backreferences.

## Complete Secondary target graph

Target classifier:

- `tools/t6_sndalias_zero_secondary_join_v2.py`
- `tools/test_t6_sndalias_zero_secondary_join_v2.py`
- `.github/workflows/t6_sndalias_zero_secondary_join_v2.yml`

Commits:

- v2 classifier `17bb7109f7fc8fef11cc687adfd51af5ddc62479`
- regression `33d6510c8a2edd291c33134ff7d243387c8edfac`
- retained workflow `a95d296f7da6cde0bae62c753585c69742884a43`

Workflow run `34181233120` completed green.

Artifact:

- `T6_SNDALIAS_ZERO_SECONDARY_JOIN_V2`
- artifact ID `10038970210`
- artifact digest `sha256:adadb96bc22561369a0c1c0d77557c0400a0e188da6b5960ab4f1fd2beb82010`
- JSON SHA-256 `3cf85796151d8073c41366377a1847b76b9964dee4a2096544cd4815f096d9d4`

### Exact target classifications

All 1,470 non-empty resolved Secondary occurrences were hashed with exact T6 `SND_HashName` and compared against the complete accepted 18,103-alias census.

Unique target names, 44 total:

- 12 nonzero-only target families;
- 12 mixed zero/nonzero target families;
- 18 zero-only target families;
- 2 target names absent from the accepted alias census.

Occurrence population, 1,470 total:

- 1,336 occurrences -> nonzero-only target families;
- 16 occurrences -> mixed zero/nonzero target families;
- 116 occurrences -> zero-only target families;
- 2 occurrences -> target ID absent from accepted alias census.

Because every nonzero target variant is already covered by the independent 24,481 / 24,481 physical join:

- 24 / 44 unique Secondary names have at least one physically backed target variant;
- **1,352 / 1,470 Secondary occurrences = 91.972789%** point to a target family with at least one physically backed direct asset variant.

This is a dependency classification only. It does **not** prove the retail engine actually follows `Secondary` when the zero-FileSource variant is selected.

## Dominant resolved edges

The largest exact target populations include:

- `fly_gear_fall_npc` — 1,184 Secondary occurrences, nonzero-only target family;
- `fly_bodyfall_sweet_gravel` — 62 occurrences, zero-only target family;
- `fly_cloth_npc` — 35 occurrences, nonzero-only target family;
- `fly_weight_plr` — 35 occurrences, nonzero-only target family;
- `prj_bulletspray_debris_large_dirt` — 35 occurrences, nonzero-only target family;
- `fly_prone_n_mantle_npc` — 16 occurrences, nonzero-only target family;
- `fly_prone_n_mantle_plr` — 16 occurrences, nonzero-only target family.

The complete 44-target table is retained in:

`manifests/audio/T6_SNDALIAS_ZERO_SECONDARY_CLOSURE_V2.json`

commit:

`773ca6426b16ff1313438022272bb863c9488f42`

## Two unresolved target identities

Only two resolved Secondary names hash to IDs absent from the complete accepted 215-FastFile alias census.

### 1. WA2000 lineage edge

Resolved target:

- name `wpn_wa2000_bass_swt_silencer`
- hash `646B2B38`

Source edge:

- source alias `wpn_metalstormsnp_silencer_fire_plr`
- source alias ID `A4BDB640`
- source bank `mpl_common.all`
- source FastFile `pluto_t6_full_game/zone/all/common_mp.ff`
- source variant index 0
- raw Secondary state: inline serialized.

Historical BO1/T5 soundalias data contains this name as a real alias. That remains lineage/search guidance only and is not promoted as T6 ownership or playback evidence.

### 2. Alcatraz tomahawk edge

Resolved target:

- name `zmb_tomahawk_sparks`
- hash `39797FA4`

Source edge:

- source alias `prj_blade_impact_water`
- source alias ID `358F2281`
- source bank `zmb_alcatraz.all`
- source FastFile `pluto_t6_full_game/zone/all/zm_prison.ff`
- source variant index 0
- raw Secondary state: non-inline serialized pointer, resolved only through native OAT.

No owner/source is inferred merely from the resolved name. It remains a genuine unresolved target identity relative to the accepted archive alias census.

## What is now closed

For the exact 215-FastFile / 116-bank archive population:

- complete serialized SndAlias structural population;
- complete physical sound-bank table population;
- complete nonzero SndAlias `assetId` -> physical-bank membership;
- source-supported `assetId == 0` authoring meaning;
- complete post-loader `Secondary` string identity for all 4,094 zero rows;
- complete classification of every non-empty Secondary target against the accepted alias census;
- physical-backed classification of those target families through the independently complete physical ID join.

## What remains open

The remaining blockers are now runtime semantics rather than unresolved serialized pointers:

- whether and when retail `t6mp.exe` follows `secondaryName`;
- recursion/fallback behavior;
- alias-list variant selection and `sequence` behavior;
- probability/randomization semantics;
- context selection;
- playback ordering;
- `stopOnPlay` behavior;
- volume/pitch/spatial/occlusion runtime conversion semantics;
- patch/base duplicate winner semantics for alias definitions;
- the two missing target identities above;
- exact byte equality of physical payload spans for duplicated physical IDs.

Do not call audio P8 until those layers are separately closed.
