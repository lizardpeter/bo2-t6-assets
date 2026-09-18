# T6 Nuketown unresolved Material GfxImage visibility closure

Date: 2026-09-18

The exact production payload deficit remains 347 Material GfxImage identities after the 103/450 payload closure.

## Closed in this transaction

A SHA-pinned five-root OAT image census now retains the complete native image names observed from each exact FastFile root rather than only emitted DDS filenames or a log tail. A fail-closed exact-string join against the 347 unresolved production identities closes visibility for **347 / 347** with **0 absent exact identity joins**.

The join additionally proves that all **347 / 347** were reported by this OAT invocation as lacking payload data in its current search path. This is deliberately *not* promoted to retail payload absence: pinned OAT's T6 image converter first attempts IPAK lookup and then a loose `.iwi` search, while this diagnostic run supplied the FastFiles but not the retail IPAK containers/loose IWI corpus.

Summary from `proof/T6_NUKETOWN_MATERIAL_GFXIMAGE_ROOT_JOIN_V1.json`:

- unresolved Material images: 347
- exact identity visibility joins: 347
- no exact visibility join: 0
- multi-root exact visibility identities: 1
- visible but OAT payload missing in the probe search path: 347
- visible with a non-missing OAT payload path: 0

This removes a useful ambiguity: the remaining 347 are not missing because their GfxImage identities are absent from the exact dependency roots. The next payload gate is the native packed-image identity tuple and retail IPAK lookup.

## New packed-hash path

Pinned OAT source confirms its T6 streamed-image lookup calls `GetEntryStream(image.hash, image.streamedParts[0].hash)`. A diagnostic source patch and workflow are now in-tree to trace exactly those native resolved fields, plus streamed-part count and dimensions, immediately before the existing lookup without changing loader behavior:

- `tools/t6_oat_gfximage_packed_identity_trace_patch_v1.py`
- `.github/workflows/t6_nuketown_gfximage_packed_identity_trace_v1.yml`
- run 35383445117 (instrumented pinned-OAT build in progress when this checkpoint was written)

A fail-closed retail resolver is also staged:

- `tools/t6_nuketown_unresolved_material_ipak_resolution_v1.py`
- `.github/workflows/t6_nuketown_unresolved_material_ipak_resolution_v1.yml`

It requires exact traced identity, native `nameHash`, native first-streamed-part `dataHash`, CRC-validated retail IPAK extraction, byte-identical payload across every matching supplied IPAK candidate, and exact traced IWI dimensions. Conflicts fail closed. A v2 production coverage projector is staged but must not be run/promoted until the resolution proof exists.

## Proof boundary

No OAT filename transformation, fuzzy identity, guessed hash, expected dimension, first-match behavior, or visual plausibility is accepted as payload authority. The 103/450 exact payload coverage remains authoritative until new traced IPAK resolutions validate.

## Exact resume point

Recover run `35383445117`. If the instrumented build/trace is green, inspect and persist `T6_NUKETOWN_GFXIMAGE_PACKED_IDENTITY_TRACE_V1.json`, exact-join its rows to the 347 unresolved identities, then run the retail IPAK resolver across the already-used exact container universe. Only successful byte-validated rows may be promoted through `t6_nuketown_production_texture_payload_coverage_v2.py`. If the trace build fails, fix the instrumentation/build error transactionally; do not fall back to inferred hashes.
