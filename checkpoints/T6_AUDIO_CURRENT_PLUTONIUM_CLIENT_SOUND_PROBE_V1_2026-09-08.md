# T6 current-Plutonium client sound probe v1 — 2026-09-08

## Status

A real current Plutonium T6 multiplayer client is now independently identified and retained as a **separate authority class**. It is useful for client-side sound reverse engineering, but it is not the historical pinned retail executable and is not being promoted as retail-equivalent.

## Current client identity

From the live Plutonium production manifest, revision **5346** contains exactly one `games/t6mp.exe`:

- bytes: **13,263,640**
- SHA-1: `f101e28c3a18ce1ffe37a40d23cd04f7f57925d3`
- SHA-256: `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`
- PE32 image base: `0x00400000`

Historical pinned retail reference remains:

- bytes: **12,850,328**
- SHA-256: `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`

The current client fails both exact retail size and exact retail SHA gates.

## Server-body comparison

The probe compared the complete exact machine-code ranges of five already-closed dedicated-server control functions against the current client. Exact byte-for-byte match counts were zero for all five:

- `SD_PreUpdate`: 0
- `SD_UpdateVoice`: 0
- `SD_MixSetParam`: 0
- `SD_VoiceSetParam`: 0
- `SD_VoiceStart`: 0

Therefore no server VA or whole-function byte body is being transferred into the current client by assumption.

The client still retains useful sound-side evidence, including current sound dvars and XAudio2 RTTI strings such as `.?AVSD_XAudio2Callbacks@@`, `.?AUIXAudio2VoiceCallback@@`, and `.?AUIXAudio2EngineCallback@@`.

## Durable evidence

- workflow: `.github/workflows/t6_current_plutonium_client_sound_probe_v1.yml`
- source commit: `ad1a2ad858fe48f857adc8287a43962a1c405fa8`
- green run: `34260299481`
- job: `102176283640`
- artifact: `T6_CURRENT_PLUTONIUM_CLIENT_SOUND_PROBE_V1`
- artifact ID: `10069585805`
- artifact ZIP SHA-256: `4fd72821457fa44018db606cd77367ccb5109dec290b39839a463129778b6617`
- result JSON SHA-256: `7015cd64b5a284cb00cef453214b34e48abe889bbbafeddf882d5eba247019a7`
- compact manifest: `manifests/audio/T6_CURRENT_PLUTONIUM_CLIENT_SOUND_PROBE_V1.json`

## Next exact frontier

Use **relocation-aware masked machine-code homology** rather than exact whole-body equality. Only address/displacement bytes demonstrated to be relocation-sensitive may be wildcarded; opcode/register/control structure must remain exact, and any promoted match must be unique. This can recover current-client homolog addresses without asserting retail equivalence.

## Proof boundary

This checkpoint establishes the exact identity of the current Plutonium client and a negative exact-body comparison only. It does **not** prove historical retail identity, retail address equivalence, or that any structurally similar current-client function has identical retail behavior.
