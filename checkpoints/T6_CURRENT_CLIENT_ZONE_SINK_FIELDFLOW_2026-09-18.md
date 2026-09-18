# T6 current-client zone sink field flow — 2026-09-18

## Authority boundary

Current Plutonium revision 5346 comparative evidence only. Nothing here establishes historical-retail behavior or selects a Technique winner.

## Exact transaction

The SHA-classified client remains `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`. The recovered 12-byte-row sink remains `0x004174b0` with the previously persisted bounded CFG of 1,020 instructions / 302 basic blocks.

`tools/t6_current_client_zone_sink_fieldflow_probe_v1.py` (`c977e31a0524d680beb1cb278f3696e04031237f`) now inventories exact decoded memory operands at candidate row displacements 0/4/8 throughout that CFG. Workflow `.github/workflows/t6_current_client_zone_sink_fieldflow_probe_v1.yml` (`a99e98eabec4abbb0fdba7c6b580e635aaa97285`) ran and persisted `proof/current_client/T6_CURRENT_CLIENT_ZONE_SINK_FIELDFLOW_PROBE_V1.json` in `726667bef965af0819a94c3367c8da6701f06f5b`.

Exact register groups recovered:

- `edi`: 80 hits; offsets 0=54, 4=26; no +8.
- `ebx`: 33 hits; offset 0 only.
- `esi`: 26 hits; offset 0 only.
- `esp`: 21 hits; offset 0 only.
- `eax`: 10 hits; offsets 0=5, 4=2, 8=3.
- `ebp`: 8 hits; offsets 0=6, 4=1, 8=1.
- `ecx`: 7 hits; offsets 0=6, 4=1; no +8.
- `edx`: 2 hits; offset 0 only.

Therefore only `eax` and `ebp` have exact decoded accesses at all three candidate row offsets in the bounded sink CFG. This is a search-space reduction only: neither register is promoted to the input-row pointer from offset coverage alone.

A compact fail-closed projector was added in `478e922a7ce793e2e6864f4a0802e91ceda19879` with workflow `67a13a9351eb1cee3a525ce3a3c9bc9ccd760444`. Its run is `35347412200`; at checkpoint creation it was still in progress, so no result is claimed yet.

## Exact next gate

Recover compact run `35347412200`, then trace the selected `eax` and `ebp` contexts backward to the exact row-pointer/count arguments entering `0x004174b0`. The first hard question is whether either register is byte-proven to derive from the incoming row pointer before its +0/+4/+8 accesses. If yes, trace +4 and +8 forward into comparisons/callees; if no, pivot to the eight exact 12-byte stride sites. Do not assign `allocFlags`/`freeFlags` names until the client data flow independently proves those semantics.

## Existing closure preserved

- production GfxImage denominator: **450** identity-deduplicated images
- exact DDS coverage: **75/450**
- unresolved shader ownership: **58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials**
