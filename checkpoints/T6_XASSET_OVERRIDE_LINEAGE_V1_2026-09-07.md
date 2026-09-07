# T6 XAsset duplicate/override lineage v1 — non-authoritative

Date: 2026-09-07

## Purpose

The native OAT Material/TechniqueSet census has encountered real duplicate XAsset names whose physical payloads differ between zones. The proof boundary forbids resolving those duplicates by guessed load order or generic "patch wins" assumptions.

This checkpoint records a concrete **T6-native lineage implementation** found in OpenBO2, but deliberately does **not** promote it to retail authority until its relevant routines are tied to the project's exact SHA-pinned retail executable or independently observed in a genuine T6 runtime.

Source lineage repository:

- repository: `builtbyxeno/OpenBO2`
- inspected commit: `a64812d21946baf710cec7fa26b98ad0d193903b`
- file: `src/code/src_noserver/database/db_registry.cpp`

OpenBO2's own README describes the project as a barebones/open-source Black Ops II recreation and does not provide a binary-equivalence guarantee. Therefore the code below is **strong branch-selection evidence, not a retail proof source by itself**.

## Recovered lineage structure

The T6 `XAssetEntry` represented by this source has:

- the active/hash-chain asset;
- `zoneIndex`;
- `nextHash`;
- `nextOverride`.

Enumeration code treats the hash-table entry as the primary asset and follows `nextOverride` only when overrides are explicitly requested.

`DB_FindXAssetEntry(type, name)` searches only the primary hash chain and returns the matching primary `XAssetEntry` directly.

This strongly indicates that the hash-table entry represents the currently selected/active asset, while displaced duplicates are retained behind it through `nextOverride`.

## Zone priority function

The lineage `DB_GetZonePriority(zone)` maps the masked zone flag to a priority value:

| zone flag | priority |
|---:|---:|
| `0x04000000` | 58 |
| `0x10000000` | 50 |
| `0x02000000` | 8 |
| `0x00400000` | 62 |
| `0x00800000` | 3 |
| `0x01000000` | 53 |
| `0x00200000` | 12 |
| `0x00040000` | 57 |
| `0x00080000` | 7 |
| `0x00020000` | 6 |
| `0x00004000` | 55 |
| `0x00008000` | 5 |
| `0x00010000` | 56 |
| `0x00000001` | 51 |
| `0x00000002` | 1 |
| `0x00000004` | 63 |
| `0x00000008` | 13 |
| `0x00000010` | 59 |
| `0x00000020` | 9 |
| `0x00002000` | 4 |
| `0x00000800` | 10 |
| `0x00001000` | 54 |
| `0x00000400` | 60 |
| `0x00000080` | 11 |
| `0x00000100` | 52 |
| `0x00000200` | 2 |
| `0x00000040` | 61 |

Unknown flags assert/fail in the lineage implementation rather than receiving a fallback priority.

## Override comparison

The lineage `DB_OverrideAsset(newZoneIndex, existingZoneIndex, type)` computes:

```text
newPriority = DB_GetZonePriority(g_zoneNames[newZoneIndex].flags & 0x17FFFFFF)
existingPriority = DB_GetZonePriority(g_zoneNames[existingZoneIndex].flags & 0x17FFFFFF)
return newPriority >= existingPriority
```

The `type` argument is present but does not alter the comparison in the inspected implementation.

The use of `>=` means equal-priority later candidates would be allowed to replace the current primary under this lineage algorithm.

## Primary replacement behavior

When `DB_LinkXAssetEntry(newEntry, allowOverride)` finds an existing same-type/same-name asset and `DB_OverrideAsset(new, existing)` returns true, the lineage implementation:

1. inserts `newEntry` immediately behind `existingEntry` in the `nextOverride` chain;
2. swaps the XAsset payloads of `newEntry` and `existingEntry`;
3. swaps their `zoneIndex` values;
4. returns `existingEntry`.

Consequently the stable primary hash entry remains in place, but after the swap it owns the **new higher/equal-priority zone's payload and zone identity**. The displaced former primary is retained in the override chain.

This is materially different from a simplistic "last file in load order wins" model: selection is explicitly mediated by a zone-priority comparison.

## Lower-priority insertion behavior

When the new duplicate cannot override the current primary, the lineage implementation walks `existingEntry->nextOverride` until it reaches the first displaced entry that the new zone *can* override, then inserts the new entry at that point.

Therefore the override chain is maintained in effective zone-priority order rather than mere discovery order.

## Default/stub behavior

The same routine contains separate paths for:

- comma-prefixed stub assets;
- default-asset pool entries (`zoneIndex == 0`);
- delayed cloning when override is not immediately permitted;
- asset types that are forbidden from ordinary duplicate override.

Those branches matter for universal XAsset precedence and should not be collapsed into the ordinary non-default duplicate case.

## Why this matters to the current native shader census

The provenance-aware OAT census correctly fails when a same-name TechniqueSet is physically present in more than one zone and its child Technique identities differ. Examples encountered in current retail work include divergent duplicate parent/child families between map and patch roots.

The lineage code provides a concrete candidate algorithm for selecting the runtime active duplicate:

```text
zone flags -> DB_GetZonePriority -> DB_OverrideAsset -> DB_LinkXAssetEntry
```

If this chain is source-closed against the exact retail executable/runtime, the census can stop requiring byte-identical duplicate parent TechniqueSets and can instead select the exact runtime winner while retaining the full displaced override chain as evidence.

## What is still needed before authority

At least one of the following must close the lineage to retail T6:

1. recover the exact SHA-pinned `t6mp.exe` bytes and prove the relevant routines/static tables directly;
2. recover an exact disassembly/function fixture from that executable covering `DB_GetZonePriority`, `DB_OverrideAsset`, and the decisive `DB_LinkXAssetEntry` branches;
3. produce a genuine runtime dump that exposes same-name duplicate XAsset zone ownership and matches the predicted chain ordering on a case with divergent physical payloads.

The project's historical exact MP executable identity remains:

- bytes: `12,850,328`
- SHA-256: `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`
- image base used by existing static proof tooling: `0x00400000`

Its raw binary is not currently retrievable from the public full-game ZIP, connected Drive, or indexed File Library.

## Proof boundary

**Do not use this checkpoint to select a retail duplicate winner yet.**

Permitted use:

- branch selection;
- designing a fail-closed retail validator;
- identifying the exact functions/zone metadata needed from a future executable/runtime capture;
- predicting an outcome that must then be independently tested.

Forbidden use until retail closure:

- declaring map or patch the owner of a divergent duplicate solely from this source;
- changing the native census from fail-closed to precedence-selected;
- treating OpenBO2's zone-priority table as proof of the exact SHA-pinned retail executable.
