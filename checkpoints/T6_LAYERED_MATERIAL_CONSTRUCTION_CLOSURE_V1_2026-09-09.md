# T6 layered Material construction closure v1 — 2026-09-09

## Status

**GREEN.** The exact T6 PC dedicated-server `Material_CreateLayered` construction path is now source-closed at the record-construction layer. This checkpoint supersedes the earlier state in which only final generated texture/constant qsort order was closed.

This does **not** claim retail-client executable equivalence and does **not** reconstruct historical standalone Material XAssets that are absent from a retail FastFile dump.

## Exact authorities

- `CoDMPServer_PC.exe`
  - SHA-256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
- `CoDMPServer_PC.map`
  - SHA-256 `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`
- `Material_CreateLayered`
  - VA `0x00A4DA60`
  - end VA exclusive `0x00A4E100`
  - 1,696 bytes
  - 494 instructions
  - body SHA-256 `505da556ae793f0a27a5e393dff0c9c1ff8f0be4a42c2935c5790c9c29535e42`
- pinned OpenAssetTools `9dca965366541504b71fa8cfb7ac049cb9b717e1`
  - exact `T6_Assets.h` SHA-256 `138ab62db70118e11a33f58fdc6c02ed5bd3beab7f589829053dc1a2976fdff9`
- exact layered-table comparator
  - VA `0x00A4D630`
  - SHA-256 `89c3ef79d0956caceb677fd742d376f28895d8788fd9ad7c1e88a4535d840952`

## Exact construction rules now closed

### Generated Material name

The runtime constructor builds the name exactly as:

`baseName + "(" + sourceMaterialName[0] + ":" + ... + sourceMaterialName[layerCount-1] + ")"`

The literal bytes were independently read from the SHA-pinned executable:

- `0x00B947B4` = `"("`
- `0x00B91FC4` = `":"`
- `0x00B947AC` = `")"`

The function asserts `layerCount < 8`. Layer 0 has no suffix byte. For layer indices 1–7 the suffix byte is exactly ASCII `'0' + layerIndex`.

### Texture rows

Pinned T6 `MaterialTextureDef` is 16 bytes in this constructor and has:

- `nameHash` +0x00
- `nameStart` +0x04
- `nameEnd` +0x05
- sampler state +0x06
- semantic +0x07
- `isMatureContent` +0x08
- image pointer +0x0C

Each source texture record is copied as the complete 16-byte record. For nonzero layers, the constructor overwrites `nameEnd` with the one-byte layer digit and updates the hash exactly as:

`newHash = oldHash * 33 XOR layerDigitByte`

For layer indices 1–7 this is exactly one additional T6 `R_HashString`/djb2-xor character.

The constructor then recomputes `isMatureContent`: semantic 0 or 1 forces false; otherwise it tests an image-owned string pointer observed at image+0x48 for the exact `_mature` substring. The high-level field name of image+0x48 remains deliberately unresolved by this checkpoint.

### Constant rows

Pinned T6 `MaterialConstantDef` is 32 bytes:

- `nameHash` +0x00
- `name[12]` +0x04
- `literal` vec4 +0x10

Each source constant is copied as the complete 32-byte record. For a nonzero layer, the constructor scans the 12-byte name for the first NUL. If there is room, it appends the one-byte layer digit and preserves NUL termination when another byte remains. If the 12-byte name is already full, the visible name bytes are not changed.

The hash is nevertheless updated **unconditionally** for every nonzero layer:

`newHash = oldHash * 33 XOR layerDigitByte`

That distinction is important for exact decoder/exporter implementation: a full 12-byte name may retain its visible bytes while carrying the layer-extended hash.

### `colorTint` completion

The constructor precomputes `R_HashString("colorTint", 0)` and scans every source layer's constants by `nameHash`. If a source layer lacks that hash, the generated Material receives one new `colorTint` constant.

The injected literal is copied from exact global `colorWhite @ 0x00C67D50`. The pinned executable bytes are:

`0000803f0000803f0000803f0000803f`

which is exactly vec4 `[1.0, 1.0, 1.0, 1.0]`.

For a nonzero layer, the injected row then receives the same bounded visible-name suffix and unconditional incremental hash update as copied constants.

Therefore generated constant count is exactly:

`sum(source.constantCount) + one for each source layer whose source constant table lacks colorTint by nameHash`

### Finalization

The constructor proves its produced row counts before sorting, then performs the already-closed qsorts:

- textures: `Material+0x54`, table `+0x60`, 16-byte records
- constants: `Material+0x55`, table `+0x64`, 32-byte records
- both compare the unsigned uint32 `nameHash` at record +0

## CI proof

Workflow: `.github/workflows/t6_layered_material_construction_closure_v1.yml`

- workflow run `34425678722`
- job `102710283434`
- head commit `b98de4d07a962bb647726496b376095a3f181bd3`
- artifact `T6_PC_SERVER_LAYERED_MATERIAL_CONSTRUCTION_V1`
- artifact ID `10132545775`
- artifact ZIP SHA-256 `010e85f2fc3fb0e612fc161fdd6f7d0d04d2686215d1598e369eacc3659f35c2`
- result JSON SHA-256 `49984bb0dd4989d3a95c8f70f881d1dcd17613d2d4ab6d36188de18e46edba34`

Durable machine manifest:

`manifests/materials/T6_PC_SERVER_LAYERED_MATERIAL_CONSTRUCTION_V1.json`

## Remaining boundary

The next proof is retail reconciliation, not more server inference: replay these exact construction rules over all known component Materials in the exact Nuketown retail FastFile dump and require the 120 generated Material constant tables to match. For the seven standalone-missing component identities, only generated-runtime residual contributions may be recovered. A generated white `colorTint` row cannot by itself distinguish a source-authored identical white `colorTint` from runtime default injection, so historical standalone provenance must remain open where the source XAsset is absent.
