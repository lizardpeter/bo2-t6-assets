# T6 Nuketown MapEnt car XModel packed-name closure v1

Both parked/destructible car XModel identities are now source-closed without adjacent-name or old-GLB inference.

## Result

- parked/destructible MapEnt instances: **6 / 6**
- unique parked-car XModels: **2 / 2**
- unresolved models: **0**

### `veh_t6_nuketown_2020_car01_clean`

- StringTable VIRTUAL offset: **92858**
- packed XModel.name pointer: `0xA0016ABB`
- fixed source start: **44523322**
- bones / surfaces / LODs: **25 / 20 / 4**
- serialized span: **1,300,611 bytes**
- serialized SHA-256: `10c92c8039fe002be40b784eae19542419e8562f3eb1073a67cf65b4ceb23dd2`

### `veh_t6_nuketown_2020_car02_whole`

- StringTable VIRTUAL offset: **93100**
- packed XModel.name pointer: `0xA0016BAD`
- fixed source start: **41469954**
- bones / surfaces / LODs: **24 / 30 / 4**
- serialized span: **1,916,749 bytes**
- serialized SHA-256: `1f7c07c40541f94eaaab2431342006ee2768d572396f196541437d50f1082214`

## Proof boundary

Identity requires the exact MapEnt token, the exact self-calibrated StringTable VIRTUAL address, the exact packed block-5 name pointer at the first word of the XModel record, and a blocker-free complete XModel serialized walk. Literal string adjacency, mesh similarity, old scene assignments, and name guessing are not accepted.

- machine-readable manifest bytes: **4,269**
- manifest SHA-256: `ad2b749f08c77a88d47166cfa82eb0c1160482425f1f6f8525f1a2e1b748122a`
