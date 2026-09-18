# T6 Nuketown exact production texture payload coverage — 103 / 450

Date: 2026-09-18

## Closed this transaction

The authoritative production dependency denominator remains **450 identity-deduplicated GfxImages**. This transaction separates dependency coverage from payload-provider coverage and adds exact inline retail providers that were previously invisible to the 81-image IPAK/DDS bridge.

Exact payload coverage is now:

- 75 production identities from the existing exact 81-image IWI27/DDS bridge;
- 1 `$identitynormalmap` from the independently recovered block-5 inline GfxImage loader replay and exact `80 80 ff 80` retail pixel validation;
- 2 GfxWorld secondary lightmaps from SHA-pinned inline serialized ranges;
- 25 GfxWorld reflection images from exact GfxWorld ownership joined to unique serialized GfxImage objects in the SHA-pinned expanded retail map.

Therefore:

- exact production payload coverage: **103 / 450 = 22.8888888889%**;
- unresolved production payload identities: **347**;
- Material exact payload coverage: **76 / 423 = 17.9669030733%**;
- unresolved Material payload identities: **347**;
- lightmaps: **2 / 2 exact payloads closed**;
- reflection probes: **25 / 25 exact payloads closed**.

The equality between unresolved production and unresolved Material counts is now meaningful: every non-Material production payload (both lightmaps and all 25 reflection probes) is exact-byte covered. The remaining production payload deficit is entirely within the Material GfxImage set.

## Exact inline GfxWorld evidence

Lightmap payloads are hashed directly from expanded retail SHA-256 `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505` using the independently recovered nullable lightmap role proof:

- `*lightmap0_secondary`: 6,291,456 bytes, SHA-256 `3f8ed737b8dedb71b818db56ca37019e051a582cfe60b367a6e8697a1da3042b`;
- `*lightmap1_secondary`: 3,145,728 bytes, SHA-256 `1aab55b6712370066f36c2e7f3f8f51de4af2d0964f5e4fad70f1801f48082a0`.

The reflection probe scanner requires exact identity from the v3 GfxWorld ownership catalog, exactly one serialized GfxImage candidate, an inline name pointer, inline/insert loadDef, a bounded resource range, and the SHA-pinned expanded source. All 25 pass with zero ambiguous/absent rows. `*reflection_probe0` has a 288-byte inline payload; probes 1–24 each have 131,232-byte inline payloads. Individual SHA-256 hashes are retained in `proof/T6_NUKETOWN_REFLECTION_INLINE_PAYLOAD_PROBE_V1.json`.

## Durable implementation / CI

Files:

- `tools/t6_nuketown_production_texture_payload_coverage_v1.py`
- `tools/t6_nuketown_lightmap_inline_payload_proof_v1.py`
- `tools/t6_nuketown_reflection_inline_payload_probe_v1.py`
- `proof/T6_NUKETOWN_LIGHTMAP_INLINE_PAYLOAD_PROOF_V1.json`
- `proof/T6_NUKETOWN_REFLECTION_INLINE_PAYLOAD_PROBE_V1.json`
- `proof/T6_NUKETOWN_PRODUCTION_TEXTURE_PAYLOAD_COVERAGE_V1.json`

Successful Actions:

- lightmap inline payload proof: run `35377638918`, job `105706026779`, artifact `10560718709`, persisted proof commit `74c0a08`;
- reflection inline payload probe: run `35377850911`, job `105706715599`, artifact `10561240801`, persisted proof commit `d709caf`;
- 103-image production payload coverage: run `35377948805`, job `105707025539`, artifact `10561225922`, persisted coverage commit `da0a0db`.

## Proof boundary

No identity is admitted by filename similarity, expected dimensions, visual plausibility, ordering, or adjacency alone. Reflection ownership comes from the separately recovered GfxWorld catalog; byte promotion additionally requires the exact serialized object topology and SHA-pinned source. This closes payload bytes, not reflection/lightmap shader equations or historical-retail duplicate TechniqueSet precedence.

## Exact next gate

The texture payload deficit is now **347 Material GfxImages only**. Continue by classifying those 347 identities by exact serialized GfxImage/loadDef topology and packed-vs-inline ownership across the five authoritative dependency roots, then recover additional payloads only where identity and byte ownership both close. Do not retry GfxWorld lightmap/reflection payload recovery: those categories are now 100% exact-byte covered.
