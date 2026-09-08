# T6 audio zero-asset / Secondary closure v1 — 2026-09-07

## Scope

This checkpoint records the complete 215-FastFile structural census of `SndAlias.assetId == 0`, the pinned-T6-OAT authoring boundary for that state, and the first exact join of inline `Secondary` names back into the complete alias/physical universe.

It deliberately does **not** claim retail runtime playback semantics for `Secondary`, packed pointer resolution, recursive alias playback, fallback behavior, or zone-precedence selection.

## Source population

The retained all-FastFile SndAlias census covers exactly:

- 215 / 215 FastFiles green;
- 445,664 serialized SndAlias occurrences;
- 18,103 unique alias IDs;
- 47,956 semantic variants;
- 441,570 nonzero `assetId` occurrences;
- 4,094 zero `assetId` occurrences.

The independent physical join proves all 24,481 unique nonzero asset IDs, covering all 441,570 nonzero occurrences, exist in the 116-bank physical SABS/SABL universe.

Source JSON hashes:

- zero census: `6a05d394c591c074570751e68429c47ba6f801701826199780994326ae125fed`
- complete alias census: `5da7ed9c5cd5ea4c2cd69213438103883f6c804db678db6496f781ed86713f5d`
- complete alias -> physical join: `e7bd3a6cb3cc2e9060d540b5abc2e37085c106beaab4379a167431b7d1a1a6c4`

## Complete zero-asset population

The dedicated parity-gated zero census completed green in workflow run `34178852305`.

Artifact:

- `T6_SNDALIAS_ZERO_ASSET_ALL_FASTFILE_V1`
- artifact ID `10038238861`
- artifact digest `sha256:12be3d7b1fbfacdc0a46fc8912355721815202a34c720f14ef5d932b09019483`
- aggregate JSON SHA-256 `6a05d394c591c074570751e68429c47ba6f801701826199780994326ae125fed`

Exact zero-asset findings:

- 4,094 zero-asset occurrences;
- 429 unique alias IDs contain at least one zero variant;
- 294 of those alias IDs are zero-only;
- 135 alias IDs are mixed and contain both zero and nonzero serialized variants;
- 473 unique zero semantic variants;
- 393 / 429 zero-bearing alias IDs have a validated inline name;
- zero variants occur in 37 FastFiles / accepted SndBank sections;
- all 4,094 have `file_ptr == NULL`;
- all 4,094 have an empty inline asset filename;
- all 4,094 have `subtitle_ptr == NULL` and no inline subtitle;
- 2,624 have `secondary_ptr == NULL`;
- 136 have an inline serialized `Secondary` string;
- 1,334 have a non-null non-inline `secondary_ptr` value that remains unresolved at this proof stage.

The 135 mixed alias IDs are important: zero is a **variant-level state**, not necessarily a property of the entire alias family.

## Source-closed authoring meaning of `assetId == 0`

Pinned OpenAssetTools T6 source at commit:

`9dca965366541504b71fa8cfb7ac049cb9b717e1`

provides a narrow but strong authoring boundary:

1. a `SndAlias` is zero-initialized;
2. only a non-empty `FileSource` assigns both `assetFileName` and `assetId = SND_HashName(assetFileName)`;
3. `Secondary` is loaded independently from the `Secondary` column;
4. the T6 soundbank writer adds physical SABS/SABL audio only when both `assetFileName` and `assetId` are nonzero.

Therefore this project may now call `assetId == 0`:

> **no direct FileSource assigned to that serialized alias variant in the source-supported T6 authoring model**

It must **not** be called “missing audio”.

This still does not prove what retail `t6mp.exe` does when such a variant is selected.

## Exact inline Secondary join

Reusable proof tooling:

- `tools/t6_sndalias_zero_secondary_join_v1.py`
- `tools/test_t6_sndalias_zero_secondary_join_v1.py`
- `.github/workflows/t6_sndalias_zero_secondary_join_v1.yml`

Commits:

- joiner `b4a97647cec0d44c16d1e42209733f1016f13938`
- regression `2f5836c78db6e3878e99829e91aca703a4670493`
- retained-artifact workflow `69f1312bbe1dc18d35ecc6b548dfb8b8adda2190`

Workflow run `34180511888` completed fully green.

Artifact:

- `T6_SNDALIAS_ZERO_SECONDARY_JOIN_V1`
- artifact ID `10038729493`
- artifact digest `sha256:beec9e32ec792160c7a8501de5a69cd23604914effbfe918852836e12db59ca5`
- JSON SHA-256 `788c8fa169a203517bb813a30e945e9fe089d20f665297367ce84b2be3f50214`

The join hashes each inline `Secondary` with the exact T6 `SND_HashName` algorithm, joins that ID against the complete accepted alias census, and only marks a target as having a physically backed variant if the independent 24,481 / 24,481 alias-to-bank join is supplied and green.

Exact result:

- 136 inline Secondary occurrences;
- 26 unique inline Secondary names;
- 12 / 26 unique names target an alias family with at least one nonzero, physically matched asset variant;
- 68 / 136 occurrences target a family with at least one nonzero, physically matched asset variant;
- 4 unique targets are nonzero-only, accounting for 57 occurrences;
- 8 unique targets are mixed zero/nonzero, accounting for 11 occurrences;
- 13 unique targets are zero-only, accounting for 67 occurrences;
- 1 unique target / occurrence is absent from the complete accepted alias census.

This is **not** evidence that runtime always plays Secondary. It is only an exact dependency classification for the inline-serialized subset.

## Single unresolved inline target

The lone inline `Secondary` name absent from the accepted T6 alias census is:

`wpn_wa2000_bass_swt_silencer`

Exact source row:

- source alias `wpn_metalstormsnp_silencer_fire_plr`
- source alias ID `A4BDB640`
- Secondary hash `646B2B38`
- source FastFile `pluto_t6_full_game/zone/all/common_mp.ff`
- source SndBank `mpl_common.all`

Historical BO1/T5 soundalias data contains `wpn_wa2000_bass_swt_silencer` as a real alias identity. That is retained only as lineage/search guidance. It does not prove the T6 runtime owner, target availability, or playback behavior.

## Remaining exact blocker inside this branch

The largest unresolved zero-asset relationship is now finite:

**1,334 non-null non-inline `secondary_ptr` occurrences.**

These must not be resolved by treating the raw serialized 32-bit values as strings, addresses, hashes, or guessed backreferences.

The preferred next proof path is a native loaded-SndBank dump using pinned T6 OAT, because after real loader pointer/backreference fixups `alias.secondaryName` is an actual resolved C string. A native dump can then be compared row-for-row with the raw zero census without inventing pointer semantics.

## Durable machine result

The compact retained target table and exact source/artifact provenance are stored in:

`manifests/audio/T6_SNDALIAS_ZERO_SECONDARY_CLOSURE_V1.json`

Commit:

`4a7d86a27001b190ecfca0d9e7605166447041ed`

## Proof boundary

Closed:

- complete 4,094-row zero-asset structural population for this exact 215-FastFile archive;
- no-direct-FileSource authoring meaning from pinned T6 OAT;
- exact classification of all 136 inline Secondary rows;
- physical-backed target classification only through the independently complete alias-to-bank join.

Open:

- 1,334 non-inline Secondary pointer resolutions;
- the one inline WA2000 target absent from the accepted T6 alias census;
- retail runtime use of `secondaryName`;
- recursive/fallback/sequence rules;
- variant-selection semantics;
- patch/base duplicate winner semantics where relevant;
- exact payload-byte equality for duplicated physical bank IDs.
