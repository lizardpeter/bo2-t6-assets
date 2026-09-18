# T6 five-root current-client scalar relation — 2026-09-18

The persisted exact five-root conflict census is now joined to the independently byte-evaluated current-client classifier scalar function without selecting a winner.

## Exact result

`proof/current_client/T6_CURRENT_CLIENT_FIVE_ROOT_SCALAR_RELATION_V1.json` proves all **58/58** unresolved divergent child-Technique conflicts have owner0 scalar lower than owner1 scalar:

- all 57 map-root vs `patch_mp` conflicts: map classifier `0x8000` -> scalar **57**, patch classifier `0x02` -> scalar **65**;
- the one `common_mp` vs `patch_mp` conflict: common classifier `0x80` -> scalar **54**, patch -> **65**.

Thus the entire remaining conflict set has a non-tied current-client scalar relation, and `patch_mp` is the higher-scalar owner in all 58 comparisons. This is an exact current-client scalar statement, not a winner statement.

The first projection run (`35359047798`) correctly failed closed because the projector initially consumed only `constructedRowMap`, which does not contain the dynamically relevant `0x8000` single-bit row. The tool was repaired to ingest `singleBitAndZeroMap`; run 2 (`35359159580`) passed its projection step and persisted the proof as commit `c96e56f999d95e4ea110468d177522d16e8cdc5a`.

## Why winnerCount remains zero

The runtime proof already establishes that the scalar return controls relinking of a 16-byte record structure carrying a runtime zone index. It does not yet establish, with source-independent current-client byte evidence, which end/order of that linked structure is lookup-visible for duplicate assets and which concrete asset pointer is returned/preserved after relinking. Therefore the projection intentionally emits `winner=null`, `winnerAuthority=false` for all 58 conflicts.

## Next hard gate

A new global xref probe for the proven linked-record arena base `0x014342e0` is in flight. Use it to identify all readers of the 16-byte arena, prioritize functions that traverse link word `+0x0c` and return/read asset payload fields, and prove lookup visibility/order. Do not infer head/tail visibility from the insertion branch alone.

Historical-retail promotion remains a separate gate even after current-client duplicate visibility is closed.
