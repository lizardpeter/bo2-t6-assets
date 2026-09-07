# T6 native shadowoverlay family across SP / MP / ZM v1

Date: 2026-09-07

## Status

The native T6 startup `shadowoverlay` Material family is now closed across all three startup modes represented in the referenced retail FastFile archive:

- SP/startup: `code_post_gfx.ff`
- MP/startup: `code_post_gfx_mp.ff`
- Zombies/startup: `code_post_gfx_zm.ff`

All three modes serialize the same Material → TechniqueSet → Technique → shader family byte-for-byte.

Authoritative chain:

`Material shadowoverlay`

→ `TechniqueSet trivial_shadowoverlay_14e2e827`

→ declared Technique type `unlit`

→ `Technique pimp_technique_trivial_7bf1260`

→ VS `pimp_shader_hdr_933ab43.hlsl`

→ PS `pimp_shader_trivial_3981dec1.hlsl`

with exact pixel argument:

`colorMapSampler = sampler.feedbackSampler`

## SP / MP native bundle

Run `34164508108`

Artifact:

- ID `10033905361`
- `T6_SHADOWCOOKIEOVERLAY_STARTUP_MATERIAL_OWNER_V3`
- digest `sha256:75a1f72bcd57a0192cbb685718d6687621a1d343d6fd13d81ed61eb62053967c`

The retained `shadowoverlay_dependency_bundle` contains identical physical copies from `code_post_gfx` and `code_post_gfx_mp`.

## Zombies native bundle

Run `34167293973` completed fully green.

Artifact:

- ID `10034715117`
- `T6_SHADOWOVERLAY_ZM_STARTUP_MATERIAL_V1`
- digest `sha256:3746d02226be11978f2e4c915541bf1cbc73f4476cf102f2284a502fe5b9412f`

SHA-pinned Zombies inputs:

- `code_post_gfx_zm.ff`
  - bytes `300608`
  - CRC32 `8279fa43`
  - SHA-256 `dc44f775074e010e37f3fbdf60fc21af1de2582634432cd6057d6eecd0099942`
- `common_zm.ff`
  - bytes `10488640`
  - CRC32 `28886207`
  - SHA-256 `b0663e765b50a17e3e7a53e2675ca18a1eeca186e0356df74e9b2c615f09ce9e`
- `patch_zm.ff`
  - bytes `3001792`
  - CRC32 `64c325b4`
  - SHA-256 `f5a27345a61de5fabd735f45f05b127e95ad9a488619bd7fbc96ac14c5ab4d47`

The Zombies workflow independently dumped the native `shadowoverlay` Material and the complete TechniqueSet dependency universe with pinned OAT, then archived the exact family. Its classification contains exactly one declared Technique: `pimp_technique_trivial_7bf1260`.

## Cross-mode byte identity

### Material

`materials/shadowoverlay.json`

- bytes `1504`
- SHA-256 `9f6281f55c71a368b49625516832a83257e0e77279046f9ba3c5598d0198747e`
- identical SP / MP / ZM

Native Material facts include:

- `techniqueSet = trivial_shadowoverlay_14e2e827`
- no Material texture bindings
- no Material constants
- depth test disabled
- depth write false
- source RGB/alpha blend = one
- destination RGB/alpha blend = zero
- RGB/alpha writes enabled
- polygon offset `offset0`
- sort key `4`

### TechniqueSet

`techsets/trivial_shadowoverlay_14e2e827.techset`

- bytes `43`
- SHA-256 `ba3c8b3b5d4535cb01440450855ca6602d17baeba2cc4a7d75385a8eb036724c`
- binding identity SHA-256 `e3f9aa199cc244befa52f5de64e619ed927aafa80eb50c7f6f70695d702f11c0`
- identical SP / MP / ZM

Exact binding:

```text
"unlit":
  pimp_technique_trivial_7bf1260;
```

### Technique

`techniques/pimp_technique_trivial_7bf1260.tech`

- bytes `284`
- SHA-256 `7285785bb833737bca9df124bb2039a0737cdc54a22f14567105df5517ff63b7`
- parsed pass/stage identity SHA-256 `835620ff3b2b7ed05ff1ed86b8fdd4d3dcbc12522f8a6a6b3d634f5f8f38869f`
- identical SP / MP / ZM

One pass:

- `stateMap "passthrough"`
- vertex shader `pimp_shader_hdr_933ab43.hlsl`
- pixel shader `pimp_shader_trivial_3981dec1.hlsl`
- pixel shader argument `colorMapSampler = sampler.feedbackSampler`
- vertex routing position→position and texcoord[0]→texcoord[0]

### Shader binaries

Vertex shader CSO:

- bytes `3040`
- SHA-256 `630a2f147e43f6bca732a73cbeea52ca5d4a65c48324ee784b84c67d7ef23909`

Pixel shader CSO:

- bytes `5600`
- SHA-256 `2ef171c239a7c98542a961252362761828747bd288ee21e3fde542d48aa5de0e`

The Zombies physical copies match the previously retained SP/MP copies exactly.

## Relationship to complete 215-FastFile census

The complete, green 215/215 retail FastFile census found the strings `shadowoverlay` and `trivial_shadowoverlay_14e2e827` in exactly these same three startup zones and nowhere else in the referenced FastFile universe.

The native OAT bundles now turn those three string-level hits into direct serialized Material dependency proof for every mode.

The same 215/215 census found zero occurrence of:

- `pimp_technique_shadowoverlay_5255c888`
- `pimp_technique_shadowoverlay_`
- `shadowcookieoverlay`

The old 592-byte candidate is therefore not part of this authoritative family and remains demoted under `T6_SHADOWOVERLAY_TARGET_PROVENANCE_AUDIT_V1_2026-09-07.md`.

## Proof boundary

This checkpoint establishes one byte-identical serialized native startup `shadowoverlay` dependency family across SP, MP, and Zombies in the referenced retail FastFile archive.

It does not establish:

- the runtime renderer-global storage slot that receives this Material;
- which T6 renderer function consumes the Material;
- whether T6 has a distinct runtime-only `shadowCookieOverlayMaterial` concept;
- the semantic meaning of `feedbackSampler` beyond the exact Technique argument binding;
- any runtime load-order relationship outside the three proven serialized startup families.

Those are executable/runtime proof tasks and remain separate.
