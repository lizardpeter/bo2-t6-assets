# T6 audio physical format / codec closure v1 — 2026-09-08

## Status

The codec identity of every physical sound payload in the retained **116-bank T6 PC corpus is now closed** without relying on guessed decoder names from the dedicated-server binary.

The closure combines three independent layers:

1. the exact pinned T6 source enum and dumper behavior;
2. the already-closed runtime fact that `SndAssetBankEntry+0x13` is the decoder-format index;
3. direct byte validation of every one of the **25,446 physical bank entries**.

Durable machine record:

`manifests/audio/T6_AUDIO_PHYSICAL_FORMAT_CODEC_CLOSURE_V1.json`

## Exact source authority

Pinned source:

`Laupetin/OpenAssetTools@9dca965366541504b71fa8cfb7ac049cb9b717e1`

`src/Common/Game/T6/T6_Assets.h` defines the exact T6 `snd_asset_format` values, including:

- `0x0 = SND_ASSET_FORMAT_PCMS16`
- `0x1 = SND_ASSET_FORMAT_PCMS24`
- `0x2 = SND_ASSET_FORMAT_PCMS32`
- `0x3 = SND_ASSET_FORMAT_IEEE`
- `0x4 = SND_ASSET_FORMAT_XMA4`
- `0x5 = SND_ASSET_FORMAT_MP3`
- `0x6 = SND_ASSET_FORMAT_MSADPCM`
- `0x7 = SND_ASSET_FORMAT_WMA`
- `0x8 = SND_ASSET_FORMAT_FLAC`
- `0x9 = SND_ASSET_FORMAT_WIIUADPCM`
- `0xA = SND_ASSET_FORMAT_MPC`

The same pinned source's T6 sound-bank dumper maps the relevant formats as:

- `SND_ASSET_FORMAT_PCMS16` -> `.wav` / PCM-writing path
- `SND_ASSET_FORMAT_FLAC` -> `.flac` passthrough path

Therefore the numeric 0/8 values seen by the runtime have exact source names rather than inferred codec labels.

## Runtime cross-check

The previous exact PC dedicated-server machine proof already established that physical:

`SndAssetBankEntry+0x13`

is copied directly into `sd_decoder.format` and indexes:

`g_sd.decoderInterfaces[decoder->format].Create`

The direct server `SD_DecoderAllocate` wrapper admits only values **0** and **8**.

That machine result now agrees exactly with the source enum and the actual PC physical-bank population.

The server itself remains only runtime-structure authority. Codec names are not being back-filled from an assumed server `Create` target.

## All-bank physical validation

A new eight-shard fail-closed validation ran over the exact current public archive:

- workflow commit `74cc4ac7e9c7b3c73103760a033d55e3e5826adf`
- run `34252631847`
- aggregate artifact `10066678977`
- artifact digest `sha256:c59966c51f573b6efac5d34b5ad20fa04b2993722f1ad3c3b2739cb2217eec62`
- result JSON SHA-256 `c9653abaffaa162d957fed7eb9f95ef876ba7b53cd7a68e904c7775fe71bc697`

Archive identity recorded by the range reader:

- URL `https://cdn.jordanlindsay.com.au/pluto_t6_full_game.zip`
- bytes `13,675,690,564`
- ZIP64
- 534 archive entries
- 116 SABS/SABL files

All 116 physical bank files were extracted with ZIP CRC validation and independently SHA-256 hashed.

Exact aggregate population:

- **116 banks**
- **25,446 physical entries**
- **4,746 format-0 entries**
- **20,700 format-8 entries**
- **0 other format codes**
- **0 validation failures**

### Format 0 / PCMS16

For every one of the **4,746** format-0 entries, the exact table-declared payload size satisfies:

`dataBytes == sampleCount * channels * 2`

This is the exact byte relation for interleaved signed 16-bit PCM.

Result:

**4,746 / 4,746 pass; 0 fail.**

Concrete retained example:

- bank `cmn_root.all.sabl`
- identifier `9A494501`
- channels `1`
- sample count `88,431`
- data bytes `176,862`
- `88,431 * 1 * 2 = 176,862`

### Format 8 / FLAC

For every one of the **20,700** format-8 entries, the exact payload span begins with:

`66 4C 61 43`

which is native FLAC stream marker:

`fLaC`

Result:

**20,700 / 20,700 pass; 0 fail.**

Concrete retained example:

- bank `mpl_castaway.all.sabs`
- identifier `0899831B`
- first 16 payload bytes `664c6143000000220400040000000000`

There is therefore no hidden T6 container or proprietary pre-decompression layer between the physical format-8 payload and a standard FLAC decoder in the observed PC bank corpus.

## Reference exporter

The closed behavior is now implemented in:

`tools/t6_audio_payload_export_v1.py`

Creation commit:

`ba42a62142396b3209350bec10621810de5ac5f8`

Tests:

`tools/test_t6_audio_payload_export_v1.py`

Test commit:

`6ab5dfcc283b6c53f4a10d8d2691fc838b27acdb`

CI workflow commit:

`518505c06b501f93d06aee8416e6b765f19a7adc`

Green run:

`34252849277`

The exporter is intentionally narrow and lossless:

### code 0

- requires source-closed `PCMS16`;
- requires exact `sampleCount * channels * 2` payload size;
- writes a standard PCM16 RIFF/WAVE header;
- copies the original PCM sample bytes unchanged;
- performs no resampling, remixing, gain change, normalization, or endian conversion.

### code 8

- requires the exact native `fLaC` marker;
- writes the physical payload byte-for-byte as `.flac`;
- performs no custom transform.

### anything else

Fails closed.

The test suite proves both positive paths and rejects malformed FLAC, wrong PCM byte counts, missing IDs, and unknown/unclosed formats.

## Implementation consequence for Blender and Rust

The PC audio decoder contract is now simple and exact for the observed retail bank universe:

```text
SndAlias.assetId
    -> exact physical SndAssetBankEntry
    -> format = entry+0x13
       |
       +-- 0 / PCMS16 -> signed 16-bit interleaved PCM
       |                use table sample rate + channel count
       |
       +-- 8 / FLAC   -> native FLAC stream
                         feed directly to a standard FLAC decoder
```

A Blender importer does not need a T6-specific compressed-audio decoder for format 8. It needs the exact bank/entry resolver plus ordinary FLAC support. For format 0 it only needs to expose the exact PCM16 bytes with their T6 sample-rate/channel metadata.

A Rust runtime should likewise keep T6 parsing separate from codec decoding: the T6 layer resolves and validates the bank entry; the audio layer receives either exact PCM16 or an intact FLAC stream.

## Remaining boundary

Still intentionally open:

1. the exact `Create` function addresses installed in retail `t6mp.exe` decoder-interface slots 0 and 8;
2. deeper retail FLAC decoder implementation details, which are not required to decode the physical payload because it is standard FLAC;
3. mixer/resampler/output-device behavior below decoded PCM;
4. exact retail-client equivalence for server-only `sd_voice` implementation details not independently closed on `t6mp.exe`.

The exact historical retail executable remains SHA-pinned at 12,850,328 bytes / `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`, but its raw bytes are not currently available through the checked Drive or historical public R2 paths. That absence does not weaken the codec closure above because codec identity is now independently source-closed and exhaustively physical-payload validated.
