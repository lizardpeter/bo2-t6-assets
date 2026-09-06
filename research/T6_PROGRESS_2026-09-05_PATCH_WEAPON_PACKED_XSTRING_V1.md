# T6 patch WEAPON packed-XString checkpoint v1

**Track:** non-map assets  
**Branch:** `reversal/nonmap-assets`  
**Date:** 2026-09-05  
**Goal:** close final MP weapon-layer precedence without guessing the single anonymous `patch_mp` WEAPON identity.

## State entering this checkpoint

The shared third-person player-animation layer is already structurally usable across all 24 selector profiles exercised by the 54 directly proven `common_mp` player-facing weapon roots. The remaining blocker is not SEAL6 skeleton compatibility. It is final retail weapon identity/precedence:

- `common_mp`: 54 directly proven player-facing roots;
- `common_patch_mp`: 81 named WEAPON overrides, all names already present in `common_mp`;
- `patch_mp`: exactly one top-level WEAPON XAsset, still unnamed under the project proof standard.

The existing precedence resolver intentionally treats an unnamed later WEAPON as a global finalization blocker. That policy remains unchanged.

## Structural WEAPON probe v1 retained unchanged

`tools/t6_weapon_xasset_structural_probe_v1.py` remains the frozen first structural gate. It recognizes the recovered 716-byte PC32 `WeaponVariantDef`, validates known pointer/boolean invariants, requires a valid direct `WeaponDef` selector before cardinality binding, rejects shifted lookalikes, and fails closed on ambiguity.

Its packed-name boundary was deliberate: a packed `szInternalName` produced `unresolved-packed-name-pointer` rather than a guessed nearby name.

## Loader-model correction

The next task had previously been described as "TEMP-block allocation replay." That description is too broad and is now corrected.

Pinned OpenAssetTools source at commit `2ca512abe7cb82d70a94d5ad7846043c3978862d` provides independent corroboration for the T6 loader contract:

- `src/ZoneCode/Game/T6/T6_Commands.txt`
  - T6 uses 32-bit zone pointers;
  - `XFILE_BLOCK_TEMP` is the default TEMP block;
  - `XFILE_BLOCK_VIRTUAL` is the default normal block.
- `src/ZoneCode/Game/T6/XAssets/WeaponVariantDef.txt`
  - `WeaponVariantDef` is assigned to `XFILE_BLOCK_TEMP`;
  - `szInternalName` is an XString;
  - `weapDef` is reusable.
- `src/ZoneCodeGeneratorLib/Generating/Templates/ZoneLoadTemplate.cpp`
  - the TEMP asset root is allocated while the TEMP block is active;
  - member loading for an asset pushes the default normal block.
- `src/ZoneLoading/Loading/ContentLoaderBase.cpp`
  - `LoadXString(false)` allocates FOLLOWING strings in the current block;
  - packed strings use normal offset-to-pointer conversion.
- `src/ZoneLoading/Zone/Stream/ZoneInputStream.cpp`
  - TEMP block offsets are restored on pop;
  - normal block offsets persist.

Therefore the exact correction is:

> `WeaponVariantDef` root allocation is TEMP, but `WeaponVariantDef.szInternalName` is loaded under the default normal VIRTUAL block. A packed internal-name XString is therefore a persistent VIRTUAL block-offset problem, not a TEMP alias problem.

This upstream loader behavior is corroborative implementation evidence. Retail T6 bytes remain the authority for any promoted asset identity.

## New strict VIRTUAL-front mapper

`tools/t6_virtual_front_map_v1.py` now replays only the already-proven VIRTUAL allocations before the XAsset body stream:

1. ScriptString pointer array;
2. FOLLOWING ScriptString payloads;
3. destination-only 4-byte alignment;
4. dependency pointer array;
5. FOLLOWING dependency strings;
6. destination-only 4-byte alignment;
7. 8-byte XAsset array.

Physical source offsets are never alignment-rounded.

A packed VIRTUAL pointer is classified as one of:

- exact front XString start;
- front XString interior;
- XAsset header slot;
- other byte inside XAsset/front allocation;
- alignment hole;
- later VIRTUAL allocation;
- non-VIRTUAL block.

Only an exact allocation-start match to a replayed FOLLOWING front string is eligible for identity promotion.

Regression: `tools/test_t6_virtual_front_map_v1.py`.

## WEAPON structural probe v2

`tools/t6_weapon_xasset_structural_probe_v2.py` layers the front mapper on top of v1 without weakening any v1 structural/cardinality gate.

For a v1 candidate whose name status is `unresolved-packed-name-pointer`, v2:

1. independently builds the VIRTUAL front map;
2. cross-checks asset count and asset-body raw offset against the raw XAsset parser;
3. decodes the exact packed `szInternalName` pointer;
4. promotes the name only if it is `exact-front-xstring`;
5. leaves every later VIRTUAL target unresolved.

Regression: `tools/test_t6_weapon_xasset_structural_probe_v2.py`.

The regression proves both directions:

- an exact packed pointer to a replayed front `peacekeeper_mp` fixture becomes `exact-packed-front-xstring`;
- an otherwise valid block-5 pointer after the XAsset array stays `unresolved-packed-name-pointer` with classification `later-virtual-allocation`.

The string in that regression is synthetic test data. It is **not** evidence that the retail `patch_mp` WEAPON is Peacekeeper.

## Retail boundary remains unchanged

Retained retail `patch_mp` evidence remains:

- expanded bytes: `14,713,756`;
- expanded SHA-256: `1bd82b0e99fcea3a9cb1c2342634f1da0d699b3fdadfa9f7c7fe15595952a7b9`;
- top-level WEAPON count: exactly `1`;
- literal `peacekeeper_mp`: absent from the expanded stream under the existing proof;
- exact `WeaponVariantDef.szInternalName`: still intentionally unclaimed.

No precedence blocker has been relaxed and no anonymous patch WEAPON has been renamed.

## Next target

If the retail packed `szInternalName` lands in the proven front, v2 closes it immediately. If it lands after the XAsset array, the correct next task is **later VIRTUAL asset-body allocation replay**.

That replay must be built incrementally from exact serialized loader/walker behavior, preserve per-block destination alignment separately from physical source movement, and promote an XString only when an exact allocation identity maps the packed VIRTUAL offset to a unique retained source string.

Do not return to string-proximity heuristics and do not treat TEMP reset behavior as the internal-name ownership mechanism.
