# T6 shadowCookieOverlay ownership — provenance-aware v4 checkpoint

Date: 2026-09-07

## Exact target

- Technique: `pimp_technique_shadowoverlay_5255c888`
- Serialized `.tech` bytes: `592`
- SHA-256: `cc2f2805aef4899b24ed1a181f816bfcdfd18c6ab876a1172cae11f0abd20d71`

## Retired inference paths

The four startup TechniqueSet-only OAT probe remains a valid negative control, not a global absence proof. Its SHA-pinned `code_post_gfx`, `code_post_gfx_mp`, `en_code_post_gfx`, and `en_code_post_gfx_mp` dumps succeeded, but did not emit the exact target `.tech` file.

The native Material shader census v3 is also superseded as an ownership resolver. Run `34161138991` preserved its forensic artifact but failed closed on a divergent same-name Technique definition:

`pimp_technique_trivial_abe3d51`: `/tmp/map_out` vs `/tmp/patch_out`.

No base/patch winner is inferred from that duplicate.

## Provenance-aware replacement

`tools/t6_oat_material_shader_census_v4.py` (commit `350e10325633fe3284e99b09bff15d172c17333b`) changes the dependency identity rule from global same-name merging to native parent provenance.

Pinned OpenAssetTools T6 `TechsetDumper` serializes one `MaterialTechniqueSet`, then walks that exact asset's `techset.techniques[]` pointers to emit child Techniques and shader binaries in the same output root. Therefore the physical root that owns the parent TechniqueSet is a native pointer-provenance constraint, not a guessed zone-precedence rule.

v4 rules:

1. A unique parent TechniqueSet owner must emit its declared child Technique in that same root.
2. Byte-identical duplicate parent TechniqueSets require every parent-owning root to emit the child and all parent-owned child pass/stage identities to agree.
3. Same-name Techniques in roots that do not own the parent TechniqueSet are retained as alternate definitions and cannot satisfy or override that parent dependency.
4. Divergent parent-owned dependencies remain fatal.
5. Generated `materials/generated` rows remain outside this ordinary native Material path.

Regression coverage is in `tools/test_t6_oat_material_shader_census_v4.py` (commit `f1b35a8ea34d7fbbd54c9cf4b4c525ec4a0241f7`). It covers unique-parent/divergent-nonparent acceptance, duplicate-parent identical-child acceptance, duplicate-parent divergent-child rejection, missing same-root child rejection, and generated-row exclusion.

The target-specific adapter is `tools/t6_oat_exact_technique_owner_closure_v2.py` (commit `f87391ed7deeb9def684ddccf03a37a1cc2b8212`). Authority additionally requires all physical target copies to equal the exact 592-byte/SHA identity and every parent `.techset` to explicitly bind the same declared type to that exact Technique.

## Native startup Material evidence recovered

The completed startup v1 forensic run `34161669935` produced artifact `10033028129`, digest `sha256:b440ee5ca58123a2d019acfde3aa38594d0c13d97ff96359d7bc09b6661ce722`.

Its four native Material populations are:

- `code_post_gfx`: 355 Materials
- `code_post_gfx_mp`: 1,114 Materials
- `en_code_post_gfx`: 18 Materials
- `en_code_post_gfx_mp`: 58 Materials

Most importantly, native OAT emitted `materials/shadowoverlay.json` in both `code_post_gfx` and `code_post_gfx_mp`, and each JSON names:

`techniqueSet = trivial_shadowoverlay_14e2e827`

This is a direct Material -> TechniqueSet relationship from OAT's T6 Material dumper, which writes `material.techniqueSet->name`. It is stronger than the earlier Technique-only filename probe.

The v1 startup census then failed closed on another global duplicate:

`pimp_technique_trivial_e617cd88`: `code_post_gfx` vs `code_post_gfx_mp` vs `patch_mp`.

That failure does not invalidate the native `shadowoverlay -> trivial_shadowoverlay_14e2e827` parent relationship; it is exactly the ambiguity v4 was designed to classify with parent provenance.

## Active authoritative runs

### Nuketown/shared v4

- Workflow: `.github/workflows/t6_nuketown_native_material_shader_census_v1.yml`
- Commit: `628797c334e5fe68457e97ac558fd75a09cddfbf`
- Run: `34162229036`
- v4 regression step: green
- Current state at checkpoint: pinned OAT build running

SHA-pinned FastFiles:

- `mp_nuketown_2020.ff`: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- `common_mp.ff`: `93fe48b0f0d8cc6844be875ccad94e0cfcf635f62eeff00ac33f2f668a77cb77`
- `common_patch_mp.ff`: `95622d93d4fb761db311a123cd073bed34ea48c9c711d2c11bce4170dd08bae9`
- `patch_mp.ff`: `459077cda8e4a1457f7ee7d8f6c5e0abf30f41767a21ff6744df6a4307cbce1e`

### Startup-Material v4

- Workflow: `.github/workflows/t6_shadowoverlay_startup_material_owner_v1.yml`
- Commit: `0e13330f0daaef1f168ece9794a5bc1cdc6b10b7`
- Run: `34162279512`
- v4 regression step: green
- Current state at checkpoint: pinned OAT build running

SHA-pinned startup FastFiles:

- `code_post_gfx.ff`: `670407ecdbc6aedbfff7eb9961e403780798af6394aec46be1249650e54d9cd3`
- `code_post_gfx_mp.ff`: `b7bce1dbe94692b1668ae9a1c83a4dcf008979ee5d5f79b3d2e619c23a1002b3`
- `en_code_post_gfx.ff`: `f4b25c8aef7fc59644775ba974051641d74b35a6117e6cb48e471629bc2577a8`
- `en_code_post_gfx_mp.ff`: `7534d3ae7ceaabacbea23576f89a78c15e5ff881e542e8fc38ed740070ab2940`

The startup workflow treats a green no-association result as authoritative only within those four censused startup Material roots. It does not promote a global absence claim.

## Renderer-global fallback branch

Historical idTech/CoD renderer lineage contains a dedicated shadow-cookie overlay pass that draws a renderer-global `shadowCookieOverlayMaterial`. This is branch-selection evidence only, not a T6 ownership proof.

If both green T6 Material censuses exclude the exact 592-byte Technique, the next proof target is the pinned T6 retail executable's renderer-global Material registration/storage path, not a byte scan of arbitrary zones.

The repository already has direct static-retail-EXE proof infrastructure pinned to:

- `t6mp.exe` bytes: `12,850,328`
- image base: `0x00400000`
- SHA-256: `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`

Any T6 `rgp`/renderer-global ownership claim must be closed against that exact executable or another separately SHA-pinned retail build.

## Proof boundary

No owner is promoted from q-index, serialized offset, byte scan, filename similarity, neighboring assets, visual appearance, historical-engine similarity, or guessed zone precedence. Positive ownership requires a direct native Material/TechniqueSet pointer chain or an independently closed T6 renderer-global registration path, plus exact target byte identity.
