# T6 audio parameter-queue runtime closure v1 — 2026-09-08

The dedicated-server producer/control side of the T6 audio voice parameter pipeline is now fail-closed and durable.

## Authority

- `CoDMPServer_PC.exe`: 13,711,872 bytes
- EXE SHA-256: `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
- linker MAP: 9,213,148 bytes
- MAP SHA-256: `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`

## Green proof

- workflow run: `34259607393`
- source commit: `d4cf325cb3df6419212780ca2f3ae07267e8fcf1`
- artifact: `10069311476` / `T6_AUDIO_PC_SERVER_PARAM_QUEUE_RUNTIME_V1`
- artifact ZIP SHA-256: `bece757f0e455e8a8654389fd3baa318095264a8231bb0918d7431479c5e7bfc`
- proof JSON SHA-256: `38fff31e6596c79d8b6b45843b8d1997a571467f292882084589d17a9fd6de2e`
- retained manifest: `manifests/audio/T6_AUDIO_PC_SERVER_PARAM_QUEUE_RUNTIME_V1.json`

## Closed structure

The high-level `SND` population and the lower sound-driver population are separate:

- high-level slots: exactly **68**
- high-level slot stride: **0x1C0 / 448 bytes**
- high-level loop span: **0x7700 / 30,464 bytes**
- lower `sd_voice` pool: exactly **128** voices
- lower `sd_voice` size: **0x180 / 384 bytes**

`SD_PreUpdate` walks the 68 high-level slots, resolves the driver voice, handles done/not-started/has-data state, obtains an initial `sd_voice_param` through `SD_GetVoiceParam`, and calls `SD_VoiceStart` only after the remaining readiness gates pass.

For an already started driver voice, `SD_UpdateVoice` reads the lower driver's 64-bit playback position and writes it into the corresponding high-level slot at offsets `0x1A8`/`0x1AC`. It then obtains a replacement parameter block through `SD_GetVoiceParam` and hands it to `SD_VoiceSetParam`.

`SD_VoiceSetParam` requires incoming parameter state `1`. The active and pending tables are distinct:

- active `voiceParam[]`: `0x00E60B00`
- pending `voiceNewParam[]`: `0x00E60900`

The pending pointer is atomically replaced. If an older non-null pending pointer is displaced, it is immediately returned through `SD_VoiceParamFree`.

The global mix-master parameter path is separate from the per-voice queue. `SD_MixSetParam` requires incoming state `1`, atomically replaces the global pending pointer at `0x01078000`, and frees any superseded global mix parameter through `SD_MixParamFree`.

## Exact function-range hashes

- `SD_PreUpdate` `0x008B90E0..0x008B94C0`: 992 bytes, SHA-256 `492e581a4db0b4c346b86b5455808b29789299450f7ea42e415e06630a747db5`
- `SD_UpdateVoice` `0x008B9860..0x008B98F0`: 144 bytes, SHA-256 `3809e0e45094a27dd616469ce5f50a1a5823807ab1bb8b9ca99d96328c33d1dd`
- `SD_MixSetParam` `0x008B9C80..0x008B9D10`: 144 bytes, SHA-256 `43b9ac292aaedd16e1adf3f5f4f05df82dd137a0d339203f5de3203a71a7f58d`
- `SD_VoiceSetParam` `0x008BA560..0x008BA610`: 176 bytes, SHA-256 `f741d01f4881b626f5aa14800ac7487edd8f5c0a17810690035fc4ece72b3e3a`

## Proof boundary

This closes only the producer/control side that survives in the dedicated server. It does **not** promote the dead-stripped retail per-voice consumer/mixer DSP, sample-rate conversion, pan law, bus/master summing, speaker/channel matrix, XAudio2 submission semantics, or retail `t6mp.exe` address equivalence.

The next authoritative target is therefore a real client binary/source universe rather than further inference from the stripped dedicated server.
