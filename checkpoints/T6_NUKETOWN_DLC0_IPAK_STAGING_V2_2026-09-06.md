# T6 Nuketown DLC0/shared IPAK deterministic staging v2 — 2026-09-06

The canonical `81 / 81` packed-GfxImage closure is now fully materialized through the range-backed retail IPAK reader.

## Result

- pointer-proven aliases: **81**
- exact resolved aliases staged: **81**
- unresolved aliases: **0**
- unique exact IWI payload files: **81**
- total exact IWI payload bytes: **13,369,792**
- staging manifest SHA-256: `58819b447e041b919552cf3d99f25e18e41aecb931c45d75775f4c318bc7946b`
- successful GitHub Actions run: `34057220382`
- validation artifact id: `9996327280`
- artifact ZIP SHA-256: `d10bcc3acfff3e42fb64d22071420689f88cb2c91deb2ebf586426c30fd87ba6`

## Canonical source proof

Input identity proof:

`manifests/maps/mp_nuketown_2020/T6_NUKETOWN_DLC0_IPAK_PACKED_IMAGE_ALIAS_CLOSURE_V3.json.zlib.b64`

The staging run requires that canonical proof to exist and then independently re-reads every recorded exact `(nameHash,dataHash)` entry from the retail R2 mirrors. Each result must pass the v2 raw/LZO/`0xCF` container replay, CRC29 identity, retained payload SHA-256, IWI27 parse and retained GfxImage dimensions.

No filename similarity, same-name wrong-data fallback, visual matching, nearest hash or generated substitute is permitted.

## Rebuild use

The 81 IWI payloads are a reproducible source layer and are not committed as duplicate retail binary blobs. The exact files can be reconstructed on demand from the canonical proof and the eight retail IPAKs. This stage is now suitable as input to the clean Nuketown material/resource binding pass.
