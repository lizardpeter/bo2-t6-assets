# T6 Nuketown exact production GfxImage denominator closure

Date: 2026-09-18

## Result

The production texture dependency census is now green and the final identity-level GfxImage denominator is closed for the current exact Nuketown production graph.

Authoritative workflow evidence:

- workflow run: `35301228578`
- job: `105464091603` (`census`) — success
- head commit: `5b64d0054ae863a8ce55855457e324771b830a68`
- artifact ID: `10529627853`
- artifact name: `T6_NUKETOWN_PRODUCTION_TEXTURE_DEPENDENCY_CENSUS_V1`
- artifact digest: `sha256:ffa2185edcc32d2fa46d07cc7b0c60f7399c9b84e6e458df2c563b7d06e83856`
- census proof: `proof/T6_NUKETOWN_PRODUCTION_TEXTURE_DEPENDENCY_CENSUS_FULL_V2.json`

Every workflow stage completed successfully, including exact five-root expansion, native Material dumping, required-only Material union, production manifest v7, exact 81 pointer-proven retail IWI materialization, and final production image coverage accounting.

## Exact identity counts

The census performs identity-level set accounting rather than adding category counts.

- required Material identities: `327`
- Material texture dependencies: `973`
- unique Material GfxImages: `423`
- exact-81 bridge coverage of Material images: `75 / 423 = 17.7304964539%`
- GfxWorld lightmap GfxImages: `2`
- GfxWorld reflection-probe GfxImages: `25`
- exact deduplicated production union: `450` unique GfxImages
- exact-81 bridge coverage of production union: `75 / 450 = 16.6666666667%`
- production images missing from exact-81 bridge: `375`
- exact-81 bridge identities unused by the current production graph: `6`

Because the identity-level union is 450 and the category cardinalities are 423 + 2 + 25 = 450, the recovered Material, lightmap, and reflection-probe identity sets have zero cross-category overlap in this production graph. This conclusion comes from the actual set-union result, not from category-count addition.

Neither of the two retail lightmap identities nor any of the 25 retail reflection-probe identities is covered by the exact-81 DDS bridge.

## Exact GfxWorld contribution

Lightmaps:

- `*lightmap0_secondary`
- `*lightmap1_secondary`

The corresponding retail primary-image slots are null and are not converted into synthetic identities.

Reflection probes:

- `*reflection_probe0` through `*reflection_probe24`

These 27 identities originate from the separately SHA-verified retail GfxWorld ownership catalogs; the V2-named inputs consumed by this run are identity-only compatibility projections of those V3 catalogs, not inferred replacements.

## Proof boundary

Coverage is exact GfxImage identity intersection only. Generated Materials contribute only their exact runtime texture table. Parsed component layers are not used to infer missing standalone component boundaries. Filename similarity, ordering, adjacency, dimensions, visual resemblance, and substitution are not admitted as retail proof.

The 375 missing production identities are therefore real unresolved payload coverage under the current exact graph; they must not be visually substituted and called exact.

## Next blocker

GfxWorld ownership and the production GfxImage denominator are no longer the blocker.

The highest-value shader-side blocker remains retail-client duplicate XAsset selection for the five-root native Material/Technique universe. The durable five-root conflict census has 58 divergent parent-owned child Technique conflicts affecting 269 ordinary Materials across 9 TechniqueSets. PC dedicated-server evidence predicts patch ownership for all 58, but that evidence is explicitly not retail-client authority.

The next exact experiment should recover the retail `t6mp.exe` duplicate-XAsset precedence path (zone allocation flags / priority / duplicate insertion-or-override behavior) against SHA-256 `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`, then project that independently recovered client rule over the existing 58-conflict census. Do not select winners from server behavior or load-order heuristics.