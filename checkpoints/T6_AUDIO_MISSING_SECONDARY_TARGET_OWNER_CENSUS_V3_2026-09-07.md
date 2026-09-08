# T6 audio missing Secondary target owner census v3 — 2026-09-07

## Status

The two `secondaryName` targets that remained absent from the complete accepted SndAlias census are now proven to have **no native SndAlias Name-row owner anywhere inside the exact 215-FastFile archive SoundBank universe**.

This is an owner-absence result only. It does not mean the serialized references are dead, unreachable, unused, or ignored by the retail runtime.

## Targets

1. `wpn_wa2000_bass_swt_silencer`
   - T6 sound hash: `646B2B38`
   - serialized Secondary source already proven:
     - source alias `wpn_metalstormsnp_silencer_fire_plr`
     - `common_mp.ff`
     - SndBank `mpl_common.all`

2. `zmb_tomahawk_sparks`
   - T6 sound hash: `39797FA4`
   - serialized Secondary source already proven:
     - source alias `prj_blade_impact_water`
     - `zm_prison.ff`
     - SndBank `zmb_alcatraz.all`

## Exact archive-wide proof

Workflow commit:

`03bc66050ebbd66207ba00fe9e0b84f6598d994e`

Run:

`34183229807`

Artifact:

- ID `10039633709`
- name `T6_MISSING_SECONDARY_TARGET_OWNER_CENSUS_V3`
- digest `sha256:26d08e0d96eb4b3eb4c26176ca802c8424d492a1cb6f0e9f1720b89e8faa7395`
- full result JSON SHA-256 `d733ec593a82f69f9dcee723c83c6931eb1bedd79c2b43a676aa47dc53a04682`

Archive coverage:

- **215 / 215 FastFiles covered**
- **152** FastFiles are covered by the retained fail-closed structural proof of zero validated SndBank sections
- **63 / 63** structurally proven SoundBank-bearing FastFiles were natively dumped by pinned OAT
- all 63 native FastFiles:
  - passed archive ZIP CRC verification
  - matched their retained exact FastFile SHA-256
  - were materialized under their exact retail FastFile basename before native loading
  - returned OAT rc `0`
  - emitted at least one SoundBank alias CSV
- **65** native SoundBank alias CSV files total
- **445,664** native alias rows total

The **445,664 native rows exactly equal the complete serialized alias-occurrence count** from the independent 215-FastFile structural census.

Target Name-row results:

- `wpn_wa2000_bass_swt_silencer`: **0 owners**
- `zmb_tomahawk_sparks`: **0 owners**

Therefore both names are genuine dangling `secondaryName` dependencies within this exact archive SoundBank universe, rather than failures of the raw packed-pointer resolver or accepted-alias structural census.

## Why v1 and v2 are invalid as owner evidence

Two earlier attempts failed because the native workflow changed the FastFile filename before passing the bytes to OAT.

### v1

The workflow wrote each exact FastFile payload under numeric names such as:

`000.ff`

The first failing example contained the bytes of `code_post_gfx.ff`, but OAT received the zone as `000.ff`.

### v2

The workflow correctly narrowed native dumping to the 63 FastFiles whose structural census proved at least one SndBank section, but still wrote them under numeric names such as:

`048.ff`

The concrete failure appeared on the bytes of `mp_magma.ff`, supplied to OAT as `048.ff`.

Neither failed run is valid positive or negative asset evidence.

### v3 correction

The v3 workflow uses:

```text
retail_name = PurePosixPath(sourceZipPath).name
```

and materializes each FastFile under that exact retail basename (`common_mp.ff`, `mp_magma.ff`, `zm_prison.ff`, etc.) before native loading.

With that correction:

- unit gate passed
- all 8 native shards passed
- aggregate passed

This filename requirement is now part of the durable native FastFile proof boundary.

## Relationship to zero-asset Secondary closure

The prior v2 closure established:

- 4,094 zero-asset alias occurrences
- 1,470 nonempty resolved Secondary occurrences
- 44 unique Secondary names
- 1,334 / 1,334 formerly opaque non-inline Secondary pointers resolved by native OAT
- 24 / 44 unique targets have at least one physically backed direct target variant
- 1,352 / 1,470 Secondary occurrences point to a target family with at least one physically backed direct variant
- only the two names in this checkpoint were absent from the complete accepted alias census

This v3 owner census closes the question of whether those two absences were merely parser misses elsewhere in the archive: they were not.

## Durable files

Machine-readable summary:

`manifests/audio/T6_MISSING_SECONDARY_TARGET_OWNER_CENSUS_V3.json`

Committed native census workflow:

`.github/workflows/t6_oat_missing_secondary_target_owner_census_v1.yml`

Native CSV target scanner:

`tools/t6_oat_alias_csv_target_census_v1.py`

Regression:

`tools/test_t6_oat_alias_csv_target_census_v1.py`

## Proof boundary

Authoritative statement:

> Neither `wpn_wa2000_bass_swt_silencer` nor `zmb_tomahawk_sparks` has a native SndAlias `Name` owner inside the exact 215-FastFile archive SoundBank universe tested here.

Not established:

- whether either name is supplied by a different install revision, language/DLC corpus, or external runtime source;
- whether retail playback attempts to resolve a dangling Secondary and then falls back;
- whether a missing Secondary is ignored, warned, or changes source-alias playback;
- whether the names are intentionally historical compatibility references;
- whether either edge is reachable in gameplay;
- retail `t6mp.exe` Secondary playback semantics.

The serialized Secondary edges remain real source data and must be preserved by exporters/reconstruction even when the target Name owner is absent from this archive.
