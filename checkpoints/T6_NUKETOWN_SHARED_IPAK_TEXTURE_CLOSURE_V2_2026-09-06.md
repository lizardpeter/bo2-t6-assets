# T6 Nuketown shared-IPAK packed-image texture closure v2

The retail six-IPAK HTTP-range replay now source-closes **74 / 81** pointer-proven packed GfxImage aliases with **0 conflicts**.

- exact `(nameHash,dataHash)` payloads: **74**
- unique decompressed payloads: **74**
- unresolved after all supplied retail IPAKs: **7**
- `base.ipak` uses: **43**
- `mp.ipak` uses: **4**
- `mp_nuketown_2020.ipak` uses: **31**

Every promotion was decompressed with retail raw/LZO/0xCF-skip block semantics, independently CRC29-checked against the retained streamed dataHash, parsed as IWI27 and dimension-matched to the pointer-proven GfxImage record. No filename-similarity or same-name/wrong-data fallback is allowed.

## Exact retained proof

- raw census JSON bytes: **134,182**
- raw SHA-256: `455425f12cdddcc120b9969c6657a16f90c584a52db8ea14fc1c83328966cfae`
- stored zlib+base64 bytes: **19,705**
- stored SHA-256 (without trailing newline): `dc3cdea55a0980986227f9b60f578581fcc3559ee3b45d5d96bdada50d430f22`

## Still absent from these six IPAKs

- `~-gnt_2020_plastic_cream_col`
- `~-gnt_2020_plastic_yellow_col`
- `~-gnt_wood_fence`
- `nt_2020_concrete_pattern_02_n`
- `~-gnt_2020_concrete_pattern_02_c`
- `~~-gnt_2020_wall_small_cos-rg~b4bc9749`
- `~-gnt_2020_wall_orange_ext_c`

These seven are not promoted as missing source data yet. They remain open until inline/embedded/generated ownership is checked against the FastFile/OAT-retained image population.
