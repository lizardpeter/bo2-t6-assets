# T6 audio PC-server alias-selection runtime v1 — 2026-09-08

## Scope and proof boundary

This checkpoint records exact runtime behavior from the SHA-pinned **T6 PC dedicated server**. It is **not** retail-client authority and must not be promoted to `t6mp.exe` behavior until corresponding retail-client bytes are independently closed.

Exact active server references:

- `CoDMPServer_PC.exe` — 13,711,872 bytes — SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
- `CoDMPServer_PC.pdb` — 49,196,032 bytes — SHA-256 `7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc`
- `CoDMPServer_PC.map` — 9,213,148 bytes — SHA-256 `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`
- PDB configuration: `codmpRelease DedicatedServer - PC`
- server evidence commit used for project metadata: `504c0d8516c50195342c8a064b2f2571b109659d`

All three reference artifacts were retrieved from the Drive IDs already pinned by the server-decompile project and independently re-hashed before analysis.

The T6 OpenAssetTools header at commit `9dca965366541504b71fa8cfb7ac049cb9b717e1` is used only to attach declared field names to offsets independently touched by machine code. Runtime semantics below come from the exact server executable.

## Actions workflow failure reclassified

The attempted source-side PDB inventory run `34184093168`, job `101928841779`, is an **infrastructure-only failure**. GitHub reports:

- `runner_id = 0`
- empty runner name
- `steps = []`
- failure within roughly two seconds

Therefore no checkout, `git cat-file`, gzip validation, parser, or evidence command ran. This failure is not evidence about the PDB inventories and is retired from the reversal path.

## Complete `snd.obj` scale

The exact linker inventory records:

- 88 functions
- 262 symbols
- 238 public symbols
- 24 static symbols
- 174 data symbols
- 12 inline symbols

This explains why the leaf-oriented reconstruction batches did not contain the central alias-selection/playback routine.

## Exact runtime cone

The linker MAP closes these functions and spans:

- `SND_PickSoundAliasFromList` — `0x008ACC50` — 0x1E0 bytes — SHA-256 `1ce10bd622bbe38e5963ee62944ea0b996cb7ed90db7f49039160dc69000ac1e`
- `SND_PickSoundAlias` — `0x008ACE30` — 0x50 bytes — SHA-256 `bb28e65fa8fb43d79089afad652b5f805ec5ffd26cbba95fba083df1a18968f6`
- `SND_CheckValidSecondary` — `0x008ACE80` — 0xC0 bytes — SHA-256 `10f79f80ccaffffb921c4cd42b91a8608f9f5185e1a52d91b7fe5d2d012f34e5`
- `SND_SetVoiceStartInfo` — `0x008B1A40` — 0xB30 bytes — SHA-256 `27f8bfa15b3e1ecadfba09f10ed012fa9b7d92569b40abd6ea2b52b101b07414`
- `SND_FindFreeVoice` — `0x008B2570` — 0x110 bytes — SHA-256 `8b253b8d2c0ff7e2c4a9944d8c8854b413e163511db7aefc65d3b15303b20f15`
- `SND_PlaySoundAlias` — `0x008B2850` — 0x980 bytes — SHA-256 `d8c4616935b59272d8382d42bc7487aaee2abe83d431f8b774f06a4da2f585a5`

Supporting exact helpers:

- `SND_AliasGetNeverPlayedTwice` — `0x008AA7B0`
- `SND_AliasSetNeverPlayedTwice` — `0x008AA7F0`
- `SND_AliasHasPlayed` — `0x008AA830`
- `SND_BankAliasLookupCache` — `0x008B4ED0`
- `SND_FindAlias` — `0x008B6720`
- `SND_HashName` — `0x008C5E00`
- `SD_StartAlias` — `0x008B94C0`

## Exact caller closure for the selection/playback gates

A full `.text` near-call census followed by MAP owner resolution establishes:

- every direct call to `SND_AliasGetNeverPlayedTwice` → `SND_PlaySoundAlias`
- every direct call to `SND_AliasHasPlayed` → `SND_PlaySoundAlias`
- every direct call to `SND_AliasSetNeverPlayedTwice` → `SND_PlaySoundAlias` (three callsites)
- every direct call to `SND_CheckValidSecondary` → `SND_PlaySoundAlias`
- every direct call to `SND_FindFreeVoice` → `SND_PlaySoundAlias`
- `SND_PlaySoundAlias` directly calls `SND_PickSoundAliasFromList`
- `SND_PickSoundAlias` also calls `SND_PickSoundAliasFromList`; its observed public caller is `SND_Whizby`
- `SND_SetVoiceStartInfo` is called by `SD_StartAlias`

The general playback path therefore forms one exact runtime cone:

`SND_PlaySoundAlias → SND_PickSoundAliasFromList → selection gates → secondary validation → limits → SND_FindFreeVoice → SD_StartAlias → SND_SetVoiceStartInfo`

## Variant selection algorithm

Exact x86 establishes:

- `SndAlias` stride = `0x60` bytes.
- `SndAliasList.head` = +0x08, `count` = +0x0C, runtime `sequence` = +0x10.
- null list or count zero returns null.
- count >= 64 asserts `(aliasList->count < MAX_VARIANTS)` and the examined count is clamped to 64.
- each alias is filtered by `contextType` (+0x24) and `contextValue` (+0x28):
  - context type 0 is eligible;
  - an exact entity-context value match is eligible;
  - context value 0 is a wildcard;
  - otherwise the global SND context value for that context type must equal the alias context value.
- zero eligible aliases returns null.
- one eligible alias is returned directly.
- for multiple eligible aliases, flags0 bit 31 selects the entity-variant seeded path.

Pinned T6 layout naming identifies flags0 bits 29–31 as `randomizeType` and `SND_RANDOMIZE_ENTITY_VARIANT = 4`, so the exact bit-31 branch is the entity-variant randomization mode.

In that mode the server seeds `RandWithSeed` from the alias-list pointer plus the picker integer argument. On the `SND_PlaySoundAlias` path that integer is exactly `SndEntHandle & 0xFFF`.

Otherwise:

- if the global sound seed is nonzero, `RandWithSeed` is used;
- otherwise CRT `rand()` is used;
- with more than two eligible aliases, the unseeded path retries up to 100 times to avoid the previous `SndAliasList.sequence` index;
- the selected eligible index is written back to `sequence`.

## Never-play-twice is distinct from variant randomization

Exact helper bytes prove:

- flags1 bit 0 at `alias+0x1C` is the `neverPlayTwice` property.
- flags1 bit 1 is mutable played-state:
  - `SND_AliasHasPlayed` reads it;
  - `SND_AliasSetNeverPlayedTwice` actually writes that bit despite its misleading symbol name.

`SND_PlaySoundAlias` checks the pair immediately after selecting an alias. If `neverPlayTwice` is set and `hasPlayed` is already set, the function returns `-1` before secondary or driver playback.

All observed successful normal exits set the played-state bit to 1. If `SD_StartAlias` returns `-1`, the allocated voice is cleaned up and the function exits failure without that success-state update.

Therefore flags0 bit31 entity-variant selection and flags1 bit0/bit1 never-play-twice state are separate mechanisms.

## Probability gate

Pinned T6 layout names `alias+0x58` as the one-byte `probability` field. Exact machine code multiplies it by `0.003921568859...`, exactly `1/255`.

Behavior:

- value 0 bypasses stochastic rejection;
- otherwise the engine calls its `random()` float generator;
- the alias attempt is rejected only when `random() > probability / 255.0`.

This is a playback gate after alias selection, not part of the eligible-variant picker itself.

## Secondary-alias behavior

`SND_PlaySoundAlias` reads `secondaryName` at `alias+0x0C` and performs:

`secondaryName → SND_HashName → SND_BankAliasLookupCache`

If the cache/lookup returns null, the server **does not fail the primary sound**. It skips secondary recursion and continues the primary play path.

If a secondary list is found, its head alias is passed to `SND_CheckValidSecondary` before recursive playback. The validator proves:

- looping primary → non-looping secondary is rejected with an explicit error;
- non-looping primary → looping secondary is rejected with an explicit error;
- the secondary-name chain is followed and compared back to the starting primary alias name;
- a return to the starting name is rejected as infinite recursion;
- the validation walk is bounded to at most ten secondary-chain hops.

The underlying `SND_BankAliasLookupCache` itself also returns null for a known cache miss and caches the negative hash state, confirming that the null branch is an intentional lookup outcome.

### Consequence for the two archive-ownerless `secondaryName` records

The earlier native SoundBank census proved no owner in the exact retail archive SoundBank universe for:

- `wpn_wa2000_bass_swt_silencer`
- `zmb_tomahawk_sparks`

This runtime closure adds a **PC-server-only** behavioral result: if those names likewise resolve to no loaded alias at runtime, the secondary layer is omitted while the primary alias attempt continues.

This does **not** prove retail-client behavior and does **not** prove that another runtime-only source cannot provide those aliases in another build/environment.

## Durable machine-readable record

`manifests/audio/T6_AUDIO_PC_SERVER_ALIAS_SELECTION_RUNTIME_V1.json`

Creation commit: `483e92670a25150142228196eccfb80eb2904f7d`

## Next exact gates

1. Reverse `SND_SetVoiceStartInfo` field-by-field and map every copied/randomized `SndAlias` field into `SndStartAliasInfo` / live voice state.
2. Reverse `SND_FindFreeVoice`, `SND_Limit`, and `SND_LimitVoice` to close channel/entity/global concurrency semantics.
3. Trace the `assetId` path from selected alias through `SD_StartAlias` into asset-bank lookup/decode.
4. Only after the server path is closed, reproduce these specific gates against exact retail `t6mp.exe` bytes before promoting them to retail-client authority.
