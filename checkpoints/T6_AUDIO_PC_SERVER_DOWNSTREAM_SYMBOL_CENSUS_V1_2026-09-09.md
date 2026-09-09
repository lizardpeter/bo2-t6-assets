# T6 audio PC-server downstream symbol census v1 — 2026-09-09

## Scope

This checkpoint is an exact Microsoft MAP inventory of the dedicated-server sound objects that sit below the already-closed alias, physical-bank, codec-identity, decoder-allocation, and stream-allocation layers. It is deliberately a **symbol/address census only**. It does not promote decoded-PCM, refill, mixer, resampler, or XAudio2 submission semantics.

Exact authority:

- `CoDMPServer_PC.exe` — 13,711,872 bytes — SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
- `CoDMPServer_PC.map` — 9,213,148 bytes — SHA-256 `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`
- server-decompile reference commit `ecdd85023274e49675a00458b210c22b4b4849e7`

Machine record:

`manifests/audio/T6_PC_SERVER_SOUND_DOWNSTREAM_SYMBOL_CENSUS_V1.json`

Workflow:

`.github/workflows/t6_audio_downstream_symbol_census_v1.yml`

Green CI:

- source commit `2ba098a028cab0a6e33b03577f812d6d88281c1b`
- run `34362389500`
- job `102502393597`
- artifact `T6_AUDIO_DOWNSTREAM_SYMBOL_CENSUS_V1`
- artifact ID `10108367742`
- artifact ZIP SHA-256 `e6edaf829d3183963ab921580928fa0fe4efeb21c60159a217afc49bf81a89a9`
- generated JSON SHA-256 `36c46f3239eccd7d0df704803111f355bb073eb00fdc20b06595ec5c89e55ea8`

## Fail-closed MAP parser correction

The first census attempt rejected 12 selected MAP rows. The diagnostic rerun showed that all 12 had one exact Microsoft MAP tail form not covered by the initial parser:

`<linear VA> f i <object>`

The parser was changed only to admit the three demonstrated forms:

- `<VA> <object>`
- `<VA> f <object>`
- `<VA> f i <object>`

No arbitrary flag sequence or heuristic line recovery was added.

## Exact census

Across the 11 selected sound-object names, the exact MAP contains:

- **217 rows**
- **65 function-flag rows**
- **12 inline-flag rows**
- **3 duplicate linear VAs**

Per-object counts:

| object | rows | functions | inline |
|---|---:|---:|---:|
| `sd_api.obj` | 95 | 22 | 5 |
| `sd_decode.obj` | 9 | 3 | 0 |
| `sd_mix_master.obj` | 2 | 1 | 1 |
| `sd_mix_radverb.obj` | 0 | 0 | 0 |
| `sd_mix_voice.obj` | 1 | 0 | 0 |
| `sd_mixer.obj` | 8 | 4 | 0 |
| `sd_output_la2.obj` | 0 | 0 | 0 |
| `sd_output_xa2.obj` | 49 | 18 | 6 |
| `sd_source.obj` | 4 | 1 | 0 |
| `sd_stream.obj` | 19 | 4 | 0 |
| `sd_voice.obj` | 30 | 12 | 0 |

## Downstream address inventory

The census gives exact addresses for the next runtime probes:

- `SD_PreUpdate` — `0x008B90E0`
- `SD_UpdateVoice` — `0x008B9860`
- `SD_Sync` — `0x008B98F0`
- `SD_StreamDevhost` — `0x008BA010`
- `SD_VoiceSetParam` — `0x008BA560`
- `SD_VoiceStart` — `0x008BA620`
- `SD_VoiceStarted` — `0x008BA6C0`
- `sd_xa2_callback::OnBufferEnd` — `0x008BA800`
- `SD_OutputShutdown` — `0x008BA820`
- `SD_OutputForceWakeup` — `0x008BA8B0`
- `SD_SwitchDevice` — `0x008BA9C0`
- shared XAudio2 callback address — `0x008BAAB0`
- `SD_OutputInit` — `0x008BAE90`
- `SD_Reset` — `0x008BB100`

The MAP also exposes `XAudio2Create` as an inline function at `0x008BA790`, and several callback names share the same tiny code addresses.

## Important alias/stub boundary

Four public names map to exact address `0x008B3F40`:

- `SD_PauseVoice`
- `SD_PostUpdate`
- `SD_UnpauseVoice`
- `SD_MixShutdown`

Several callbacks similarly share `0x008BAAB0`.

These aliases are preserved exactly. The census does **not** choose one name as the true semantic owner. Machine bytes must establish whether these are common no-op stubs or shared implementations.

## Already-narrowed `SD_VoiceStart` boundary

Independent decompile evidence for exact `SD_VoiceStart @ 0x008BA620` shows that it computes the 0x180-byte voice-pool index, asserts both `voiceNewParam[index]` and `voiceParam[index]` are null, and installs the supplied parameter pointer in `voiceParam[index]`.

Therefore `SD_VoiceStart` itself is not the missing decoder or hardware-start function. `SD_VoiceStarted` is likewise only a state-and-parameter-pointer predicate in the reconstructed server source.

## Remaining proof boundary

Still open and deliberately not inferred:

1. where the worker consumes `voiceParam` / `voiceNewParam` and advances voice state;
2. exact decoder Process/read/refill behavior;
3. decoded sample representation and frame-count contract;
4. exact stream double-buffer lifecycle;
5. mixer/resampler equations and output layout;
6. XAudio2 source-buffer submission and completion semantics;
7. retail `t6mp.exe` decoder/output equivalence.

The immediate next pass is a byte- and call-target probe of `SD_PreUpdate`, `SD_UpdateVoice`, `SD_Sync`, `SD_StreamDevhost`, `SD_VoiceSetParam`, `OnBufferEnd`, `SD_OutputForceWakeup`, `SD_OutputInit`, and `SD_Reset`, while retaining all shared-address aliases rather than resolving them by name.
