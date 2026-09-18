# T6 current-client constructed zone-row closure — 2026-09-18

## Authority boundary

Comparative current-client evidence only. This checkpoint does **not** establish historical-retail `t6mp.exe` behavior and does not select any of the 58 unresolved historical-retail Technique winners.

## Exact client / source proof

Current Plutonium revision `5346`, `t6mp.exe` 13,263,640 bytes, SHA-256 `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`.

Workflow `T6 current client decoded zone construction probe v1` run `35342122514`, job `105590180567`, completed green. Artifact `10545750508` (`T6_CURRENT_CLIENT_ZONE_CONSTRUCTION_PROBE_V1`) has ZIP digest `sha256:080cd941b998eaf757bf0644d13bfc710ecac260404c386eb357a87bd9e26847`.

The workflow persisted `proof/current_client/T6_CURRENT_CLIENT_FASTFILE_NAME_CONSTRUCTION_PROBE_V1.json` with SHA-256 `21f69123d49db277afb2ff35d2963bb3510702e4052b746aa2d616ddce848c14`.

## New exact result

The constructor at `0x005806e0..0x005808ec` first copies exact base names into fixed destination buffers and then appends the exact `_mp` suffix. This establishes the constructed identities of those buffers without relying on naming adjacency or raw-byte scans.

Following only decoded executable operand xrefs to those exact buffers recovers a common consumer target `0x004174b0` and exact stack-built **12-byte rows**. After normalizing the two argument pushes, each row has the destination-buffer pointer at `+0`, a concrete positional value at `+4`, and a concrete positional value at `+8`.

Exact rows now recovered:

| constructed name | call site | count | row | +4 | +8 |
|---|---:|---:|---:|---:|---:|
| `common_mp` | `0x00459440` | 1 | 0 | `0x00000080` | `0x00000000` |
| `patch_ui_mp` | `0x0045940e` | 2 | 0 | `0x08000000` | `0x00000000` |
| `ui_mp` | `0x0045940e` | 2 | 1 | `0x02000000` | `0x00000000` |
| `patch_mp` | `0x00611336` | 2 | 0 | `0x00000002` | `0x00000000` |
| `code_post_gfx_mp` | `0x00611336` | 2 | 1 | `0x00000008` | `0x00000000` |
| `ffotd_mp` | `0x00922a35` | 1 | 0 | `0x20000000` | `0x80000000` |

The particularly important current-client construction at `0x00611303..0x00611336` is byte-explicit: it zeroes the two row `+8` slots, takes a pointer to the first row, pushes count `2` and that pointer, stores `patch_mp` / `2` into row 0, stores `code_post_gfx_mp` / `8` into row 1, then calls `0x004174b0`.

Likewise `common_mp` is passed as one 12-byte row with positional values `0x80, 0`, and `patch_ui_mp` + `ui_mp` are passed as two contiguous rows with positional values `0x08000000,0` and `0x02000000,0`.

This supersedes the earlier **zero admitted row** result only in a precise way: that earlier probe looked for direct use of immutable target-string VAs. The client actually constructs mutable fastfile-name buffers first. Tracing those exact buffers to consumers closes the missing indirection and yields the rows above.

Derived proof is persisted as `proof/current_client/T6_CURRENT_CLIENT_CONSTRUCTED_ZONE_ROWS_V1.json`.

## What is proven vs not proven

**Proven for the SHA-classified current client:** exact base-name copies, exact `_mp` appends, exact destination buffers, exact decoded consumer xrefs, exact 12-byte row stride, exact row counts, exact positional `+4/+8` values, and the common consumer target `0x004174b0`.

**Not promoted:** source symbol identity for `0x004174b0`; the source-level names `XZoneInfo`, `allocFlags`, or `freeFlags`; historical-retail equivalence; server priority semantics; or any of the 58 Technique winners. The numerical agreement of `common_mp=0x80`, `patch_mp=2`, and `code_post_gfx_mp=8` with server-lineage expectations is comparative evidence, not historical-retail proof.

## Exact next blocker

Disassemble and recover the bounded function/control-flow body at `0x004174b0`, then trace the row pointer/count arguments forward. Determine from decoded memory/data-flow evidence where the `+4` and `+8` fields are consumed and whether the same routine reaches zone registration/loading state. In parallel, recover historical retail/runtime evidence using these now-exact current-client call sites and row shapes as search/instrumentation anchors. Do not name `0x004174b0` from similarity alone.

The production texture denominator remains closed at 450 identity-deduplicated GfxImages with 75/450 exact DDS coverage. The historical-retail shader ownership set remains 58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials.
