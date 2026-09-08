# T6 audio PC-server decoder / stream runtime v1 — 2026-09-08

## Scope

This checkpoint closes the exact `SndAssetBankEntry -> decoder interface -> stream object` runtime layer for the SHA-pinned **T6 PC dedicated server**. It does not claim retail `t6mp.exe` equivalence and deliberately does not assign codec names to numeric physical formats until their interface initialization is independently closed.

Exact source identities:

- `CoDMPServer_PC.exe` — 13,711,872 bytes — SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
- `CoDMPServer_PC.map` — 9,213,148 bytes — SHA-256 `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`

Reusable fail-closed verifier:

`tools/t6_pc_server_sound_decoder_stream_runtime_proof_v1.py`

Machine record:

`manifests/audio/T6_PC_SERVER_SOUND_DECODER_STREAM_RUNTIME_V1.json`

Green CI:

- run `34250772038`
- artifact `10065900362`
- generated proof SHA-256 `a9fe6073fb4c658cb7e2d0789c15f2f92cf7a24b4b8554efe0cf840043ec3cd7`

## Exact function identities

- `SD_DecoderShutdown` `[0x008B99F0,0x008B9A10)` — 32 bytes — `09e6ad9478f56465517ecbcdfe2e356fb68e85acd67c452ab4844806dc6af779`
- generic `SD_DecoderAllocate` `[0x008B9A10,0x008B9B20)` — 272 bytes — `35ec6c52fb0105ff7f5d3a80e44047a7849b8fc50acab49dd7d7839c1efa6f0c`
- direct `SD_DecoderAllocate` wrapper `[0x008B9B20,0x008B9B70)` — 80 bytes — `73b09271cd3713480eb43d4d3b7af23c95e0171b3ca8962da7513fa70553a4f2`
- `SD_SourceInitStream` `[0x008B9D10,0x008B9DA0)` — 144 bytes — `8a1c3ebfb4d69d2c3b88ed35f7b014bf7e0aa64bef1c2366a7fe1fe6549b2081`
- `SD_StreamShutdown` `[0x008B9DA0,0x008B9DC0)` — 32 bytes — `dd5a9abab4fb383a3f6dbb5e57a71f700bcbf72ba934fbd8e21b1bd28090898d`
- `SD_StreamBufferPreload` `[0x008B9DC0,0x008B9E20)` — 96 bytes — `393f1ede1bef4e54cb3bfe9b5dbde3e65494be996679f36dd421dcb3d676f7ea`
- `SD_StreamAllocate` `[0x008B9E20,0x008BA010)` — 496 bytes — `3732b14d49e8c65495226e32b0d5aa2147a5432bbb6243da1fb840530d1edff0`

## Decoder interface dispatch

The physical `SndAssetBankEntry` byte at exact offset **`+0x13`** is copied into `sd_decoder+0x20` and used directly as the decoder-interface index.

`SD_DecoderShutdown` proves there are exactly **11 interface records** with stride **`0x2C` / 44 bytes**. Its shutdown-function pointer walk starts at `0x00DE2514`, advances by `0x2C`, and ends at `0x00DE26F8`.

The generic allocator indexes a second pointer table at `0x00DE2538` with the same `0x2C` stride. The binary's source assertion names that target exactly:

`g_sd.decoderInterfaces[decoder->format].Create`

The selected `Create` function is invoked with the allocated `sd_decoder*` and the physical `SndAssetBankEntry*`.

The direct two-argument `SD_DecoderAllocate(sd_source*, entry*)` wrapper accepts only numeric physical formats **0** and **8**. Other values print `sound no decoder for asset type %d` and return null.

For format 0 the wrapper selects instance-pool base `0x00DE3054`; for format 8 it selects `0x00DE3E64`. Both pass an exact instance count of **100** into the generic allocator.

This checkpoint intentionally records these as `format0` and `format8`, not guessed codec names.

## Stream source setup

`SD_SourceInitStream` reads physical `entry+0x11` as channel count and asserts that it is exactly **1 or 2**.

It passes the supplied filename and physical entry into exact `SD_StreamAllocate @ 0x008B9E20` and stores the result at `sd_source+0x18`.

On allocation failure:

- `sd_source+0x20 = 1`
- `sd_source+0x28 = 1`
- `sd_source+0x2C = 1`

On success those three fields are cleared. The boolean `entry+0x12 != 0` is stored at exact `sd_source+0x24`.

## Stream pool and integrity gates

`SD_StreamAllocate` scans a fixed pool:

- base `0x07F1A420`
- end exclusive `0x07F1AC90`
- stride `0x6C` / 108 bytes
- exact count **20**

It requires the reusable stream's source-named members to be clear, including:

- `stream->ioBuffer`
- `stream->buffers[0]`
- `stream->buffers[1]`
- `stream->buffersSubmitted[0]`
- `stream->buffersSubmitted[1]`

A crucial physical-file identity check is now exact:

`SND_HashName(filename) == entry->id`

Thus the same physical entry ID already reached from serialized `SndAlias.assetId` is checked again against the supplied runtime sound filename before the stream object is initialized.

The initialized stream records exact state including:

- `stream+0x00 = 1`
- `stream+0x04 = filename`
- `stream+0x64 = entry`
- `stream+0x44 = 0`
- `stream+0x58 = 0`

The separate preload table is `0x140` bytes at `0x07F1B108`, scanned in `0x14`-byte records, giving exactly **16 preload records**.

## Closed chain so far

For this exact server build the sound path is now machine-closed through:

`SndAlias.assetId -> physical SndAssetBankEntry -> entry.format(+0x13) -> g_sd.decoderInterfaces[format].Create -> sd_decoder / sd_source -> fixed stream object + filename hash integrity`

This sits below the already-closed logical voice allocation/limit layer and the `SD_StartAlias` physical-bank lookup layer.

## Remaining proof boundary

Still open and deliberately not inferred:

1. codec names for physical formats 0 and 8;
2. exact `Create` and subsequent decode function targets installed in decoder interface slots 0 and 8;
3. exact encoded-bitstream-to-PCM behavior;
4. retail `t6mp.exe` equivalence.

The next pass is an exact machine-code xref census of `g_sd.decoderInterfaces` and the two format-specific instance pools, followed by fail-closed identification of the installed codec functions.
