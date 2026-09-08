# T6 retail-client archive locator v1 — 2026-09-08

## Status

The complete public T6 archive already used as the source universe for the validated 116-bank audio corpus has now been exhaustively checked for the exact pinned retail `t6mp.exe` identity.

Result: **the client executable is not present in this archive**.

This is a bounded negative result, not a global absence claim.

## Exact target

Expected retail client identity:

- filename/reference: `t6mp.exe`
- bytes: **12,850,328**
- SHA-256: `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`

## Source universe

Archive:

`https://cdn.jordanlindsay.com.au/pluto_t6_full_game.zip`

The ZIP64 central directory contains exactly **534 entries**.

This is the same public archive whose 116 SABS/SABL files were independently CRC-verified and structurally validated for the complete 25,446-entry PC audio corpus.

## Durable proof

- workflow: `.github/workflows/t6_retail_client_archive_locator_v1.yml`
- creation commit: `81061518fec1d32a073fdacbb810e4dd616583fc`
- green run: `34256387012`
- job: `102163159685`
- artifact: `T6_RETAIL_CLIENT_ARCHIVE_LOCATOR_V1`
- artifact ID: `10068029233`
- artifact ZIP SHA-256: `a55d4f0900d6199927d777e21de6e970533d515e8f7076413d8396f76c2b0f2f`
- compact manifest: `manifests/audio/T6_RETAIL_CLIENT_ARCHIVE_LOCATOR_V1.json`

The locator enumerates the exact ZIP64 central directory, identifies executable-like candidates, CRC-verifies every extracted candidate, and SHA-256 hashes the resulting bytes.

## Exact census

- ZIP entries: **534**
- executable-like candidates: **7**
- candidates of exactly 12,850,328 bytes: **0**
- exact expected retail SHA matches: **0**

The seven hashed candidates are only Bink/redistributable support files:

1. `binkw32.dll` — 215,040 bytes — `1ea5e8075bd12651e51d482fda4f16e9f0382a9cb3a46cd9b2286af98c2e5376`
2. `redist/.NETFramework.exe` — 129,746 bytes — `f15c4b99f08d42b28dcf30f0b27acfd44204d3433f854a500e6088a80dc22915` — not an MZ image
3. `redist/DirectX/DSETUP.dll` — 95,576 bytes — `2a61679eeedabf7d0d0ac14e5447486575622d6b7cfa56f136c1576ff96da21f`
4. `redist/DirectX/dsetup32.dll` — 1,566,040 bytes — `fb0e534f9b0926e518f1c2980640dfd29f14217cdfa37cf3a0c13349127ed9a8`
5. `redist/DirectX/DXSETUP.exe` — 517,976 bytes — `8f47d7121ef6532ad9ad9901e44e237f5c30448b752028c58a9d19521414e40d`
6. `redist/vcredist_x86.exe` — 4,995,416 bytes — `66b797b3b4f99488f53c2b676610dfe9868984c779536891a8d8f73ee214bc4b`
7. `redist/VC_redist.x86.exe` — 14,427,696 bytes — `b4d433e2f66b30b478c0d080ccd5217ca2a963c16e90caf10b1e0592b7d8d519`

No candidate is even the expected byte length, so no file from this archive can satisfy the pinned retail identity.

## What this changes

The earlier failed direct-R2 lookup is no longer the only evidence about the public Plutonium corpus. We now know the **complete 534-entry archive itself does not contain the client executable**.

That means further retail mixer work should not spend time guessing another path inside this ZIP. The next client search must move to a genuinely different source universe: historical Plutonium distributions/caches, modding mirrors, GitHub releases/assets, other public archives, or user-retained retail files.

## Proof boundary

Authoritative statement:

> The exact 12,850,328-byte retail `t6mp.exe` with SHA-256 `11c7542f…24d5d1` is absent from this specific 534-entry public ZIP64 archive.

Not established:

- global absence of the executable;
- absence from other Plutonium mirrors or historical installers;
- absence from private/user-owned retail installations;
- retail mixer or decoder function addresses.

Do not turn this bounded negative control into a global absence claim.
