# T6 shadowoverlay shader semantics + executable boundary v1

Date: 2026-09-07

## Status

The native serialized `shadowoverlay` family is already byte-identical across SP / MP / Zombies:

`shadowoverlay -> trivial_shadowoverlay_14e2e827 -> unlit -> pimp_technique_trivial_7bf1260`

with:

`colorMapSampler = sampler.feedbackSampler`

This checkpoint closes the exact arithmetic of the family's native pixel shader and separately closes the executable-source boundary of the public full-game ZIP64 archive.

## Exact native pixel shader

Shader:

- name: `pimp_shader_trivial_3981dec1.hlsl`
- bytes: `5600`
- SHA-256: `2ef171c239a7c98542a961252362761828747bd288ee21e3fde542d48aa5de0e`

Source native dependency artifact:

- run `34167293973`
- artifact `10034715117`
- `T6_SHADOWOVERLAY_ZM_STARTUP_MATERIAL_V1`
- digest `sha256:3746d02226be11978f2e4c915541bf1cbc73f4476cf102f2284a502fe5b9412f`

## Exact disassembly gate

Pinned disassembly workflow commit:

`41e7fe5f5d1c01fb04c5dbd65b35f96f6c2ebb94`

Run:

- `34168269517`
- fully green
- artifact `10034875651`
- `T6_SHADOWOVERLAY_SHADER_DISASSEMBLY_V3`
- digest `sha256:61d1c1ba250539594ecdd35e9b5c8597e8c607cb54616403c997661dc8e539c7`

The disassembler is source-pinned to:

- repository `doitsujin/dxbc-spirv`
- commit `dcd27e1dfdb579e978fda948be5ff67be7b7c8b7`
- exact submodule revisions are initialized and recorded by the workflow

## Fail-closed shader semantic adapter

Tool:

`tools/t6_shadowoverlay_shader_semantics_v1.py`

Tool introduction commit:

`257538a93f249e0ad7e1fc4fe2ea4f02dcf7a0e2`

Integrated workflow commit:

`0ab4942ef38e2252ca1b5e03f49361b5fcb60b6a`

Validation run:

- `34168452899`
- fully green
- artifact `10034936590`
- `T6_SHADOWOVERLAY_SHADER_SEMANTICS_V1`
- digest `sha256:29bfbaa3b7f73e4129984f1657a036421e6e654f29bce1d9d8dcdc34e03b904e`

The adapter refuses authority unless all of the following match:

1. exact 5600-byte shader identity and SHA-256;
2. DXBC container validity;
3. Shader Model 4.0 pixel-program identity;
4. exact RDEF resource table;
5. `PerSceneConsts` at `b0`;
6. `filterTap` beginning at byte offset `1648` = `cb0[103]`, 128 bytes / 8 float4s;
7. `colorMapSampler` as the sole texture/sampler pair at `t0 / s0`;
8. the complete expected executable instruction sequence.

## Exact reflected resources

The retail shader's RDEF contains exactly:

- `colorMapSampler` — sampler `s0`
- `colorMapSampler` — float `Texture2D t0`
- `PerSceneConsts` — constant buffer `b0`

`filterTap`:

- variable index `70`
- start byte `1648`
- size `128`
- first float4 register `103`
- float4 count `8`

Pinned T6 OpenAssetTools independently identifies `CONST_SRC_CODE_FILTER_TAP_0` with accessor `filterTap`, array count 8, and `RARELY` update frequency.

## Exact pixel arithmetic

Let:

- `s = texture2D(t0, uv).r`
- `f = cb0[103] = filterTap[0]`

The exact instruction sequence establishes:

```text
d = f.w + s * (f.z - f.w)
u = (s * f.z) / d
v = saturate(u * f.x + f.y)

RGB = (s == 1.0) ? (0.0, 0.0, 0.5) : (v, v, v)
A   = 1.0
```

The sampled channel is red/x. There is exactly one texture sample instruction.

This arithmetic is authoritative for the exact SHA-pinned retail shader.

## Historical Treyarch lineage: branch-selection only

Recovered T5 renderer source performs a shadow-map debug overlay with the same structural ingredients:

- `shadowOverlayMaterial`
- feedback code-image sampler
- shadow-map image
- `CONST_SRC_CODE_FILTER_TAP_0`
- scale/bias based on near/far overlay depth bounds

This is useful search guidance only. It is not promoted as T6 runtime behavior.

## Public full-game executable inventory

Workflow:

`.github/workflows/t6_public_game_executable_inventory_v1.yml`

Commit:

`b9ad14b1e8dba2df948add0e4212e26a60f6c6a1`

Run:

- `34168547408`
- fully green
- artifact `10034950258`
- `T6_PUBLIC_GAME_EXECUTABLE_INVENTORY_V1`
- digest `sha256:3bb572b7ef23b1b79fb61a4f37c7c1c21bb54dc3ce319577fab70ee7f2a62f5e`

Archive:

- URL: `https://cdn.jordanlindsay.com.au/pluto_t6_full_game.zip`
- ZIP64 bytes: `13,675,690,564`
- entries: `534`

Central-directory executable/library census:

- EXE entries: `4`
- DLL entries: `3`
- T6-name candidates: `0`

The only `.exe` files are redistributable/setup installers:

- `redist/.NETFramework.exe`
- `redist/DirectX/DXSETUP.exe`
- `redist/VC_redist.x86.exe`
- `redist/vcredist_x86.exe`

The only DLLs are:

- `binkw32.dll`
- DirectX setup DLLs

Therefore this exact public game ZIP contains no T6 game executable that can be used for runtime consumer closure.

## Exact retail MP executable provenance still known

Earlier retained user-file analysis establishes the required MP binary identity:

- file `t6mp(1)(1).exe`
- bytes `12,850,328`
- SHA-256 `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`
- PE32 / Intel i386
- PE build timestamp `2013-05-24 19:30:57`
- image base used by existing static proof infrastructure: `0x00400000`

The current File Library retains multiple exact analysis products and hash manifests for this executable, but not a directly retrievable copy of the executable bytes. Google Drive search likewise does not currently expose a `t6mp` file.

A historical workbook also references a prior `t6mp.rar`, but the archive itself is not currently indexed/retrievable from File Library.

## Remaining T6-native shadowoverlay runtime closure

Only the runtime producer/consumer layer remains open for this family:

1. identify the T6 renderer-global or equivalent Material slot receiving `shadowoverlay`;
2. prove the T6 draw/consumer function using it;
3. prove which runtime image is assigned to `sampler.feedbackSampler` for that draw;
4. prove the T6 producer of `filterTap[0]` and its exact values;
5. close any shadow-map/render-target identity and scheduling relationship from T6 itself.

Until exact executable bytes or an independently equivalent T6-native runtime artifact are available, historical T5/IW lineage is not promoted across this boundary.

## Current shadowoverlay completion assessment

For the declared `shadowoverlay` asset/Technique/shader path, the remaining unknown is narrow and runtime-only. Serialized ownership, cross-mode identity, exact Technique binding, shader resource reflection, and exact pixel arithmetic are closed.

A reasonable engineering estimate is approximately **90-95% closed for this specific path**, with the final 5-10% concentrated in executable/runtime producer-consumer proof rather than serialized asset decoding.
