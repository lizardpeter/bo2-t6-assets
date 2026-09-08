# T6 audio PC-server assetId → physical bank → driver voice runtime v1 — 2026-09-08

## Scope

This checkpoint closes the exact runtime handoff from a selected `SndAlias.assetId` through the PC dedicated-server sound-bank lookup layer and into RAM/stream `sd_voice` allocation.

Authority remains deliberately narrow: **the exact SHA-pinned T6 PC dedicated-server build only**. Nothing here is promoted to retail `t6mp.exe` authority without a separate equivalence proof.

Exact sources:

- `CoDMPServer_PC.exe`
  - 13,711,872 bytes
  - SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
  - PE32 image base `0x00400000`
- `CoDMPServer_PC.map`
  - 9,213,148 bytes
  - SHA-256 `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`

Reusable fail-closed verifier:

`tools/t6_pc_server_sound_assetid_runtime_proof_v1.py`

Machine record:

`manifests/audio/T6_PC_SERVER_SOUND_ASSETID_RUNTIME_V1.json`

The generated proof JSON from the green Actions run is SHA-256:

`ecbf515623f05d10974504dec3f076e51ce906a96c09a6b7b48ef7c8d2480c4a`

Green verification run:

- Actions run `34248592499`
- job `102136885319`
- artifact `T6_AUDIO_ASSETID_RUNTIME_PROBE_V2`
- artifact ID `10065032251`
- artifact ZIP SHA-256 `afafd5ee3bc462902ae1b7cc1fe331510404157d0d71d37b7e43e69275541327`

Verifier repair/finalization commit:

`b38d679bb6e3b0a8df5a1de06cd1a8de3f93307a`

Machine-record commit:

`ec82f7b1ee8a1b5390c9dd296440a6043c127b39`

## Exact runtime symbols

- `SND_AssetBankFindEntry` physical — `0x008B4060`
- overloaded runtime `SND_AssetBankFindEntry` — `0x008B48A0`
- `SND_AssetBankFindStreamed` — `0x008B4960`
- `SND_AssetBankFindLoaded` — `0x008B4980`
- `SD_StartAlias` — `0x008B94C0`
- `SND_SetVoiceStartInfo` — `0x008B1A40`
- `SD_VoiceAllocateRam` — `0x008BA310`
- `SD_VoiceAllocateStream` — `0x008BA4D0`
- `SD_VoiceHasData` — `0x008BA610`
- `SD_VoiceStart` — `0x008BA620`

Loaded-entry metadata helpers:

- `SND_AssetBankGetFrameRate` — `0x008B4100`
- `SND_AssetBankGetChannelCount` — `0x008B41B0`
- `SND_AssetBankGetLooping` — `0x008B41C0`
- `SND_AssetBankGetFrameCount` — `0x008B41D0`
- `SND_AssetBankGetLengthMs` — `0x008B41E0`

## Exact function identities

- physical `SND_AssetBankFindEntry`
  - `[0x008B4060, 0x008B4100)`
  - 160 bytes
  - SHA-256 `4d58506f53dad05314ac5767df0bcfbc7103f8b9834b3003a33ab03f126176b4`
- runtime `SND_AssetBankFindEntry`
  - `[0x008B48A0, 0x008B495E)`
  - 190 bytes
  - SHA-256 `d197d45e6e25fd7164837fd1ba9ce780f71fff8ebdd0ae042dcc94328b67ab2c`
- `SND_AssetBankFindStreamed`
  - `[0x008B4960, 0x008B497B)`
  - 27 bytes
  - SHA-256 `7bbd5e43740391b1ed04ceb9f6c9b3660853fed4c64c7780762a5936499f6c64`
- `SND_AssetBankFindLoaded`
  - `[0x008B4980, 0x008B4A31)`
  - 177 bytes
  - SHA-256 `bdca163e63805518d60b7c166cefda588c60d3e7aba5ab67838f261be86a6941`
- `SD_StartAlias`
  - `[0x008B94C0, 0x008B9801)`
  - 833 bytes
  - SHA-256 `4ed142af3829da86eecb8d5e2db32e53db64decf3651a03bbcfff3c30ff97738`
- `SD_VoiceAllocateRam`
  - `[0x008BA310, 0x008BA4C1)`
  - 433 bytes
  - SHA-256 `9a82ead78d8745ac6365ccebee0ee6e754e17d208e0b2fc3dd035357e4099d6c`
- `SD_VoiceAllocateStream`
  - `[0x008BA4D0, 0x008BA559)`
  - 137 bytes
  - SHA-256 `356f708d145dcf3b03424abbc5bf88cad925b6da254d2fe55c050df33edcc98f`
- `SD_VoiceHasData`
  - `[0x008BA610, 0x008BA620)`
  - 16 bytes
  - SHA-256 `4edbbea44f2180c146797f430e3ae02de67ac019daf6d847fc26162e0d89a247`

## `SndAlias.assetId` is the physical lookup key

`SD_StartAlias` reads the selected alias's serialized 32-bit value at exact `SndAlias+0x10` and forwards it unchanged to the relevant sound-bank lookup path.

For stream-pool voices (`voiceIndex <= 9`), the exact machine code additionally requires `flags0.loadType` bits 15–16 to be either:

- `SA_STREAMED = 2`, or
- `SA_PRIMED = 3`.

It then calls:

`SND_AssetBankFindStreamed(alias.assetId, ...)`

For RAM-pool voices (`voiceIndex > 9`) it calls:

`SND_AssetBankFindLoaded(alias.assetId, ...)`

This is the runtime counterpart to the already established authoring/package relationship: the serialized alias `assetId` is not a loose label. It is the exact physical bank-entry lookup key.

## Physical `SND_AssetBankFindEntry`

The lower physical routine at `0x008B4060` is now closed exactly.

It is **not a hash scan**. It performs an inclusive low/high binary search over a sorted array of fixed-size physical entries:

- requested key: 32-bit `assetId`;
- entry stride: **20 bytes**;
- entry ID field: dword at entry `+0x00`;
- midpoint: `(low + high) / 2`;
- entry address: `base + midpoint * 20`;
- equality: stores the exact `SndAssetBankEntry*` and returns true;
- exhaustion: returns false.

The routine also asserts that the requested ID is nonzero before starting the search.

That sharpens the earlier zero-ID boundary:

- `assetId == 0` is still **not** a request to follow Secondary inside `SD_StartAlias`;
- Secondary recursion belongs to the upstream alias-playback layer;
- if zero reaches the physical lookup, the physical lookup's own nonzero invariant is violated.

## Streamed/primed runtime-bank lookup

The overloaded `SND_AssetBankFindEntry` at `0x008B48A0` scans exactly **32** runtime bank slots under critical section 11.

For the streamed selector it:

1. chooses the streamed descriptor;
2. requires its runtime valid/loaded byte;
3. obtains its entry count and derives its physical entry-table base;
4. passes the exact 32-bit alias `assetId` to physical `SND_AssetBankFindEntry`;
5. returns the exact physical entry on success.

`SND_AssetBankFindStreamed` is a 27-byte exact wrapper that sets the overloaded routine's final selector argument to `true` and forwards `assetId` unchanged.

## Loaded runtime-bank lookup

`SND_AssetBankFindLoaded` also scans exactly **32** runtime bank slots under critical section 11.

For each candidate bank it uses:

- entry count at bank `+0x1270`;
- entry-table pointer at bank `+0x1274`.

It calls physical `SND_AssetBankFindEntry` with the exact alias `assetId`.

A found entry is usable only when:

`entry+0x08 != 0xFFFFFFFF`

When a data pointer is requested, the exact reconstruction is:

`loadedData = bankLoadedBase(+0x127C) + entryOffset(+0x08)`

## `SD_StartAlias` loaded validation

Before RAM allocation, the exact server path obtains physical metadata through the source-named `SND_AssetBankGet*` helpers.

It explicitly requires:

`frameRate == 48000`

and requires the physical entry's looping state to equal the selected alias's source-defined looping flag:

`SND_AssetBankGetLooping(entry) == (SndAlias.flags0 & 1)`

The path also obtains exact channel count, frame count and length information.

## Driver voice allocation

### RAM

`SD_VoiceAllocateRam`:

1. acquires an `sd_voice` through exact helper `0x008BA1C0`;
2. returns null if no `sd_voice` is available;
3. initializes RAM voice fields and validates channel count 1 or 2;
4. calls exact lower helper `0x008B9B20`;
5. if that setup fails, marks state `3` and returns null;
6. on success sets `sd_voice+0x08 = 1` (data ready), state `2`, and returns the exact `sd_voice*`.

### Stream

`SD_VoiceAllocateStream`:

1. uses the same `0x008BA1C0` acquisition helper;
2. initializes stream state through exact helper `0x008B9D10`;
3. treats nonzero `sd_voice+0x44` as setup failure and releases/fails;
4. otherwise calls exact lower helper `0x008B9B20`;
5. copies physical entry byte `+0x11` to `sd_voice+0x10C`;
6. sets state `2` and returns the exact `sd_voice*`.

The names/prototypes and deeper semantics of `0x008BA1C0`, `0x008B9B20`, and `0x008B9D10` remain intentionally unresolved in this checkpoint.

## Allocation handoff back into logical voices

For both stream and RAM paths, `SD_StartAlias` stores the returned `sd_voice*` into the per-logical-voice driver array.

If allocation returns null:

- `SND_StopVoice(logicalVoice)` is called;
- the start fails.

If allocation succeeds:

- `SND_SetVoiceStartInfo(logicalVoice, startInfo)` is called.

On the RAM path, `SD_VoiceHasData` is exact and simply tests whether `sd_voice+0x08 != 0`; the later start path reaches exact `SD_VoiceStart`.

## Newly closed chain

The runtime chain is now source/machine closed for the pinned server build through:

`selected SndAlias`

`→ SndAlias+0x10 assetId`

`→ 32-slot runtime bank selection`

`→ sorted 20-byte physical SndAssetBankEntry binary search`

`→ loaded offset / streamed entry handoff`

`→ physical metadata validation`

`→ SD_VoiceAllocateRam / SD_VoiceAllocateStream`

`→ sd_voice* stored on the logical voice`

`→ SND_SetVoiceStartInfo`

No naming, adjacency, or heuristic matching is used to bridge those stages.

## Remaining exact frontier

The next narrowly bounded targets are:

1. resolve the MAP/PDB names and exact prototypes for `0x008BA1C0`, `0x008B9B20`, and `0x008B9D10`;
2. continue below those helpers into the codec/backend data-open path;
3. close codec-specific sample/block decode semantics for the SABS/SABL payloads;
4. separately establish retail `t6mp.exe` equivalence where needed.

The proof boundary remains fail-closed. No server behavior is silently promoted to retail-client authority.