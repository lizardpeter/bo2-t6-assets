# T6 current-client decoded zone construction result — 2026-09-18

## Authority boundary

This is comparative evidence from the SHA-classified current Plutonium client only. It is not historical-retail authority and selects no Technique winner.

## Exact client

- revision: \`5346\`
- bytes: \`13263640\`
- SHA-256: \`770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf\`

## Decoded instruction-operand xrefs

- \`_mp\`: literals=39, oldRawPackedHits=8, decodedOperandXrefs=8
- \`_zm\`: literals=19, oldRawPackedHits=0, decodedOperandXrefs=0
- \`code_post_gfx\`: literals=1, oldRawPackedHits=2, decodedOperandXrefs=2
- \`code_post_gfx_mp\`: literals=0, oldRawPackedHits=0, decodedOperandXrefs=0
- \`common\`: literals=1, oldRawPackedHits=2, decodedOperandXrefs=2
- \`common_mp\`: literals=1, oldRawPackedHits=0, decodedOperandXrefs=0
- \`common_patch_mp\`: literals=0, oldRawPackedHits=0, decodedOperandXrefs=0
- \`localized_code_post_gfx\`: literals=0, oldRawPackedHits=0, decodedOperandXrefs=0
- \`localized_code_post_gfx_mp\`: literals=0, oldRawPackedHits=0, decodedOperandXrefs=0
- \`mp_nuketown_2020\`: literals=1, oldRawPackedHits=2, decodedOperandXrefs=1
- \`patch\`: literals=14, oldRawPackedHits=1, decodedOperandXrefs=1
- \`patch_mp\`: literals=0, oldRawPackedHits=0, decodedOperandXrefs=0

## Structural 12-byte-row comparison

- admitted structural row candidates: **0**

## Exact fastfile-name constructor

- constructor range: `0x005806e0`..`0x005808ec`
- decoded constructor instructions: **128**
- selected helper calls: **26**
- exact destination buffers: **14**

### Destination-buffer consumers

- `0x012eaddc`: decodedOperandXrefs=15
- `0x0131bf00`: decodedOperandXrefs=6
- `0x0135a544`: decodedOperandXrefs=2
- `0x0143326c`: decodedOperandXrefs=3
- `0x01433284`: decodedOperandXrefs=2
- `0x014332a0`: decodedOperandXrefs=2
- `0x014334bc`: decodedOperandXrefs=2
- `0x01707b4c`: decodedOperandXrefs=6
- `0x01707b64`: decodedOperandXrefs=4
- `0x01709508`: decodedOperandXrefs=4
- `0x01709520`: decodedOperandXrefs=2
- `0x018018d0`: decodedOperandXrefs=3
- `0x018018e8`: decodedOperandXrefs=6
- `0x01805c90`: decodedOperandXrefs=3

## Constructed-name 12-byte-row comparison

- admitted constructed-name row candidates: **10**
- `0x0131bf00`: **1**
- `0x01707b4c`: **2**
- `0x01707b64`: **1**
- `0x01709508`: **2**
- `0x018018e8`: **3**
- `0x01805c90`: **1**

## Artifact identities

- decoded xref JSON: 110,394 bytes, SHA-256 \`dde226b48d17220241ca62f132b6b0e6f7cc6304c18894aa9905aa645979b7c3\`
- structural row JSON: 6,219 bytes, SHA-256 \`ef9c7b524c1b34928c270361cbddd46e2a33bff920930ed4a563f019926125d5\`
- fastfile-name construction JSON: 373,148 bytes, SHA-256 \`21f69123d49db277afb2ff35d2963bb3510702e4052b746aa2d616ddce848c14\`
- constructed-name row JSON: 19,503 bytes, SHA-256 \`5b5feb017f49038a99ee68f89cb3416818c1bee82c5639abc5051227a1b18d0e\`

## Proof boundary

Only decoded executable instruction operands equal to an exact mapped target-string VA are admitted as xrefs. Raw packed-address byte hits are retained solely to measure the prior method's false-positive surface and are never treated as references. String use, proximity, formatting, or a nearby call does not establish DB load semantics, XZoneInfo ownership, historical-retail behavior, or a Technique winner.

A candidate requires decoded straight-line stores tying an exact mapped target string pointer to the same effective memory row at +0 and a concrete value at +4. ESP-relative offsets are normalized only through exact push/pop/add/sub forms. This can demonstrate a current-client 12-byte-row-like construction but does not prove that the row is XZoneInfo, that +4 has retail allocFlags semantics, that server flag priorities apply, or that any historical-retail Technique winner is selected.

The constructor range, direct calls, contiguous push arguments, mapped C strings, destination-buffer VAs, and decoded operand xrefs are exact for the SHA-classified current client. Cdecl argument ordering is recorded only for contiguous PUSH sequences immediately preceding a direct CALL. Helper behavior can be inspected from the included instructions, but no source symbol name is assigned. Buffer construction/use does not prove XZoneInfo semantics, allocFlags, precedence, historical-retail equivalence, or any Technique winner.

A candidate requires a decoded straight-line store of an exact constructor destination-buffer pointer at row +0 and a concrete value at the same effective row +4, with the row-base register stable; +8 is retained when concrete. This tests the server-proven 12-byte shape without importing server flag values or priorities. A shape match does not prove the current-client row is XZoneInfo, does not name its +4/+8 fields, and cannot select a historical-retail winner.

## Next step

Use only decoded operand xrefs and admitted same-row +0/+4(/+8) stores as anchors for further current-client data-flow recovery. Raw packed-address hits and proximity-only calls remain excluded. If no exact full-zone row is recovered, trace exact base-string construction into the eventual row pointer without importing dedicated-server flag values. Historical-retail promotion still requires genuine retail executable/runtime evidence.

## Existing closure preserved

- production GfxImage denominator: **450**
- exact DDS coverage: **75/450**
- unresolved shader ownership: **58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials**
