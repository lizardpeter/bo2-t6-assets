# T6 Nuketown production texture payload closure — 450 / 450

Date: 2026-09-18

The exact production GfxImage denominator for mp_nuketown_2020 is now payload-closed.

## Exact denominator

The already-closed identity-deduplicated production union is:

- Material GfxImages: 423
- GfxWorld lightmap GfxImages: 2
- GfxWorld reflection-probe GfxImages: 25
- exact production union: **450**
- cross-category identity overlaps: 0 in the closed denominator proof

This checkpoint does not recreate that denominator by adding category counts; it consumes the existing identity-deduplicated production census.

## Exact payload closure

proof/T6_NUKETOWN_PRODUCTION_TEXTURE_PAYLOAD_COVERAGE_V1.json had 103 / 450 exact payload providers:

- 75 from the exact IPAK/DDS bridge
- 28 exact inline providers
- Material: 76 / 423
- lightmaps: 2 / 2
- reflections: 25 / 25

The remaining 347 identities were all Material GfxImages.

Five-root native tracing then established a stable native packed tuple for **347 / 347** remaining production identities, with zero cross-root tuple conflicts and zero trace absences in that production subset:

- proof/T6_NUKETOWN_GFXIMAGE_PACKED_IDENTITY_TRACE_V2.json
- proof/T6_NUKETOWN_UNRESOLVED_MATERIAL_PACKED_TRACE_JOIN_V1.json

The exact retail IPAK resolver then resolved **347 / 347**, with:

- 0 missing exact (nameHash,dataHash) pairs
- 0 cross-root trace conflicts
- 0 IPAK byte/dimension conflicts
- CRC29-validated extraction
- byte identity required across every supplied IPAK carrying the same exact pair
- exact native traced width/height/depth agreement

Proof:

- proof/T6_NUKETOWN_UNRESOLVED_MATERIAL_IPAK_RESOLUTION_V1.json
- resolver workflow run 35401512450
- resolver job 105782217851
- persisted resolver commit f60a7af95199e502299913729958bb5a23c655ad

The v2 production projector is intentionally all-or-nothing for this promotion: it refuses to emit the completed coverage state unless the full 347-image unresolved set is resolved exactly.

Final persisted proof:

- proof/T6_NUKETOWN_PRODUCTION_TEXTURE_PAYLOAD_COVERAGE_V2.json
- proof commit 09d5207ce2a9db5a1d6928584eb0e58598a08fce
- validation workflow runs 35401947891 and 35401959030

Final exact coverage:

- production: **450 / 450 = 100%**
- Material: **423 / 423 = 100%**
- GfxWorld lightmaps: **2 / 2 = 100%**
- reflection probes: **25 / 25 = 100%**
- unresolved production GfxImages: **0**

## Fail-closed boundary

No filename similarity, inferred hashes, dataHash-only ownership fallback, first-match selection, expected dimensions, ordering, or visual substitution is used for the 347 new providers. Native (nameHash,dataHash) comes from SHA-pinned five-root FastFile tracing through exactly pinned OAT. Retail IPAK promotion requires the exact pair plus CRC-valid bytes and traced dimensions.

The separate historical-retail duplicate TechniqueSet precedence authority boundary remains unresolved and is not changed by this texture closure.

## Next hard gates

The production texture identity/payload denominator is closed and should not be rebuilt in future sessions unless newer authoritative evidence invalidates it.

Continue with renderer/export closure outside payload ownership: Material / TechniqueSet / shader / sampler / render-state semantics, duplicate TechniqueSet historical-retail ownership, world secondary vertex streams, inline brush-model validity, XModel/XAnim/DObj, FX, sounds, scripts, and other supporting asset classes.
