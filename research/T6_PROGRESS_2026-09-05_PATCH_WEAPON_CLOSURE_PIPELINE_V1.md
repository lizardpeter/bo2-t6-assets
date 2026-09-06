# T6 patch WEAPON closure pipeline v1

**Track:** non-map assets  
**Branch:** `reversal/nonmap-assets`  
**Date:** 2026-09-05

## Objective

Turn the single still-anonymous retail `patch_mp` WEAPON into an exact named player-animation selector layer, then clear the final global weapon-precedence blocker without relaxing the proof standard.

## Retained retail identity gates

`t6_patch_weapon_closure_v1.py` hard-codes the retained `patch_mp` identities:

- encrypted `patch_mp.ff`: **3,638,592 bytes**
- SHA-256: `459077cda8e4a1457f7ee7d8f6c5e0abf30f41767a21ff6744df6a4307cbce1e`
- expanded stream: **14,713,756 bytes**
- expanded SHA-256: `1bd82b0e99fcea3a9cb1c2342634f1da0d699b3fdadfa9f7c7fe15595952a7b9`
- XAsset count: **1,764**
- top-level WEAPON count: **1**

These values are not user-overridable in retail closure mode.

## One-command closure

New tool:

`tools/t6_patch_weapon_closure_v1.py`

It accepts either the exact retail FF or the exact retained expanded stream.

With `--fastfile`, it performs:

1. exact FF size/hash verification;
2. deterministic expansion through `t6_pc_fastfile_expand_v1.py`;
3. exact expanded size/hash verification;
4. raw XAsset inventory;
5. structural WeaponVariantDef probe v1;
6. packed-front XString enrichment through probe v2;
7. exact closure evaluation;
8. normalized `patch_mp` selector-layer emission only on success;
9. optional surgical precedence-spec promotion;
10. optional rerun of `t6_weapon_playeranim_precedence_v1.py`.

With `--expanded`, the exact expanded identity gate is still mandatory.

## Exact closure gates

A selector layer is emitted only if all of these are true:

- retained expanded identity is exact;
- XAsset count is exactly 1,764;
- WEAPON count is exactly 1;
- there is exactly one `exact-by-single-inline-weapon-cardinality` binding;
- the bound WeaponVariantDef name is exact under either:
  - `exact-inline-following`, or
  - `exact-packed-front-xstring`;
- its direct WeaponDef prefix status is exactly `exact-direct-weapdef-prefix`;
- the extracted selector contains both `weaponclass` and `playerAnimType`.

If any condition fails, the closure result is `blocked`, no promotable selector layer is emitted, and precedence is not modified.

## Precedence normalization

The structural probe's exact direct selector status is retained as provenance.

The generated precedence-compatible row uses:

`selectorStatus: exact`

This is one of the exact statuses already accepted by `t6_weapon_playeranim_precedence_v1.py`. It is emitted only after the structural status has passed the stricter `exact-direct-weapdef-prefix` gate.

The generated layer format is the existing normal format:

`t6-weapon-playeranim-selector-layer-v1`

No parallel patch-only selector schema was introduced.

## Surgical precedence promotion

`promote_patch_layer_in_spec()` requires the incoming spec to contain exactly one `patch_mp` layer with:

`unknownWeaponAssetCount == 1`

On exact closure it changes only:

- `patch_mp.selectorManifest`
- `patch_mp.unknownWeaponAssetCount`: `1 -> 0`

All other layer/spec content is deep-copied unchanged. The CLI also requires the promoted spec to remain in the same directory as the original so existing relative layer references keep identical semantics.

## Regression coverage

New regression:

`tools/test_t6_patch_weapon_closure_v1.py`

It proves:

- exact synthetic structural closure produces a standard exact selector row;
- an unresolved packed internal name remains blocked;
- multiple exact cardinality bindings remain blocked;
- a non-exact direct selector remains blocked;
- XAsset-count mismatch remains blocked;
- WEAPON-count mismatch remains blocked;
- precedence promotion changes only the two intended `patch_mp` fields;
- a noncanonical prior unknown count is rejected;
- artifact verification rejects both size and SHA mismatches.

The synthetic regression weapon is `fixture_weapon_mp`. It does not encode any retail identity assumption.

`.github/workflows/nonmap-weapon-regressions.yml` now runs the closure regression alongside the VIRTUAL-front and structural-probe regressions.

## Peacekeeper remains an expectation, not a promoted identity

Independent/public data and retained patch metadata make Peacekeeper a useful fingerprint target, but `t6_patch_weapon_closure_v1.py` does not consult any of those sources.

In particular, the tool does not assume that the anonymous record is Peacekeeper and does not use UI weapon category to infer `weaponClass` or `playerAnimType`.

A public T6 dump currently suggests that `peacekeeper_mp` would have `weaponClass=rifle` and `playerAnimType=default`; that may be useful for later comparison only after the retail bytes independently name the record.

## Remaining boundary

The File Library retained the original August 30 source-set manifest proving that `shared/patch_mp.ff` was supplied, but the binary itself is not exposed through semantic File Library retrieval or the GitHub source-container policy.

Therefore the anonymous retail WEAPON is **not renamed in this checkpoint**.

The remaining closure is now deterministic:

- run the exact retained `patch_mp.ff` or expanded stream through `t6_patch_weapon_closure_v1.py`;
- if probe v2 resolves the packed name in the proven VIRTUAL front, final named precedence can be promoted immediately;
- if v2 returns `later-virtual-allocation`, the only remaining decoder work is later VIRTUAL asset-body allocation replay.

Do not weaken the unknown-later-WEAPON blocker before exact closure.
