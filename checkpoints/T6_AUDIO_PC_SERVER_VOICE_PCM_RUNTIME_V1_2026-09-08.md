# T6 audio PC-server voice/PCM runtime v1 — 2026-09-08

## Status

The exact dedicated-server path from the physical audio-bank format byte through decoder allocation, stream-source initialization, high-level voice allocation/start and the basic voice state fields is now machine-closed.

This checkpoint sits immediately below the already-closed physical codec result:

- format `0` = `SND_ASSET_FORMAT_PCMS16`
- format `8` = `SND_ASSET_FORMAT_FLAC`
- complete retained PC corpus = **4,746 PCMS16 + 20,700 FLAC = 25,446 physical entries**

## Exact source identity

- `CoDMPServer_PC.exe`: **13,711,872 bytes**
- EXE SHA-256: `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
- linker MAP: **9,213,148 bytes**
- MAP SHA-256: `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`

## Durable proof

- verifier: `tools/t6_pc_server_sound_voice_pcm_runtime_proof_v1.py`
- workflow: `.github/workflows/t6_audio_voice_pcm_runtime_proof_v1.yml`
- green run: `34256138470`
- artifact: `T6_AUDIO_PC_SERVER_VOICE_PCM_RUNTIME_V1`
- artifact ID: `10067925188`
- artifact ZIP digest: `sha256:80d0c632c801fe101187314e90954359565cc3a6928e52f957fb117f213f450f`
- result JSON SHA-256: `5a86460fa54bdbe8a6f388ca060be73f8101f9373490dd4899ba426e2b2f4ac8`
- compact record: `manifests/audio/T6_AUDIO_PC_SERVER_VOICE_PCM_RUNTIME_V1.json`

The verifier is fail-closed: it SHA-gates both source files, requires exact linker symbols, then compares exact instruction bytes/call targets. Two earlier runs correctly failed when the verifier itself used an over-wide byte window; those expectations were corrected against the independently retained disassembly rather than weakening the runtime claims.

## Decoder handoff

The two-argument `SD_DecoderAllocate` wrapper at `0x008B9B20` reads `SndAssetBankEntry+0x13` and accepts the two PC formats observed in the complete bank corpus:

- `0` -> decoder-instance pool `0x00DE3054`
- `8` -> decoder-instance pool `0x00DE3E64`

Both route into the generic `SD_DecoderAllocate` at `0x008B9A10`.

Combined with the independent source/payload closure, this gives the practical PC decode contract:

`SndAssetBankEntry.format(+0x13) -> 0/PCMS16 or 8/FLAC -> decoder allocation`

## Stream source initialization

`SD_SourceInitStream` is linker-named at `0x008B9D10`.

It:

1. requires `SndAssetBankEntry+0x11` to be either `1` or `2`;
2. calls `SD_StreamAllocate` at `0x008B9E20`;
3. stores the returned stream pointer at `sd_source+0x18`;
4. on allocation failure sets source offsets `+0x20`, `+0x28`, and `+0x2C` to `1`;
5. on success clears those three fields and writes `bool(entry+0x12 != 0)` to `sd_source+0x24`.

The numeric meanings of entry bytes `+0x11/+0x12` are deliberately not overnamed until their enum/semantic owners are separately closed.

## Voice pool and start handoff

The dedicated-server high-level voice pool is exact:

- base `0x00E57100`
- **128 voices**
- **0x180 / 384 bytes per voice**
- total span **0x9600 / 38,400 bytes**

`SD_VoiceAllocate` scans this pool and uses an atomic claim. If it cannot obtain a free voice, it calls `SD_OutputForceWakeup` and retries up to four times.

`SD_OutputForceWakeup` at `0x008BA8B0` is now closed exactly as:

`Sys_SetEvent(0x01087A88)`

This corrects an earlier provisional interpretation of the tiny wakeup wrapper; the exact machine code is a direct event signal, not an indirect backend dispatch.

## Voice parameter publication

Two per-voice parameter tables are distinct:

- `voiceNewParam[]` base `0x00E60900`
- `voiceParam[]` base `0x00E60B00`

`SD_VoiceStart` at `0x008BA620` is exactly **159 bytes**, SHA-256:

`6d65d5ddfe6b86078c815997c5063e14d92c8d2416be002ec434fe0d7f723053`

It derives the voice index from the pool pointer, requires both parameter slots to be empty, then publishes the supplied `sd_voice_param*` into `voiceParam[index]`.

Therefore `SD_VoiceStart` is a parameter/state handoff into the lower sound-driver side. It is not itself the PCM/FLAC decoding routine.

## Exact public voice-state fields

The following accessors are machine-closed:

- `SD_VoiceHasData` -> `voice+0x08 != 0`
- `SD_VoiceDone` -> `voice+0x04 != 0`
- `SD_VoicePosition` -> signed/opaque 64-bit value at `voice+0x10/+0x14`
- `SD_VoiceStarted` -> `voice.state(+0x00) == 2 && voiceParam[voiceIndex] != null`

So the currently closed prefix of `sd_voice` is:

- `+0x00` state
- `+0x04` done
- `+0x08` hasData
- `+0x10` 64-bit position

## Dedicated-server mixer negative control

The complete linker-symbol census is important here. The server includes the high-level sound control path, decoder/source/stream/voice allocators and a limited XAudio2 initialization/shutdown layer. However, the retail-style mixer DSP is not available as an authoritative server target:

- `sd_mix_voice.obj` contributes only retained data/string evidence such as `"blend"`; no public active `SD_MixVoice` implementation is present in this build.
- `sd_mix_master.obj` does not provide a usable retail mixer body for this closure.
- `sd_mixer.obj` retains parameter-pool/control functions (`SD_MixParamAllocate`, `SD_MixParamFree`, `SD_MixSetParam`) rather than a complete retail sample mixer.

Therefore the server remains authoritative for the control/handoff layer above, but it must **not** be used to invent retail resampling, pan-law, bus mixing or DSP behavior.

## Next exact frontier

The next work should proceed on two tracks:

1. close the producer/consumer parameter queue around `SD_UpdateVoice`, `SD_VoiceSetParam`, `SD_MixSetParam` and retained mixer-control state;
2. recover an exact client executable and use that binary for the actual sample mixer/resampler/speaker-output path.

The old direct R2 client paths currently return 404. The next client search should inspect the central directory of the already-used complete public T6 archive rather than assuming the executable is absent.

## Proof boundary

This checkpoint proves the exact SHA-pinned PC dedicated-server control path only. It does **not** establish:

- retail `t6mp.exe` address equivalence;
- retail decoder `Create` function addresses;
- actual retail mixer DSP or resampling algorithm;
- channel/speaker pan law;
- reverb/filter implementation;
- XAudio2 sample submission semantics;
- that normal headless dedicated-server configuration enables audible output.

Do not promote any of those from source filenames, linked libraries, stripped object-module names or adjacency.
