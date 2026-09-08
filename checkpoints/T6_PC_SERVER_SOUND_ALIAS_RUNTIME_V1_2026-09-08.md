# T6 PC dedicated-server SndAlias runtime semantics v1 — 2026-09-08

## Status

The first substantial T6-native sound runtime path is now source-closed against the exact PC dedicated-server EXE/MAP/PDB trio.

This checkpoint is **authoritative only for that exact dedicated-server build**. It is not retail `t6mp.exe` client authority.

## Exact source identity

### Executable

- `CoDMPServer_PC.exe`
- bytes: `13,711,872`
- SHA-256: `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`

### Linker MAP

- `CoDMPServer_PC.map`
- bytes: `9,213,148`
- SHA-256: `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`

The MAP timestamp is the 2013 server build and its preferred image base is `0x00400000`.

### PDB

- `CoDMPServer_PC.pdb`
- bytes: `49,196,032`
- SHA-256: `7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc`

All three files were materialized directly from the project-recorded Drive IDs and independently rehashed in the active runtime.

## Exact linked symbols

The MAP gives the previously hidden selector/playback symbols directly:

- `SND_AliasGetNeverPlayedTwice` — `0x008AA7B0`
- `SND_AliasSetNeverPlayedTwice` — `0x008AA7F0`
- `SND_AliasHasPlayed` — `0x008AA830`
- `SND_PickSoundAliasFromList` — `0x008ACC50`
- `SND_PickSoundAlias` — `0x008ACE30`
- `SND_CheckValidSecondary` — `0x008ACE80`
- `SND_FindFreeVoice` — `0x008B2570`
- `SND_PlaySoundAlias` — `0x008B2850`
- `SND_BankAliasLookupCache` — `0x008B4ED0`
- `SND_FindAlias` — `0x008B6720`
- `SND_FindContextIndex` — `0x008BC750`
- `SND_SubtitleNotify` — `0x008C2DD0`
- `SND_HashName` — `0x008C5E00`
- `SD_StartAlias` — `0x008B94C0`
- `RandWithSeed` — `0x00760DD0`
- `random` — `0x00760D80`
- `I_stricmp` — `0x0078E2C0`
- `g_snd` — `0x07E52F00`

The PDB/MAP prototype for the selector is:

```text
SndAlias *SND_PickSoundAliasFromList(
    const SndAliasList *,
    int,
    SndEntHandle)
```

## Exact byte gates

The reusable verifier is:

`tools/t6_pc_server_sound_alias_runtime_proof_v1.py`

Verifier commit:

`72d117a56b959b08e3ec105ae25ffd9752efed9a`

Promoted slices:

- `SND_PickSoundAliasFromList`
  - `0x008ACC50 .. 0x008ACE26`
  - 470 bytes
  - SHA-256 `536aac394901153948e21ca9537ef761ac448c6c18edff71606d72d0c569458c`
- `SND_CheckValidSecondary`
  - `0x008ACE80 .. 0x008ACF40`
  - 192 bytes
  - SHA-256 `10f79f80ccaffffb921c4cd42b91a8608f9f5185e1a52d91b7fe5d2d012f34e5`
- `SND_PlaySoundAlias` selected-variant / Secondary / zero-direct slice
  - `0x008B2979 .. 0x008B2A9D`
  - 292 bytes
  - SHA-256 `fccb01b12942e5f7a80a54cdcdccf0ab6fe5dd97b755c7e56afdb4ca477c134d`
- probability slice
  - `0x008B2CE4 .. 0x008B2D1F`
  - 59 bytes
  - SHA-256 `95e5426bd177a1655f88935e578419f66fec906419c432260f910f7610c3bea1`
- successful direct-start / has-played slice
  - `0x008B2F9B .. 0x008B3178`
  - 477 bytes
  - SHA-256 `ad0dd7ce8d3d91a002b4e78e3943aa3c8e6a4a36087fd4a83be28fd5389f01f4`

The three alias-state helper functions are also byte-hashed separately in the machine manifest.

## T6 variant selection — exact server behavior

The serialized layouts independently established in the FastFile census line up directly with the machine code:

### SndAliasList

- `count` — `+0x0C`
- `sequence` — `+0x10`

### SndAlias

- stride — `0x60`
- `contextType` — `+0x24`
- `contextValue` — `+0x28`
- `probability` — `+0x58`

`SND_PickSoundAliasFromList` does the following:

1. Null list or `count == 0` returns null.
2. It asserts the serialized list count is below 64 and locally caps the candidate walk at 64.
3. Each candidate is advanced at the exact `0x60`-byte SndAlias stride.
4. `contextType == 0` is accepted without a context comparison.
5. The low 12 bits of the supplied `SndEntHandle` select an entity-context row when the index is below `0x700`.
6. For nonzero context type, `SND_FindContextIndex` maps the type into the context arrays.
7. A matching entity-specific context accepts the candidate.
8. `contextValue == 0` is also accepted.
9. Otherwise the candidate must match the corresponding global context value.

The accepted candidates are stored in a local maximum-64 pointer array.

### Random-selection modes

Once there is more than one accepted candidate:

- if the first accepted candidate has **flags0 bit 31**, the selector derives a local seed from the alias-list address plus the supplied object ID and uses `RandWithSeed`;
- otherwise, when the DWORD at `g_snd + 0x288` (`0x07E53188`) is nonzero, the selector passes that exact mutable global word to `RandWithSeed`;
- otherwise it uses libc `rand()` modulo the accepted-candidate count.

For the ordinary `rand()` mode, when there are **more than two** accepted candidates, T6 retries a choice equal to the previous `SndAliasList.sequence`. The retry loop is bounded to 100 attempts.

The chosen accepted-candidate index is then written back to:

`SndAliasList.sequence (+0x10)`.

### Important separation

The selector itself does **not** evaluate:

- selected-variant probability;
- never-played-twice state.

Those are later gates in `SND_PlaySoundAlias`.

## Never-played-twice runtime state

The exact helpers separate two bits:

- `SND_AliasGetNeverPlayedTwice` returns **flags1 bit 0**;
- `SND_AliasHasPlayed` returns **flags1 bit 1**.

Despite its PDB name, `SND_AliasSetNeverPlayedTwice(alias, bool)` does not modify bit 0. Its exact machine code updates **flags1 bit 1** to the supplied boolean.

So bit 0 is the enable/authoring state and bit 1 is runtime "has played" state.

`SND_PlaySoundAlias` performs this after choosing a variant:

```text
if (NeverPlayedTwice(alias) && HasPlayed(alias))
    fail
```

This happens **before Secondary handling**.

A full `.text` relative-call scan finds exactly three calls to the mutating helper:

- `0x008B30A3`
- `0x008B3136`
- `0x008B315C`

All three are inside `SND_PlaySoundAlias`, and all pass literal `true`.

There are no calls through this helper with `false` anywhere in the exact server `.text`.

On a new direct-sound path, the bit is set only after `SD_StartAlias` succeeds; failed voice allocation/start paths do not pass through these success setters.

This does **not** prove there is no unrelated raw/direct write to the same bit elsewhere. The authoritative negative is specifically that the named setter has no false call site in this executable.

## Secondary ordering — T6-specific result

This differs materially from the historical T5 search fingerprint.

On this exact T6 server, the order is:

```text
pick selected variant
→ never-played-twice gate
→ selected variant secondaryName
→ selected variant direct assetId check
```

Therefore **Secondary belongs to the selected variant at runtime**, not merely to `SndAliasList.head` before selection.

### Secondary lookup

For a non-null selected `secondaryName`:

```text
secondaryName
→ SND_HashName
→ SND_BankAliasLookupCache
```

If that lookup returns null, T6 skips Secondary playback and continues processing the selected primary variant.

### SND_CheckValidSecondary

For a found secondary list:

1. It compares **flags0 bit 0** between the selected primary alias and the immediate secondary-list head.
2. A looping/non-looping mismatch is rejected.
3. It follows downstream `secondaryName` references through `SND_FindAlias`, using each found list head for validation.
4. `I_stricmp` is used to reject a chain whose downstream Secondary resolves back to the primary alias name.
5. The validation walk is bounded to 10 downstream steps.

If validation succeeds, the **complete Secondary alias list** is recursively passed to `SND_PlaySoundAlias`.

The recursive Secondary playback result is not returned as the primary playback ID.

## `assetId == 0` runtime behavior

This closes the most important open question from the 4,094-row zero-FileSource census for the exact server build.

After optional valid Secondary recursion, T6 checks the **selected variant** `assetId` at `SndAlias + 0x10`.

When `assetId == 0`:

- no direct physical sound is started for the selected primary variant;
- if the selected alias has a non-null subtitle pointer, T6 calls:

```text
SND_SubtitleNotify(subtitle, 5000)
```

- the primary `SND_PlaySoundAlias` call returns `-1`.

The zero-direct return happens before the successful direct-start runtime-has-played setter paths.

Therefore on this exact server, a zero-FileSource alias can still trigger a valid Secondary as a side effect even though the primary itself produces no direct bank playback and returns no primary playback ID.

This is substantially stronger than the earlier serialized/OAT statement "assetId==0 means no direct FileSource."

## Probability semantics

Probability is evaluated only after a variant has already been selected.

The exact selected field is the byte at:

`SndAlias + 0x58`.

The exact server constant at `0x00B93F54` is raw bytes:

`81 80 80 3B`

which is float:

`0.003921568859368563 ≈ 1/255`.

Therefore:

```text
p = uint8(probability) * (1 / 255)
```

The machine code then behaves as follows:

- when `p > 0`, call `random()`;
- reject the selected alias only when `random() > p`;
- when `p == 0`, bypass the random rejection gate entirely.

So a stored probability byte of zero is **not** a 0% playback chance in this server path. It disables this random rejection gate.

Probability does not influence which variant is chosen from the alias list; it can reject the already-selected variant afterward.

## Relationship to the whole-game audio closure

Before this runtime pass, the archive-level audio work had already closed:

- 215/215 FastFile SndAlias structural coverage;
- 116/116 physical SABS/SABL banks;
- 24,481/24,481 nonzero alias physical-ID joins;
- all 670 duplicate physical IDs as exact payload-byte-identical;
- 4,094 zero-direct alias occurrences;
- 1,334/1,334 opaque Secondary pointers resolved natively;
- complete 1,470-occurrence / 44-name Secondary graph;
- both ownerless Secondary target names proven to have zero native Name owners in the complete archive SoundBank universe.

The present checkpoint adds exact **runtime ordering and selected-variant behavior** for the PC dedicated server.

## Durable artifacts

Machine summary:

`manifests/audio/T6_PC_SERVER_SOUND_ALIAS_RUNTIME_V1.json`

Verifier:

`tools/t6_pc_server_sound_alias_runtime_proof_v1.py`

## Still open

The following are intentionally not promoted here:

- retail `t6mp.exe` equivalence;
- `SndAlias.stop_on_play` runtime semantics;
- a human-readable PDB member name for the exact mutable seed word at `g_snd + 0x288`;
- complete lower-level voice/driver mixing semantics;
- whether the two archive-ownerless Secondary names are reachable or intentionally historical;
- any assumption that T5 and T6 Secondary/selector behavior are interchangeable.

## Proof boundary

All T6 behavior promoted in this checkpoint comes from:

1. exact SHA-pinned PC server EXE;
2. exact SHA-pinned linker MAP naming the routines and addresses;
3. exact SHA-pinned PDB as matching symbol provenance;
4. exact machine-code range hashes and call-site census.

Historical T5 source was used only to locate the selector concept. The actual T6 result was independently recovered from the T6 MAP and executable and notably differs from the T5 search path in Secondary ordering.
