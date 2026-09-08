# T6 PC dedicated-server XAsset override proof v1

Date: 2026-09-07

## Status

The ordinary duplicate-XAsset precedence path is now instruction-byte-closed for one exact T6 **PC dedicated-server** build. This is strong PC-native corroboration for the remaining client duplicate problem, but it is deliberately **not** promoted to retail `t6mp.exe` authority.

Exact source pair recovered from the connected BO2 PC Server archive:

- `CoDMPServer_PC.exe`
  - bytes `13,711,872`
  - SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
  - PE32 / Intel i386
  - image base `0x00400000`
- `CoDMPServer_PC.map`
  - bytes `9,213,148`
  - SHA-256 `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`

Reusable verifier:

`tools/t6_pc_server_xasset_override_proof_v1.py`

Server-only OAT conflict projection:

`tools/t6_oat_conflict_pc_server_projection_v1.py`

## Exact MAP symbols

The exact linker MAP pins:

- `DB_GetZonePriority` → `0x00550230`
- `DB_OverrideAsset` → `0x00550410`
- `DB_LinkXAssetEntry` → `0x005504A0`
- `DB_SwapXAsset` → `0x0054F590`
- `DB_LoadXZone` → `0x00550F80`
- `DB_TryLoadXFileInternal` → `0x00551370`
- `DB_InitFastFileNames` → `0x00551A40`
- `DB_LoadXAssets` → `0x00556790`
- `DB_Thread` → `0x00556E80`
- `DB_LoadGraphicsAssetsForPC` → `0x00557190`
- `Com_LoadCommonFastFile` → `0x006BFCF0`
- `Com_LoadLevelFastFiles` → `0x006BFDF0`
- `Com_IsAddonMap` → `0x00760020`

The verifier gates both whole-file identities, every symbol VA above, exact function-range SHA-256 identities, and decisive instruction-byte windows.

## Exact function-range identities

- `DB_GetZonePriority` — `[0x00550230,0x00550410)` — 480 bytes — `591b7bb0cfbdbd21a429981aa8aa87bc8f9cb8a64e179203677000fd8479058f`
- `DB_OverrideAsset` — `[0x00550410,0x005504A0)` — 144 bytes — `a3d4e78ed92ca99fc821b21f429c5cadf00131174aab529de87243d574bb74a9`
- `DB_LinkXAssetEntry` — `[0x005504A0,0x00550D70)` — 2256 bytes — `1be0a50aedb4b5848552d75842d568f4fc2b0e800128f0fe86b002782e15072e`
- `DB_LoadXZone` — `[0x00550F80,0x005510C0)` — 320 bytes — `4b7751b245839090d45ef7c53c1ec894d3122dfc44c1e68d7c4ef356db964354`
- `DB_TryLoadXFileInternal` — `[0x00551370,0x00551A40)` — 1744 bytes — `774eb230e5739f047a50005ca0620336a0f997bd8a9e8211044a776ec0395d10`
- `DB_InitFastFileNames` — `[0x00551A40,0x00552050)` — 1552 bytes — `73491c8706e6ec340503f3e30a519f577fce6b2da5a68d3e31557f7b2f4e411d`
- `DB_LoadXAssets` — `[0x00556790,0x00556E80)` — 1776 bytes — `d6630efa78232bce6cafeb18b99cde569805bc35ad5f490b35b70900f665d55f`
- `DB_Thread` — `[0x00556E80,0x00557100)` — 640 bytes — `b3de0a6efab70e0b2447e1bf5d40958f908712096fb5fd3d056598068b837dda`
- `DB_LoadGraphicsAssetsForPC` — `[0x00557190,0x00557200)` — 112 bytes — `07810919599dd5fed847827ccc48905f37a40b24b55c59ac2e599331b52e3227`
- `Com_LoadCommonFastFile` — `[0x006BFCF0,0x006BFD80)` — 144 bytes — `a87e2354720ffc60dc36e2f60ac4dccbb27b5760176693fcfc7c67b9576a8986`
- `Com_LoadLevelFastFiles` — `[0x006BFDF0,0x006C0140)` — 848 bytes — `349e68516bbbe3a8c95f35d58f1346b7a4f83ad9a139cceb5ea805ad935ba84d`
- `Com_IsAddonMap` — `[0x00760020,0x00760100)` — 224 bytes — `275d1fe63b97345ff74f4e2379eb277efbb678ea1339423a8b4cd89b4a4d1dbd`

## Exact flag propagation

The exact executable closes this chain:

`XZoneInfo.allocFlags @ +0x04`

→ `DB_LoadXZone` queued-record `+0x40`

→ `DB_Thread` passes queued `+0x40` as the flags argument

→ `DB_TryLoadXFileInternal` writes that value to `g_zoneNames[zoneIndex].flags`

→ `DB_OverrideAsset` reads the same field.

`XZoneInfo` stride on this path is exactly 12 bytes: name at `+0`, allocFlags at `+4`, freeFlags at `+8`.

## Exact ordinary duplicate rule

`DB_OverrideAsset` masks both stored zone flags with:

`0x3FFFFFFF`

then obtains both priorities through `DB_GetZonePriority` and returns:

`newPriority >= existingPriority`

`DB_LinkXAssetEntry` tests that result. On the true replacement path it relinks the override chain, calls exact MAP symbol `DB_SwapXAsset`, then swaps the two `zoneIndex` bytes. Thus the stable primary hash entry acquires the winning zone payload/zone identity while the displaced payload remains in the override chain.

This is not a simple unconditional last-loaded-wins rule.

## Exact MP load flags in this PC server build

`DB_InitFastFileNames` constructs `common_mp` and `patch_mp` from the exact base strings plus `_mp` suffix.

Exact call-site values:

- `common_mp`
  - `Com_LoadCommonFastFile`
  - allocFlags `0x00000080`
  - server priority **54**
- `patch_mp`
  - `DB_LoadGraphicsAssetsForPC`
  - allocFlags `0x00000002`
  - server priority **65**
- ordinary built-in MP map, including `mp_nuketown_2020`
  - `Com_LoadLevelFastFiles` non-addon branch
  - allocFlags `0x00008000`
  - server priority **57**

`Com_IsAddonMap` tests only the exact three-byte prefixes `so_` and `zo_` on this path. `mp_nuketown_2020` matches neither, so its built-in-map `0x8000` row is direct for this fixture.

Therefore, on this exact server build:

- patch vs common: `65 > 54` → patch wins regardless of load order;
- patch vs ordinary built-in map: `65 > 57` → patch wins regardless of load order.

## Correction to old OpenBO2 lineage assumptions

The exact PC server `DB_GetZonePriority` implementation is **not** byte/constant equivalent to the previously quarantined OpenBO2 table. The exact server mask is `0x3FFFFFFF`, not the old diagnostic `0x17FFFFFF`, and several priority values differ materially.

Accordingly, the older OpenBO2 table must not be used as a PC-server priority oracle. Its earlier map/patch predictions were useful falsifiable lineage only and are superseded for this exact server build by the proof above.

## Projection onto current Nuketown native conflicts

Source native conflict census:

- 60 unresolved relations total;
- 58 divergent parent-owned child Techniques;
- 2 missing-parent TechniqueSet owner gaps;
- 272 distinct affected ordinary Materials;
- 0 winners selected by the authoritative OAT census.

Applying only this exact PC-server rule as a separate server projection gives:

- **58 / 58** divergent conflicts → server predicts `patch_mp` / `/tmp/patch_out`;
- **2 / 2** missing-parent conflicts remain owner-universe gaps;
- 0 unmapped server zone classes;
- 0 server priority ties;
- **0 retail-client winners promoted**.

The server projection is intentionally kept outside the production retail-client census.

## Proof boundary

Authoritative:

- exact behavior described above for SHA-pinned `CoDMPServer_PC.exe` + exact linker MAP;
- exact server flags/priorities for `common_mp`, `patch_mp`, and ordinary built-in MP maps on the proved paths;
- exact server duplicate replacement algorithm for the ordinary branch.

Not authoritative:

- that retail `t6mp.exe` has identical function bytes, priority table, flag mask, load constants, or special cases;
- selecting a production retail Material/TechniqueSet/Technique winner from this server proof alone;
- the two missing-parent TechniqueSet owner gaps;
- any renderer-global `shadowoverlay` consumer path, which remains a retail-client renderer proof task.

Retail-client promotion still requires either the exact SHA-pinned `t6mp.exe` static path or an independently genuine retail-client runtime duplicate-chain observation.