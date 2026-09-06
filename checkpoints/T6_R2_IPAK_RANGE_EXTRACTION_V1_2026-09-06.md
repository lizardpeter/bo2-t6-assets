# T6 R2 range-backed IPAK extraction v1 — 2026-09-06

This checkpoint removes the shared-IPAK availability bottleneck for retail T6 asset reconstruction. The extractor reads only IPAK metadata/index ranges and exact requested compressed blocks from the user-provided retail mirror; it does not require downloading the multi-gigabyte containers wholesale.

## Implementation

- tool: `tools/t6_ipak_http_range_v1.py`
- tool commit: `c1a4170d783b27e5505fa597662061f4a7901529`
- validation workflow: `.github/workflows/t6_r2_ipak_range_smoke_v1.yml`
- workflow commit: `f1958eebc51267f91b60e5c5a4094e44f297ae97`
- successful run: `34055636017`

The reader validates HTTP `Content-Range`, stable remote object length, T6 `KAPI` / `0x50000` IPAK structure, index bounds, raw/LZO block decoding and the decompressed 29-bit CRC identity.

## Retail containers indexed by range

| Container | Full bytes | Entries | Metadata/index bytes fetched |
|---|---:|---:|---:|
| `mp_nuketown_2020.ipak` | 165,543,936 | 677 | 10,912 |
| `mp.ipak` | 348,651,520 | 3,298 | 52,816 |
| `base.ipak` | 2,614,362,112 | 13,366 | 213,904 |
| `patch_mp.ipak` | 56,623,104 | 800 | 12,848 |
| `so.ipak` | 146,538,496 | 656 | 10,544 |
| `en_base.ipak` | 786,432 | 65 | 1,088 |

Each index required exactly three HTTP range requests. In particular, the 2.61 GB `base.ipak` can be indexed with only 213,904 transferred bytes.

## Exact payload canary

Previously source-proven streamed image payload:

- retained streamed `dataHash`: `225863395`
- retail map-IPAK index nameHash: `3353894529`
- decompressed IWI bytes: **174,840**
- SHA-256: `b0bdda7032e682e07970264e141e6521038e7e40b13354f5aafa767e203a2e40`
- IWI27 format: `11`
- dimensions: **512 × 512 × 1**

The range reader reproduced that IWI byte-for-byte from `mp_nuketown_2020.ipak`. Index plus payload extraction transferred 185,880 bytes over five HTTP range requests.

A six-container audit also reproduced the historical retail condition where the retained GfxImage name hash does not match the IPAK index name hash: the payload still resolves uniquely by the exact retained 29-bit streamed-part `dataHash`, with zero missing and zero ambiguous candidates.

## Proof boundary

Primary identity remains exact `(GfxImage nameHash, streamed dataHash) == (IPAK nameHash, dataHash)`. A dataHash-only fallback is admitted only when the supplied retail IPAK set yields an identity-safe result and the extracted bytes independently satisfy CRC29 and retained IWI metadata. Filename similarity, nearest hash, same-name/wrong-data selection and visual matching are prohibited.

## Forward use

This reader is now the canonical transport layer for exact retail image recovery needed by Nuketown and the future all-map exporter. The immediate next pass resolves the retained packed GfxImage alias bank and then the complete visible world/static/generated/lightmap/reflection/sky dependency census across these six containers.
