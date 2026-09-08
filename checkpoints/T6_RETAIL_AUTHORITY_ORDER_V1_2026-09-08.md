# T6 retail authority order v1 — 2026-09-08

## Production authority

For weapon, character, material, audio and gameplay export work, the authoritative retail value/asset source order is:

1. **Current SHA-pinned retail files retrieved from `r2.houseofkublai.com` in GitHub Actions** — FastFiles, IPAKs, SABS/SABL and any other exact current retail payloads.
2. Exact native decoding/dumping of those files through source-pinned tools, with independent structural/hash canaries where available.
3. Exact retail-client executable semantics only when the corresponding client binary is itself independently identity-pinned to the intended retail build.

## Legacy server/PDB boundary

The historical `CoDMPServer_PC.exe` / PDB / MAP set is an older dedicated-server build. It is retained because symbols and decompiled routines are extremely useful for reverse-engineering:

- discovering structure/enum/routine names;
- identifying candidate field meanings;
- locating likely runtime composition algorithms;
- guiding targeted searches in newer retail evidence.

It is **not** production authority for current retail values, FastFile precedence, attachment applicability, camo population, or retail-client runtime behavior.

A server-derived formula may be emitted only as guidance/provisional semantic provenance until independently reproduced from current retail-client evidence or an equivalently strong current source. It must never overwrite the exact raw values decoded from the current R2 retail files.

## Current retail client availability

Historical intended retail client identity:

- `t6mp.exe`
- 12,850,328 bytes
- SHA-256 `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`

The strict R2 path probe on 2026-09-08 tested 12 explicit historical HTTP paths and found zero reachable candidates. Therefore current work must not silently substitute the old server executable for the missing client bytes.

## Exporter consequence

Every exported gameplay/equip property carries separate provenance for:

- `rawRetailValue` — exact value decoded from an R2-authoritative retail asset;
- `effectiveValue` — present only when the composition rule is closed strongly enough for the requested authority level;
- `semanticAuthority` — for example `retail_client_exact`, `source_closed`, `legacy_server_guidance`, or `unresolved`.

The canonical base weapon remains immutable. Attachments and camos produce derived equip states without replacing or normalizing away the exact current retail source records.
