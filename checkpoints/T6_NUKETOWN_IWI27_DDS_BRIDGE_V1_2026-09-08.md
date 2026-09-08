# T6 Nuketown IWI27 -> DDS closure v1 — 2026-09-08

Status: **GREEN for the exact 81 pointer-proven packed GfxImage payloads.** This is not a claim that 81 images are the complete Nuketown world texture population.

## Exact source

- `mp_nuketown_2020.ff`
  - SHA-256 `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- exact expanded stream
  - 154,653,476 bytes
  - SHA-256 `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`
- exact packed-image alias authority
  - `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_DLC0_IPAK_PACKED_IMAGE_ALIAS_CLOSURE_V3.json.zlib.b64`
  - 81 aliases / 81 resolved / 81 byte-distinct payloads / 0 unresolved

## IWI27 mip layout closure

The original exploratory model treated the eight size words as ordinary adjacent mip boundaries. That model fit 75/81 files and was **not promoted**.

The six failures were all small 2D block-compressed images whose last size-table words repeat after the final addressable mip boundary. Their exact bytes establish the clamped table rule rather than a malformed-file exception.

The fail-closed v2 proof requires the complete equation:

```text
physical IWI payload after the 64-byte header:
    smallest mip -> ... -> largest mip

mips = exact BC byte counts ordered largest -> smallest
size[i] = 64 + sum(mips[min(i,lastMip):])   for i = 0..7
```

Hosted proof:

- tool: `tools/t6_iwi27_mip_layout_proof_v2.py`
- tool commit: `36a6e95d52270af8be9308211cbffff65f4b5908`
- run: `34280371596`
- artifact: `10077366885`
- artifact ZIP SHA-256: `603f14c547d619d9c77639444ee01fbd359b7b5d05ea1fee8837778c1cb8afa6`
- proof JSON: 92,738 bytes
- proof JSON SHA-256: `b71a1f1544c4ba8cc0f9204869e37e08281dc3f31339a66540261576302efdda`

Exact census:

- 81/81 complete eight-word fits
- 81/81 complete mip-payload byte-sum fits
- 0 failures
- 81/81 depth = 1
- 81/81 flags = 16
- formats: 22 DXT1, 39 DXT5, 20 DXN
- mip counts: 2 images with 6, 4 with 7, 8 with 8, 24 with 9, 43 with 10

## Lossless DDS bridge

`tools/t6_iwi27_dds_bridge_v1.py` consumes only a green v2 layout proof plus the exact 81-payload staging manifest. It does not decode or recompress any BC block.

The operation is:

1. verify the complete eight-word IWI layout again;
2. split the exact source payload into source-proven compressed mip slices;
3. reverse whole mip slices from IWI smallest->largest into DDS largest->smallest order;
4. synthesize only the standard 128-byte legacy DDS container header;
5. require every source compressed mip SHA-256 to equal the corresponding DDS compressed mip SHA-256.

Observed/promoted mappings:

- IWI `0x0B` DXT1 -> DDS `DXT1` / BC1
- IWI `0x0D` DXT5 -> DDS `DXT5` / BC3
- IWI `0x0E` DXN -> DDS `ATI2` / BC5_UNORM

DXT3 is intentionally not promoted: it is absent from this exact corpus and the current production DDS preview decoder does not accept it.

Hosted closure:

- bridge tool commit: `7427cbb7afdb709b69379be23cd209f5bd02db93`
- final validation workflow commit: `ff0a6cc13dcef3778e0476f1c006e788d70e72d3`
- run: `34280860385`
- artifact: `10077571150`
- artifact ZIP SHA-256: `267aa6f9e974bf3a37fe6d2f4c4be328782f8e010e6aa2836a88df5d62d8a0ac`
- bridge manifest: 316,482 bytes
- bridge manifest SHA-256: `693a23ccbf5e13d079ecb408393bf151c2c87bbf8f485a26e0d78bf820d8701e`

Final bridge result:

- 81 source aliases
- 81 source payloads
- 81 DDS image outputs
- 22 DXT1/BC1
- 39 DXT5/BC3
- 20 ATI2/BC5_UNORM
- every compressed mip byte preserved
- 81/81 independent full-mip-chain checks
- 81/81 independent top-mip decode checks
- 0 unresolved
- 0 conflicts

## Cross-decoder correction

The first independent pixel validator required exact RGBA equality between two already-existing software BC decoders and rejected a DXT1 case even though all compressed-byte checks had passed.

That failure was a validator-policy mismatch, not source-data loss:

- the direct IWI decoder expands RGB565 endpoints using floor division;
- the production DDS decoder expands RGB565 endpoints using nearest rounding.

The final validation therefore keeps **all compressed-data checks exact**, requires alpha exact, and permits only the mathematically bounded RGB565 decoder-policy difference of at most one code value for BC1/BC3. The observed maximum was exactly 1. BC5 normal decoding remained exact.

## Proof boundary

This checkpoint proves the exact lossless IWI27->DDS bridge for the 81 pointer-proven packed GfxImage payloads only.

It does **not** prove that those 81 images are every texture required by the full world exporter. Inline/non-packed images, generated-material dependencies, lightmaps, reflection probes, runtime renderer images, built-in identities, and any other image class remain separate dependency-closure questions.

The next gate is therefore an exact native-OAT/world dependency census against this DDS root. Missing dependencies must be enumerated from source; they must not be filled by filename similarity, placeholders, nearest hashes, or appearance.
