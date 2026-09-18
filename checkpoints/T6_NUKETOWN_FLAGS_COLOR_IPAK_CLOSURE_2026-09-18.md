# T6 Nuketown flags color IPAK closure — 2026-09-18

The last color payload explicitly left unresolved by the v12 three-XModel-material closure is now byte-closed without weakening identity rules.

## Exact source identity

The retained v12 Material proof already fixed:

- Material: `mc/mtl_nt_2020_flags_01`
- GfxImage: `~-gnt_2020_flags_01_c`
- native nameHash: **584722835**
- native streamed dataHash29: **147283182**

This image is an XModel/component Material dependency and is **not** a member of the separate 450-image world-production denominator; therefore this closure does not change the 103/450 world payload count.

## Exact retail payload result

`proof/T6_NUKETOWN_FLAGS_COLOR_IPAK_CLOSURE_V1.json` audits the exact pair across the eight supplied retail IPAK containers.

Exactly one container matched:

- container: `dlc0.ipak`
- entry offset: **12,599,296**
- entry rawSize: **592,000**
- reconstructed IWI bytes: **1,398,192**
- reconstructed IWI SHA-256: `70de67e2c7af7ab499ad75643b898f36a4d30b38bb5161b70dde99007cc77af0`
- IWI format: **13**
- IWI flags: **208**
- dimensions: **1024 x 1024 x 1**

Extraction is CRC29-validated against dataHash **147283182**.

The first hosted attempt failed on retail IPAK command `0xCF` because the v1 range reader did not implement the padding/skip command. The critical paths now use `t6_ipak_http_range_v2.py`, whose existing source-closed behavior consumes `0xCF` source bytes without emitting image bytes and still requires final CRC29 equality.

## Proof boundary

Only the exact source-proven `(nameHash,dataHash)` pair can satisfy this closure. No dataHash-only fallback, same-name lookup, nearest entry, filesystem ordering, visual substitution, or cross-container guess is admitted.

This closes the **payload identity** left unresolved in the v12 three-material proof. Applying the newly closed payload into a regenerated current production GLB is a separate artifact-generation transaction; the old v12 artifact must not be treated as silently modified.

## Hosted validation

- successful exact-pair run: **35386533796**
- job: **105734652712**
- persisted proof commit: `3fa541e3168a2b8be5ee2d9dacc30ccf3a1b119a`
