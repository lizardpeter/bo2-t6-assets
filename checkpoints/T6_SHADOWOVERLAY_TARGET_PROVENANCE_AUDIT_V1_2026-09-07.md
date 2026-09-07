# T6 shadowoverlay target provenance audit v1

Date: 2026-09-07

## Result

The previously carried identity

- `pimp_technique_shadowoverlay_5255c888`
- 592 serialized `.tech` bytes
- SHA-256 `cc2f2805aef4899b24ed1a181f816bfcdfd18c6ab876a1172cae11f0abd20d71`

is **not source-closed for the pinned retail T6 archive** and must no longer be described as an exact retail target.

It is retained only as an **unproven candidate identity** until a physical source artifact or independently reproducible derivation is produced.

This is a proof-boundary correction, not an assertion that such a Technique can never exist in another T6 build/container.

## Provenance audit

### 1. First repository appearance of the filename

Commit `9a12a4e186882c2715e6228a8d09e4f0689b136e` introduced `pimp_technique_shadowoverlay_5255c888.tech` only as the input target of `.github/workflows/t6_shadowoverlay_owner_probe_v1.yml`.

Actions run `34150661226` / job `101832092052` did **not** recover that file.

Its retained artifact is:

- artifact `10029462309`
- `T6_SHADOWOVERLAY_OWNER_PROBE_V1`
- digest `sha256:b7c2fb32dc6c801d4a8e5621238055227e21a0488670e75e42ef6f2edd11de17`

The artifact's `owner_matches.txt` is zero bytes. All four candidate OAT TechniqueSet dumps returned rc=0, so the negative is not an extraction crash.

The startup dumps contain `trivial_shadowoverlay_14e2e827.techset` in `code_post_gfx` and `code_post_gfx_mp`, but do not contain `pimp_technique_shadowoverlay_5255c888.tech`.

Therefore run `34150661226` is a **negative probe**, not provenance for the candidate Technique.

### 2. Intervening retained shader extraction is not the source

The successful cross-map retained-unlit workflow run `34151387858` produced artifact `10029480742` (`T6_RETAIL_UNLIT_DIRECT_DXBC_V1`, digest `sha256:237f9bfc1298c1ebbc5c4fed32360dc441023ae1c744b5b22d5f4a1743035703`).

The 92-file artifact contains no occurrence of:

- `shadowoverlay`
- `shadowcookie`
- `5255c888`

It therefore did not produce the candidate Technique identity or its alleged 592-byte payload.

### 3. First repository appearance of the 592-byte/SHA identity

Commit `329d0b99b81e05f91eb154415a55f2a922bf894c` is the first located repository commit that supplies all three candidate constants together:

- name `pimp_technique_shadowoverlay_5255c888`
- bytes `592`
- SHA-256 `cc2f2805aef4899b24ed1a181f816bfcdfd18c6ab876a1172cae11f0abd20d71`

They are passed as literal command-line arguments to the owner-closure adapter. That commit contains no extraction, source-file reference, artifact ID, or derivation that establishes where the 592 bytes came from.

The generic fail-closed adapter added immediately before it (`4c53a2de31458b189dd169a78a317b4a0891428e`) likewise does not derive those constants.

Consequently the byte/SHA pair is an asserted input at that point in history, not a retained proof output.

## Complete retail FastFile census

Hardened run `34167293970` completed all 8 scan shards and the aggregate successfully.

Aggregate artifact:

- artifact `10034581135`
- `T6_SHADOWOVERLAY_ALL_FASTFILE_SCAN_V1`
- digest `sha256:99d47cbd3a0ad08caec6688296169fab4830c0195e4a0c190db6474eeb299de2`

Archive identity recorded by the aggregate:

- ZIP kind: ZIP64
- ZIP bytes: `13,675,690,564`
- ZIP entries: `534`
- FastFiles: `215`
- FastFiles successfully CRC-verified, SHA-256 pinned, decrypted and inflated: `215 / 215`
- failed expansions: `0`

Exact expanded-XFile name census:

- exact `pimp_technique_shadowoverlay_5255c888\0`: **0 zones**
- stem `pimp_technique_shadowoverlay_`: **0 zones**
- `shadowcookieoverlay`: **0 zones**
- `shadowoverlay`: **3 zones**
- `trivial_shadowoverlay_14e2e827`: **3 zones**

The only three `shadowoverlay` / `trivial_shadowoverlay_14e2e827` FastFiles are:

1. `zone/all/code_post_gfx.ff`
2. `zone/all/code_post_gfx_mp.ff`
3. `zone/all/code_post_gfx_zm.ff`

This is authoritative for literal-name presence in the referenced 215-FastFile archive universe because every FastFile completed exact container verification and source-closed T6 decrypt/inflate before the census.

## Why the zero Technique-name census matters

Pinned OpenAssetTools T6 `TechsetDumper` at `9dca965366541504b71fa8cfb7ac049cb9b717e1` writes `MaterialTechnique::name` directly when dumping `.tech` files and writes that same Technique name into the parent `.techset` representation.

The dumper does not synthesize a `pimp_technique_*` name while dumping a nameless retail Technique. Repository/source search of the pinned OAT implementation finds the `pimp_technique_` prefix in compiler/test logic, not as a dump-time naming fallback.

Therefore the complete 215-FastFile zero is stronger than a generic string-scan negative: it rules out `pimp_technique_shadowoverlay_5255c888` as an ordinary named serialized Technique in this exact retail FastFile archive.

It still does **not** prove absence from:

- the executable or renderer-global runtime state;
- non-FastFile containers;
- another retail/build revision;
- dynamically generated data;
- an external precompiled/source asset system not serialized into these FastFiles.

## Native Material facts that remain valid

The demotion of the candidate Technique does not invalidate the native startup Material result.

Pinned OAT Material dumping proves in both `code_post_gfx` and `code_post_gfx_mp`:

`Material shadowoverlay -> TechniqueSet trivial_shadowoverlay_14e2e827`

Those are direct native Material pointer-derived relationships.

The complete FastFile census independently shows the same `shadowoverlay` / `trivial_shadowoverlay_14e2e827` literal family in `code_post_gfx_zm`; native Zombies Material/dependency closure remains a separate gate and must not be inferred from the string census alone.

## Renderer-global branch

Historical CoD renderer source remains useful only as branch-selection evidence: it has distinct renderer-global `shadowCookieOverlayMaterial` and `shadowOverlayMaterial` slots.

That historical fact must not be promoted to T6 semantics without direct T6 evidence.

The repository's separately established retail executable identity remains:

- bytes: `12,850,328`
- image base: `0x00400000`
- SHA-256: `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`

A renderer-global T6 closure must be made against that exact executable (or another separately SHA-pinned build) and must independently prove the relevant registration/storage/consumer path.

The public full-game ZIP used for the 215-FastFile census does not itself provide the exact executable source needed for that static proof, so executable provenance remains a separate retrieval problem.

## Superseded language

Any earlier checkpoint or workflow description calling the candidate name/592/SHA tuple an **exact retail target** is superseded by this audit.

The owner-closure adapters remain valid generic fail-closed machinery. Their candidate-specific invocations are not authoritative evidence unless the candidate identity is independently source-closed first.

## Proof boundary

No owner may be promoted from the candidate filename, 592-byte assertion, candidate SHA, q-index, serialized offset, byte-scan hit, adjacency, visual similarity, historical-engine similarity, or guessed zone precedence.

The current authoritative boundary is:

1. the complete 215/215 FastFile archive has zero occurrence of the candidate Technique name/stem;
2. native startup Materials in the proven SP/MP roots bind `shadowoverlay` to `trivial_shadowoverlay_14e2e827`;
3. the candidate `pimp_technique_shadowoverlay_5255c888 / 592 / cc2f...` tuple has no retained source provenance and is therefore unproven;
4. any renderer-global `shadowCookieOverlay` claim still requires direct T6 executable/runtime proof.
