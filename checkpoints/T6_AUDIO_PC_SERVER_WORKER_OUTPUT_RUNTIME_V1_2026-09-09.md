# T6 audio PC-server worker/output runtime v1 — 2026-09-09

## Scope

This checkpoint advances the dedicated-server audio proof from decoder/stream allocation into the API handoff and XAudio/output synchronization layer. It also records an exact operand census over the `g_sd` decoder-interface region.

It does **not** claim that the dedicated server is retail-equivalent for decoding, mixing, resampling, or XAudio2 submission. Those remain open until separately closed.

Exact authority:

- `CoDMPServer_PC.exe` — 13,711,872 bytes — SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
- `CoDMPServer_PC.map` — 9,213,148 bytes — SHA-256 `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`
- server-decompile reference commit `ecdd85023274e49675a00458b210c22b4b4849e7`

Machine record:

`manifests/audio/T6_PC_SERVER_SOUND_WORKER_OUTPUT_RUNTIME_V1.json`

## Evidence artifacts

### Worker/output machine-code probe

- workflow `.github/workflows/t6_audio_worker_output_probe_v1.yml`
- source commit `afcae9a02059ee815f45942330039b351ec0db05`
- run `34362855678`
- job `102503988526`
- artifact ID `10108562967`
- ZIP SHA-256 `dcb7c476a6919b77cb7f9c8f378f38d862efa3049766c7b5a9ff6608d05e074a`
- generated JSON SHA-256 `6e1b6109bb4ad92a2dc29d5ebfe12f596f1b0a30ed7a3daeff0ef09174148fd5`

### Global xref probe

- workflow `.github/workflows/t6_audio_worker_global_xref_probe_v1.yml`
- source commit `1f33d1e05fc1c8f6bcaa732583a950b690f61c9d`
- run `34363145360`
- job `102504990578`
- artifact ID `10108684709`
- ZIP SHA-256 `a6936614f24027ebbeb62cf3df80fb84dfac4916e748e4c18f4cf3375d9adff1`
- generated JSON SHA-256 `1afc9ff797006530a435964fcecc91e7edf4fd1743c33736bd6bbc71dccff048`

### Decoder-interface indirect census

- workflow `.github/workflows/t6_audio_interface_indirect_census_v1.yml`
- source commit `884c9ef76f3015f575ad24091a013c65bea94008`
- run `34363665010`
- job `102506769899`
- artifact ID `10108898252`
- ZIP SHA-256 `8aa516cda0cc8eb69f6bc293d6df717b573c1f54699308bd4626f3a7c0e05f43`
- generated JSON SHA-256 `0df1ae61a95575764e803e0ec13af816cfcf19464932524a4e337311bc37fca0`

## Exact API-side handoff semantics

`SD_VoiceStart @ 0x008BA620` is not a decoder or hardware-start routine. It installs the voice parameter pointer after checking the relevant active/new slots.

`SD_VoiceStarted @ 0x008BA6C0` is a state-and-parameter-pointer predicate.

`SD_PreUpdate @ 0x008B90E0` is the main API-side handoff visible in this slice. It starts a voice only after `SD_VoiceHasData`, and it reports decoder/output telemetry.

`SD_UpdateVoice @ 0x008B9860` reads the current voice position, records that position at the higher-level voice, and passes a replacement parameter through `SD_VoiceSetParam`. It does not perform decoder processing.

`SD_VoiceSetParam @ 0x008BA560` is an atomic parameter-pointer handoff.

## Exact output synchronization semantics

`sd_xa2_callback::OnBufferEnd @ 0x008BA800`:

1. atomically decrements the global flying-buffer counter at `0x01087A8C`;
2. signals `bufferReadyEvent @ 0x01087A88`.

`SD_OutputForceWakeup @ 0x008BA8B0` signals the same event.

`SD_OutputInit @ 0x008BAE90` initializes the output/XAudio side, initializes the buffer-ready event, zeroes the flying-buffer counter, and zeroes `g_sd.syncCounter @ 0x00DE250C`.

The shared callback address `0x008BAAB0` is retained as an exact shared tiny stub rather than assigning one preferred callback name to it.

## Exact telemetry xref boundary

The decoder timing globals are directly read by `SD_PreUpdate`:

- `0x00E4A898` — `SD decoder wait usec`
- `0x00E4A89C` — `SD decoder process usec`

The exact `.text` absolute-operand census found no direct absolute writer to either address. That is a negative statement only about direct absolute operands in this exact dedicated-server `.text`; it does not prove the counters cannot be reached through a derived pointer or that equivalent retail code is absent.

The stream telemetry globals are similarly read directly by `SD_StreamDevhost`, but their mutation sites are not promoted from this evidence.

## Exact decoder-interface operand census

The complete raw dword-address census over `[0x00DE2500,0x00DE2700)` admitted only values that were exact immediate or memory-displacement operands in decoded instructions.

Results:

- 10 raw candidate byte hits
- 9 admitted exact operand references
- 1 rejected raw false-positive

The only decoder-interface function-pointer fields reached by exact direct operands are:

- `0x00DE2514` — Shutdown field base, iterated by `SD_DecoderShutdown`
- `0x00DE2538` — Create field base, indexed and indirect-called by lower `SD_DecoderAllocate`

No other direct immediate/memory-displacement reference into the decoder-interface range exists in the exact server `.text` census.

This is important, but it is **not** sufficient to claim that decoder processing cannot occur. A processing function could still be reached through a callback/interface pointer copied into a decoder object, or through a computed/base-relative access that does not encode a decoder-table address directly.

## Exact source-assertion breadcrumbs

The MAP carries compiler assertion strings exposing these exact source expressions:

### `sd_stream`

- `stream->buffersSubmitted[1] == 0`
- `stream->buffersSubmitted[0] == 0`
- `stream->buffers[1] == 0`
- `stream->buffers[0] == 0`
- `stream->ioBuffer == 0`

### `sd_voice`

- `voice->decoder->framesDecoded`
- `voice->decoder->lastBuffer`
- `voice->decoder->eos`
- `voice->source.stream == 0`

These are source-level member-name evidence only. Exact member offsets and state transitions still require machine-code closure.

## Remaining boundary

Still open:

1. the exact code that advances `framesDecoded`, `lastBuffer`, and `eos`;
2. decoder Process/read callback identity and ABI, if retained in this dedicated-server build;
3. decoded sample layout and frame-count contract;
4. stream refill/double-buffer ownership transitions;
5. source-buffer submission and the flying-buffer increment path;
6. mixer/resampler equations;
7. retail `t6mp.exe` equivalence and retail decoder callback targets.

The next probe uses xrefs to the exact `sd_voice` and `sd_stream` assertion strings plus an operand census around the anonymous XAudio/output globals near `0x01087A88` to locate those transitions without broadening the proof boundary.
