# T6 audio PC-server voice allocation / limit runtime v1 — 2026-09-08

## Scope

This checkpoint closes the next sound-runtime layer for the exact SHA-pinned **T6 PC dedicated-server** build. It is intentionally not retail `t6mp.exe` authority.

Exact sources:

- `CoDMPServer_PC.exe`
  - bytes `13,711,872`
  - SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
  - PE32 image base `0x00400000`
- `CoDMPServer_PC.map`
  - bytes `9,213,148`
  - SHA-256 `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`

Reusable fail-closed verifier:

`tools/t6_pc_server_sound_voice_limit_runtime_proof_v1.py`

Machine record:

`manifests/audio/T6_PC_SERVER_SOUND_VOICE_LIMIT_RUNTIME_V1.json`

Pinned T6 field/enum names come from OpenAssetTools commit `9dca965366541504b71fa8cfb7ac049cb9b717e1`. Runtime behavior comes from the exact server machine code.

## Exact function identities

- `Snd_GetGlobalPriorityVolume`
  - `[0x008AC640, 0x008AC770)`
  - 304 bytes
  - SHA-256 `a0edfb93192d6c4f14f0990773ebd8ceb0819d64b9e60b65dd7e90cf07dbdf1e`
- `Snd_GetLowestPriority`
  - `[0x008AC770, 0x008AC8D0)`
  - 352 bytes
  - SHA-256 `eed4a0828be56265c980507d7afa878464c23f872b59d5a816e05d2e9b4d1777`
- `SND_GetPlayingInfo`
  - `[0x008ACF40, 0x008AD1B0)`
  - 624 bytes
  - SHA-256 `909e2686c849f26ff2707bd6beb3cf59b5be8a84ffe10a5c38cbeff25f011602`
- `SND_FindFreeVoice`
  - `[0x008B2570, 0x008B2680)`
  - 272 bytes
  - SHA-256 `8b253b8d2c0ff7e2c4a9944d8c8854b413e163511db7aefc65d3b15303b20f15`
- `SND_Limit`
  - `[0x008B2680, 0x008B2750)`
  - 208 bytes
  - SHA-256 `f1b33defa4519809ce91c90937b1498f94eb72cc823e28cc5445f97834937a6e`
- `SND_LimitVoice`
  - `[0x008B2750, 0x008B2850)`
  - 256 bytes
  - SHA-256 `76acc81aad1550b1ed29c3bf75912615e1ce0a2e446560276f9a81fa1201d795`

Exact MAP helpers used by these paths include:

- `SND_StopVoice` — `0x008B02B0`
- `Dvar_GetInt` — `0x00776850`
- `Dvar_GetFloat` — `0x007769E0`
- `Snd_GetGlobalPriorityVolume` — `0x008AC640`
- `Snd_GetLowestPriority` — `0x008AC770`
- `Snd_GetGlobalPriority` — `0x008C5FE0`
- `SND_GetPlayingInfo` — `0x008ACF40`
- `snd_playing_priority_boost` — `0x0798749C`
- `snd_max_stream_voice` — `0x07F1D4E0`
- `snd_max_ram_voice` — `0x07F1D4F4`

## Source-closed T6 alias layout used here

`SndAlias` is 96 bytes.

Exact fields relevant to this gate:

- alias ID: `+0x04`
- `flags0`: `+0x18`
- `limitCount`: `+0x5D`
- `entityLimitCount`: `+0x5E`

Pinned T6 `flags0` names:

- bit 9: `voiceLimit`
- bits 15–16: `loadType`
- bits 17–21: `volumeGroup`
- bits 25–26: `limitType`
- bits 27–28: `entityLimitType`

This corrects a tempting but wrong interpretation: **flags0 bit 9 is `voiceLimit`, not `stopOnPlay`**. T6 `stopOnPlay` is a separate serialized field, not this bit.

Exact T6 limit enum:

- `SND_LIMIT_NONE = 0`
- `SND_LIMIT_OLDEST = 1`
- `SND_LIMIT_REJECT = 2`
- `SND_LIMIT_PRIORITY = 3`

Exact T6 load enum:

- `SA_UNKNOWN = 0`
- `SA_LOADED = 1`
- `SA_STREAMED = 2`
- `SA_PRIMED = 3`

## `SND_FindFreeVoice`

The exact server code computes the incoming global priority as:

`Snd_GetGlobalPriority(alias, Snd_GetGlobalPriorityVolume(alias, startInfo + 0x08, -1))`

### Voice-pool split

The machine code extracts `flags0.loadType` and compares it exactly against value `1` (`SA_LOADED`).

For `SA_LOADED`:

- pool starts at voice index **10**;
- pool count is `Dvar_GetInt(snd_max_ram_voice)`.

For all other load-type values:

- pool starts at voice index **0**;
- pool count is `Dvar_GetInt(snd_max_stream_voice)`.

Within the selected range the first voice whose `g_snd.voiceAliasHash[index] == 0` is returned immediately.

### Full-pool priority replacement

If there is no free slot, `Snd_GetLowestPriority` returns the lowest `globalPriority` and channel in that same pool.

The new request may evict that voice only when:

`incomingGlobalPriority > lowestExistingGlobalPriority + Dvar_GetFloat(snd_playing_priority_boost)`

If true:

1. `SND_StopVoice(candidate)` is called;
2. the code asserts the candidate's `voiceAliasHash` is now zero;
3. the candidate index is returned for reuse.

Otherwise `SND_FindFreeVoice` returns `-1`.

So pool exhaustion is **not** unconditional oldest-voice replacement.

## `SND_Limit`: serialized global and entity limit pairs

`SND_PlaySoundAlias` makes two separate exact calls into `SND_Limit` using the selected alias:

### Global limit

- `aliasId` from `+0x04`
- `limitCount` from `+0x5D`
- `limitType = (flags0 >> 25) & 3`
- `useEnt = false`
- the already computed global priority

### Entity limit

- same alias ID
- `entityLimitCount` from `+0x5E`
- `entityLimitType = (flags0 >> 27) & 3`
- `useEnt = true`
- the same `SndEntHandle`
- the same computed global priority

`SND_GetPlayingInfo(aliasHash, &count, &oldest, &least, &isMultiple, ent, useEnt)` is the exact census helper used by the non-NONE modes.

The exact server code establishes:

- `oldest` is selected from the matching voice with the minimum integer field at exact `SndVoice +0x24`;
- `least` is selected from the matching voice with minimum exact `SndVoice.globalPriority` at `+0xE4`;
- `isMultiple` is an independently returned boolean on the entity-filtered path; its internal predicate remains recorded numerically rather than being given a stronger semantic name here.

### Limit behaviors

`SND_LIMIT_NONE`

- allows immediately;
- does not run the playing-info census.

For the other modes:

- `isMultiple == true` rejects;
- if `count < configured limitCount`, the request is allowed.

At/over the limit:

`SND_LIMIT_REJECT`

- rejects.

`SND_LIMIT_OLDEST`

- if an oldest channel is returned, calls `SND_StopVoice(oldest)`;
- then allows;
- if no valid oldest channel is returned, it still allows.

`SND_LIMIT_PRIORITY`

- requires a valid least-priority channel;
- requires:

`incomingPriority > existingLeast.globalPriority + snd_playing_priority_boost`

- if true, `SND_StopVoice(least)` and allow;
- otherwise reject.

Thus the same four exact policies are independently usable for the alias-global and alias+entity populations.

## `SND_LimitVoice`: `voiceLimit` and `volumeGroup`

This routine implements a separate gate after the two alias-count limits.

### `voiceLimit` bit 9

If the incoming alias has `flags0.voiceLimit == 1`, the server scans all **68** active voices.

For every existing voice:

- its `SndEntHandle` must equal the new request's `SndEntHandle`;
- its alias must also have `voiceLimit == 1`.

Every such existing voice is stopped with `SND_StopVoice` before the new attempt continues.

This is exact entity-scoped replacement behavior for the source-named `voiceLimit` flag.

### `volumeGroup` bits 17–21

The incoming alias's 5-bit `volumeGroup` is compared to the exact DWORD at:

`g_snd + 0x158`

If it does not equal that runtime value, this gate allows.

If it does equal that value, all active voices are scanned. If any active voice's alias has the same `volumeGroup`, the new attempt is rejected. If no such active voice exists, it is allowed.

The **PDB/source member name of `g_snd+0x158` is not yet closed**, so the checkpoint preserves this as an exact numeric runtime selector rather than assigning an inferred name.

## Newly closed facts

For this exact PC server build:

- RAM-vs-stream voice-pool selection is closed;
- free-slot search order is closed;
- full-pool priority stealing is closed;
- global alias limit behavior is closed;
- entity alias limit behavior is closed;
- `OLDEST`, `REJECT`, and `PRIORITY` replacement/rejection behavior is closed;
- source-named `voiceLimit` entity replacement is closed;
- the special `volumeGroup` exclusivity gate is closed numerically.

## Remaining boundaries

Still intentionally open:

1. the PDB/source member name for `g_snd+0x158`;
2. the PDB/source member name for exact `SndVoice+0x24`;
3. a stronger high-level name for the exact `SND_GetPlayingInfo.isMultiple` predicate;
4. the field-by-field `SND_SetVoiceStartInfo` copy/randomization path;
5. `SD_StartAlias → assetId → physical bank entry` runtime lookup/decode;
6. final hardware voice/speaker matrix behavior;
7. exact retail `t6mp.exe` equivalence.

No result here is promoted to retail-client authority.
