# T6 shadowoverlay runtime targets v1

Date: 2026-09-07

## Purpose

This checkpoint narrows the remaining runtime proof for the already source-closed native `shadowoverlay` Material family. It deliberately separates exact T6 source identities from renderer-lineage search anchors.

## Exact T6 source-closed identities

Pinned OpenAssetTools T6 source at commit `9dca965366541504b71fa8cfb7ac049cb9b717e1` defines:

- `TEXTURE_SRC_CODE_FEEDBACK = 0x8`
- accessor `feedbackSampler`
- update frequency `PER_OBJECT`
- `CONST_SRC_CODE_FILTER_TAP_0 = 0x1A`
- accessor family `filterTap`

The exact native Technique is already closed as:

`shadowoverlay -> trivial_shadowoverlay_14e2e827 -> unlit -> pimp_technique_trivial_7bf1260`

with pixel argument:

`colorMapSampler = sampler.feedbackSampler`

The exact SHA-pinned pixel shader independently proves:

- `colorMapSampler` is the sole `Texture2D t0` / sampler `s0` pair;
- `filterTap` begins at `cb0[103]`;
- only sampled red is used by the shadowoverlay equation;
- output alpha is exactly 1.

Therefore the unresolved runtime producer problem has two exact code-source identities:

1. code image source `0x8` / `feedbackSampler`;
2. code constant source `0x1A` / `filterTap[0]`.

## T6 renderer lineage anchors — not retail authority

OpenBO2 commit `a64812d21946baf710cec7fa26b98ad0d193903b` preserves T6 renderer symbols:

- `RB_GetShadowOverlayDepthBounds`
- `RB_SetSunShadowOverlayScaleAndBias`
- `RB_DrawSunShadowOverlay`
- dvars `sm_showOverlay` and `sm_showOverlayDepthBounds`

The three shadow-overlay routines themselves are `UNIMPLEMENTED` in that source and therefore establish names/search targets only.

The same reconstructed T6 renderer contains concrete writes to:

`gfxCmdBufSourceState.input.codeImages[8]`

in shell-shock draw paths before drawing `rgp.shellShockBlurredMaterial` / related materials. That is useful lineage evidence that slot 8 is deliberately rebound per draw, consistent with the exact T6 `PER_OBJECT` source classification. It does **not** identify the image used by `shadowoverlay`.

## Exact retail executable gate

Required executable identity remains:

- file: `t6mp(1)(1).exe`
- bytes: `12,850,328`
- SHA-256: `11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1`
- image base: `0x00400000`

The executable was previously user-supplied and extensively analyzed, but its raw bytes are not currently materialized in the active source corpus. Retained File Library records independently preserve the same byte count and SHA.

## Next exact static/runtime proof

When the exact executable bytes are available, search/trace in this order:

1. locate retail implementations/callers corresponding to the sun-shadow overlay routine family;
2. identify writes to T6 code-image source slot `0x8` on that path;
3. identify writes to T6 code-constant source `0x1A` on that path;
4. source-close the concrete render-target image assigned to slot 8;
5. source-close the four `filterTap[0]` floats for the draw;
6. identify the exact Material pointer used by the draw and bind it to native `shadowoverlay`;
7. retain instruction bytes, addresses, cross-references and target executable SHA.

A passive runtime observation of those same identities in the exact SHA-matching client is also acceptable corroboration, but must not substitute for binary identity.

## Proof boundary

Authoritative here:

- T6 numeric/accessor identities `feedbackSampler = 0x8` and `filterTap[0] = 0x1A` from pinned T6 source definitions;
- the native Material/Technique/shader chain and exact shader arithmetic already closed elsewhere.

Not authoritative here:

- which image is placed in codeImages[8] for shadowoverlay;
- the values placed into filterTap[0];
- the exact retail address/body of the shadow-overlay renderer routines;
- a renderer-global Material field;
- any T5/COD4/OpenBO2 high-level behavior not independently closed against the exact retail T6 executable/runtime.
