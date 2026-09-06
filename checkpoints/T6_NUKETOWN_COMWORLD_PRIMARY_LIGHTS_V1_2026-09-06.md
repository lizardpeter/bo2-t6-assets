# T6 Nuketown ComWorld primary-light closure v1 — 2026-09-06

This checkpoint source-closes Nuketown 2025's native `ComWorld` primary-light table from the exact expanded retail `mp_nuketown_2020.ff` stream. No old GLB, Blender scene, visual fitting, or guessed light placement is used.

## Source

- expanded retail SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`
- T6 XAsset count: **840**
- XAsset **562**: `COMWORLD` / inline
- XAssets **563-564**: `LIGHT_DEF` / inline
- XAsset **565**: `TECHNIQUE_SET` / inline

Pinned OpenAssetTools contract: `2ca512abe7cb82d70a94d5ad7846043c3978862d`.

The pinned T6 ZoneCode contract is:

```text
ComWorld: TEMP fixed; name string; primaryLights[primaryLightCount]
ComPrimaryLight: defName is a string/packed reusable string alias
GfxLightDef: TEMP fixed; name string; attenuation GfxImage asset reference
```

## Exact ComWorld closure

The unique retail ComWorld header/name topology lands at:

- fixed source: **48,632,868**
- fixed bytes: **16**
- name: `maps/mp/mp_nuketown_2020.d3dbsp`
- `isInUse`: **1**
- `primaryLightCount`: **18**
- primary-light fixed-array source: **48,632,916**
- PC32 `ComPrimaryLight` record size: **196 bytes**
- primary-light fixed-array end: **48,636,444**
- ComWorld serialized end after inline `defName` strings: **48,636,471**
- total ComWorld serialized bytes: **3,603**
- serialized-span SHA-256: `7e25df94c9f4c07c515c1cf5404bf53987502739d824c42ad3595c587bd5b771`

The two inline/reused light-definition string identities are closed through their exact block-5 VIRTUAL aliases:

- `lava_lamp_gobo` -> **48,410,784**
- `white_light` -> **48,410,799**

The 15-byte spacing is exactly the serialized byte length of `lava_lamp_gobo\0`, and subsequent packed references reuse those exact addresses.

## Primary-light census

Native raw `type` values are retained rather than renamed without a separate renderer enum proof:

- type 0: **1**
- type 1: **1**
- type 2: **16**
- `canUseShadowMap = 1`: **9**
- `canUseShadowMap = 0`: **9**
- cookie-enabled records: **2**
- non-zero `shadowmapVolume`: **7**
- `lava_lamp_gobo`: **2** records
- `white_light`: **14** records
- two records have null `defName`

Every record preserves the native fields including `type`, shadow/cookie controls, `cullDist`, color, direction, origin, radius, all three cosine half-FOV values, rotation/translation limits, mip distance, attenuation, roundness, diffuse/falloff/angle/aAbB vectors, and all three cookie-control vectors.

## Independent downstream boundary proof

The ComWorld end is not accepted in isolation. The verifier replays the next two top-level retail assets:

### XAsset 563 LIGHT_DEF

- exact start: **48,636,471**
- packed name -> block 5 / `lava_lamp_gobo`
- attenuation image pointer: INSERT
- exact inline GfxImage name: `nt_2020_lava_lamp_gobo`
- exact end: **48,636,602**

### XAsset 564 LIGHT_DEF

- exact start: **48,636,602**
- packed name -> block 5 / `white_light`
- attenuation image pointer: INSERT
- exact inline GfxImage name: `whitesquare`
- exact end: **48,636,722**

Byte **48,636,722** is then validated as the start of top-level XAsset **565 TECHNIQUE_SET**.

This gives an exact downstream source-boundary closure rather than a plausible structure scan.

## Artifacts

- verifier: `tools/t6_nuketown_comworld_primary_lights_v1.py`
- compressed exact manifest: `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_COMWORLD_PRIMARY_LIGHTS_V1.json.zlib.b64`
- locally validated uncompressed manifest bytes: **29,653**
- locally validated uncompressed manifest SHA-256: `45d268235a0147c1bbf67a68676ee38c9241ca840585c87ea7c21e2cbe8e639c`
- compressed manifest bytes: **4,833**
- compressed-file SHA-256: `12df9c33df6df532af6b6994eb8f693164de76b04690c257491e51c72a0e9ddc`
- local verifier SHA-256 used for the run: `dd695f3d34fe5a7e0a23640815326a172504a9728235395173a17fbd770184c0`
- deterministic second generation: **byte-identical**

## Integration boundary

This closes the retail light records themselves. It does **not** yet claim that a generic Blender light reproduces T6's full primary-light renderer. The exact records should be carried into the fresh full-map package first; renderer-specific conversion remains downstream and must not replace the native data.

Next lighting work: bind these 18 exact primary lights to the GfxWorld primary-light ownership/light-grid/shadow path and recover the remaining runtime composition semantics without dropping the already-closed lightmap/reflection contracts.
