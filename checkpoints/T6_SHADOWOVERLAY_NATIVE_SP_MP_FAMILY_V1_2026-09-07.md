# T6 native SP/MP shadowoverlay dependency family v1

Date: 2026-09-07

## Status

This checkpoint promotes the actual native SP/MP startup `shadowoverlay` Material dependency family recovered by pinned OpenAssetTools from the SHA-pinned retail FastFiles.

It supersedes any attempt to bind `shadowoverlay` to the unproven candidate `pimp_technique_shadowoverlay_5255c888`.

The authoritative serialized dependency chain is:

`Material shadowoverlay`

→ `TechniqueSet trivial_shadowoverlay_14e2e827`

→ declared Technique type `unlit`

→ `Technique pimp_technique_trivial_7bf1260`

The Technique's one pass uses:

- state map `passthrough`
- vertex shader `pimp_shader_hdr_933ab43.hlsl`
- pixel shader `pimp_shader_trivial_3981dec1.hlsl`
- pixel argument `colorMapSampler = sampler.feedbackSampler`
- vertex routing `position -> position`, `texcoord[0] -> texcoord[0]`

## Retained native source artifact

Workflow run: `34164508108`

Artifact:

- ID: `10033905361`
- name: `T6_SHADOWCOOKIEOVERLAY_STARTUP_MATERIAL_OWNER_V3`
- digest: `sha256:75a1f72bcd57a0192cbb685718d6687621a1d343d6fd13d81ed61eb62053967c`

The surrounding all-Material census later failed closed on an unrelated duplicate-definition ambiguity. The `shadowoverlay_dependency_bundle` itself was emitted before that failure and preserves the physical native files, their source roots, byte counts, hashes, TechniqueSet bindings, parsed Technique pass/stage identity, and referenced shader binaries.

The dependency-bundle producer deliberately does not resolve duplicate zone precedence. For this family, the physical SP and MP copies agree exactly.

## Material identity

Physical roots:

- `code_post_gfx`
- `code_post_gfx_mp`

`materials/shadowoverlay.json`:

- bytes: `1504`
- SHA-256: `9f6281f55c71a368b49625516832a83257e0e77279046f9ba3c5598d0198747e`
- identical in both roots
- `_game = t6`
- `_type = material`
- `sortKey = 4`
- `contents = 1`
- no Material constants
- no Material texture bindings
- `techniqueSet = trivial_shadowoverlay_14e2e827`
- texture atlas `1 x 1`

Native state row:

- alpha test: disabled
- RGB blend op: disabled
- alpha blend op: disabled
- RGB color write: enabled
- alpha color write: enabled
- cull face: back
- depth test: disabled
- depth write: false
- destination RGB blend: zero
- destination alpha blend: zero
- source RGB blend: one
- source alpha blend: one
- polygon offset: `offset0`

`stateBitsEntry` contains one active entry at index 2 pointing to this state row; all other entries are `-1`. The authoritative Technique type comes from the `.techset` binding below rather than from an inferred numeric-index meaning.

## TechniqueSet identity

`techsets/trivial_shadowoverlay_14e2e827.techset`:

- bytes: `43`
- SHA-256: `ba3c8b3b5d4535cb01440450855ca6602d17baeba2cc4a7d75385a8eb036724c`
- binding identity SHA-256: `e3f9aa199cc244befa52f5de64e619ed927aafa80eb50c7f6f70695d702f11c0`
- identical in SP and MP roots

Exact binding:

```text
"unlit":
  pimp_technique_trivial_7bf1260;
```

This is direct OAT serialization of the native T6 `MaterialTechniqueSet` and its `techniques[]` pointer relationship.

## Technique identity

`techniques/pimp_technique_trivial_7bf1260.tech`:

- bytes: `284`
- SHA-256: `7285785bb833737bca9df124bb2039a0737cdc54a22f14567105df5517ff63b7`
- parsed pass/stage identity SHA-256: `835620ff3b2b7ed05ff1ed86b8fdd4d3dcbc12522f8a6a6b3d634f5f8f38869f`
- identical in SP and MP roots

Exact dumped Technique text:

```text
{
  stateMap "passthrough"; // TODO

  vertexShader 4.0 "pimp_shader_hdr_933ab43.hlsl"
  {
  }

  pixelShader 4.0 "pimp_shader_trivial_3981dec1.hlsl"
  {
    colorMapSampler = sampler.feedbackSampler;
  }

  vertex.position = code.position;
  vertex.texcoord[0] = code.texcoord[0];
}
```

The `// TODO` text is OAT dumper presentation and is not interpreted as uncertainty in the physical Technique identity.

## Shader binaries

Vertex shader `pimp_shader_hdr_933ab43.hlsl`:

- CSO bytes: `3040`
- SHA-256: `630a2f147e43f6bca732a73cbeea52ca5d4a65c48324ee784b84c67d7ef23909`

Pixel shader `pimp_shader_trivial_3981dec1.hlsl`:

- CSO bytes: `5600`
- SHA-256: `2ef171c239a7c98542a961252362761828747bd288ee21e3fde542d48aa5de0e`

The exact `.tech` binding is:

`colorMapSampler = sampler.feedbackSampler`

No semantic meaning beyond that binding is promoted here without separate retail renderer proof.

## Relation to the complete FastFile census

The separately completed 215/215 retail FastFile census found `shadowoverlay` and `trivial_shadowoverlay_14e2e827` in exactly three startup zones:

- `code_post_gfx.ff`
- `code_post_gfx_mp.ff`
- `code_post_gfx_zm.ff`

It found zero occurrence of the demoted candidate `pimp_technique_shadowoverlay_5255c888` or the `pimp_technique_shadowoverlay_` stem.

This checkpoint closes only the native SP/MP dependency family. Zombies is a separate native closure gate until its physical Material/TechniqueSet/Technique bundle is compared.

## Proof boundary

Authoritative here means the serialized native SP/MP startup Material dependency family is directly reproduced by pinned OAT and the two physical roots agree on the exact Material, TechniqueSet, Technique, and shader payload identities.

This checkpoint does **not** establish:

- runtime built-in/global Material registration;
- the T6 `rgp` field or equivalent storage slot;
- the renderer pass that consumes `shadowoverlay`;
- zone load-order precedence;
- that `sampler.feedbackSampler` has any specific high-level effect beyond the exact shader argument binding;
- any relationship to historical `shadowCookieOverlayMaterial` names;
- ownership of the demoted `pimp_technique_shadowoverlay_5255c888 / 592 / cc2f...` candidate.

Those require separate T6-native proof.
