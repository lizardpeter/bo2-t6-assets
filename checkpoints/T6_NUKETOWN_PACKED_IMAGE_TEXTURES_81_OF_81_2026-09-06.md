# T6 Nuketown packed GfxImage textures — 81 / 81 exact

The pointer-proven packed GfxImage population for `mp_nuketown_2020` is now completely source-closed against the retail Nuketown/DLC0/shared IPAK set.

## Canonical result

- pointer-proven aliases: **81**
- exact `(nameHash,dataHash)` matches: **81**
- dataHash-only fallbacks: **0**
- missing: **0**
- conflicts: **0**
- unique exact payloads: **81**

The seven aliases previously absent from the six-container census are all exact-pair members of retail `dlc0.ipak`; no generated, guessed, or similarly named substitute is used.

## Retail IPAK set

- `mp_nuketown_2020.ipak`
- `dlc0.ipak`
- `dlc0_load_mp.ipak`
- `mp.ipak`
- `base.ipak`
- `patch_mp.ipak`
- `so.ipak`
- `en_base.ipak`

## Proof artifact

- raw JSON bytes: **156,678**
- raw SHA-256: `21b8ec70bd03e08c83468e5d6125ea86998755d1a0eb0a126b0700cf04532e98`
- stored zlib+base64 bytes: **21,525**
- stored SHA-256 (without trailing newline): `a9e530aba48b041ff2eb0472698aa8fbbb5dcfb439ab7b5e6810498bbeaf9899`
- DLC0-backed alias rows: **34**

Every payload was actually range-read and retail-decompressed using raw/LZO/`0xCF` skip semantics, CRC29-checked, parsed as IWI27, and dimension-matched to the retained pointer-proven GfxImage. Unknown compression commands remain fail-closed.

This checkpoint supersedes the earlier 74/81 shared-IPAK closure for this 81-alias population.
