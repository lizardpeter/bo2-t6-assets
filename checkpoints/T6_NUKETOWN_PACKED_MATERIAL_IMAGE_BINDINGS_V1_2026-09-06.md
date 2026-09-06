# T6 Nuketown packed Material -> exact GfxImage payload bindings v1

This checkpoint promotes the pointer-proven packed-image alias bank and the canonical 81/81 retail IPAK payload closure into explicit packed `Material` texture-slot bindings.

## Result

- packed Materials with exact bindings: **49**
- exact packed Material/slot bindings: **94**
- retained evidence joins: **94**
- aliases represented: **81 / 81**
- unique exact retail payloads: **81**
- conflicts: **0**

Each binding preserves the exact packed Material identity, texture-table slot, semantic, sampler state, packed GfxImage virtual address, GfxImage name/hash/dataHash/dimensions, and exact retail IWI SHA-256.

No material-name suffix, visual similarity, slot-order guess, or old GLB assignment is used to promote a binding. Multiple witnesses are collapsed only when all identity fields agree exactly.

## Proof artifact

- raw JSON bytes: **68,468**
- raw SHA-256: `bbce72a824d34c439bd2edc0706e2c2ebb68d3b66af4ed31039e3763feeeb3ea`
- stored zlib+base64 bytes: **12,009**
- stored SHA-256 (without trailing newline): `649ded6107e98ca6bcc33cd1592fb579c49e2d3625a41056393e1a921c62f606`
