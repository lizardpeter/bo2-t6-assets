# T6 Nuketown shared-IPAK deterministic staging v1 — 2026-09-06

The exact six-IPAK packed-GfxImage census is now consumable as a reproducible retail texture-resource stage. `tools/t6_nuketown_shared_ipak_stage_v1.py` re-materializes every resolved payload directly from the user-provided R2 retail mirrors and refuses any identity drift.

## Result

- pointer-proven input aliases: **81**
- exact resolved aliases staged: **74**
- unresolved aliases retained open: **7**
- unique IWI payload files: **74**
- total exact IWI payload bytes: **13,030,568**
- staging manifest SHA-256: `47953ea9c74292865880dd7eacd0b023329e209b03f6e12df8e913db3a5d8b2a`
- successful GitHub Actions run: `34056681664`
- validation artifact id: `9996176192`
- artifact ZIP SHA-256: `efb8df5a50f1a81408f1681923323b69de22fb09c4dd93faa41e3e9eff59447c`

## Reproducibility boundary

The binary artifact is not canonical project state and does not need to be retained indefinitely. The committed census plus v2 HTTP-range IPAK reader deterministically reconstruct the exact 74 IWI files from R2. Each staged file is keyed by SHA-256 and is independently checked against:

1. the exact IPAK `(nameHash,dataHash)` entry retained in the census;
2. retail raw/LZO/`0xCF` block semantics;
3. IPAK CRC29;
4. the census payload SHA-256;
5. IWI27 parse identity;
6. retained GfxImage dimensions.

No filename similarity, nearest hash, same-name/wrong-data fallback, or visual matching is allowed.

## Forward use

This is now the source layer for the clean Nuketown texture rebuild. The seven aliases absent from all six supplied IPAKs remain open until exact inline/embedded/generated ownership is checked. The final scene must still preserve the v31-and-later shader contracts and pass the v25 release floor before promotion.
