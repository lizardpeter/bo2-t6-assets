# T6 Rust FastFile performance checkpoint — 2026-09-25

Pinned retail input:

- file: `mp_nuketown_2020.ff`
- encrypted bytes: **38,472,064**
- encrypted SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- XChunks: **4,730**
- expanded bytes: **154,653,476**
- expanded SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`
- benchmark iterations: **10**
- green GitHub Actions run: **36160908939**

All variants that emit the expanded SHA-256 produced the same exact output digest.

## Same-run measurements

| Variant | Seconds / 10 | Encrypted MiB/s | Expanded MiB/s |
| --- | ---: | ---: | ---: |
| scalar Salsa20 + miniz, expanded hash | 4.023534 | 91.188 | 366.566 |
| **original production-equivalent**: scalar + miniz + encrypted and expanded SHA-256 | **4.639392** | **79.083** | **317.906** |
| scalar Salsa20 + zlib-rs | 3.584300 | 102.363 | 411.486 |
| RustCrypto Salsa20 + miniz | 4.066932 | 90.215 | 362.654 |
| RustCrypto Salsa20 + zlib-rs | 3.471148 | 105.699 | 424.900 |
| RustCrypto Salsa20 + zlib-rs + safe output reserve | 3.415434 | 107.424 | 431.831 |
| **optimized production-equivalent**: winner + encrypted and expanded SHA-256 | **3.704618** | **99.038** | **398.122** |
| **runtime path**: winner, no reporting-only SHA-256 summaries | **2.626157** | **139.709** | **561.616** |
| winner + encrypted SHA-256 only | 2.908921 | 126.129 | 507.023 |

## Direct production comparisons

- optimized production-equivalent throughput vs original production-equivalent:
  - **1.252x**
  - wall time: **4.639392 -> 3.704618 s**
  - wall-time reduction: **20.15%**

- hash-free runtime throughput vs original production-equivalent:
  - **1.767x**
  - wall time: **4.639392 -> 2.626157 s**
  - wall-time reduction: **43.39%**

- hash-free runtime vs optimized production-equivalent:
  - **1.411x**
  - wall time: **3.704618 -> 2.626157 s**
  - wall-time reduction: **29.11%**

## Production changes justified by the matrix

1. Use `flate2` with the pure-Rust `zlib-rs` backend.
2. Use RustCrypto `salsa20` instead of the handwritten scalar block loop.
3. Pre-scan XChunk lengths and best-effort reserve the expanded stream upper bound.
4. Preserve the existing full-summary APIs for audit/CLI use.
5. Provide runtime APIs that skip only the reporting SHA-256 passes. They still perform the correctness-critical Salsa20 decrypt, raw DEFLATE, per-chunk SHA-1 evolution, and (for the verified runtime API) official Treyarch RSA-PSS verification.

The public performance lab contains only already-public T6 format/crypto behavior. Private project-specific runtime code remains in `lizardpeter/Rust-test`.
