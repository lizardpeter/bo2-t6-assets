# T6 Nuketown MapEnt source census v1

The map-owned entity string was regenerated directly from the exact retail `mp_nuketown_2020.ff` expansion and sliced at the already source-closed ClipMap/MapEnt serialization span. No prior GLB or hand-authored placement list was used.

## Source

- expanded FastFile SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`
- MapEnt entity-string bytes: **177,971**
- MapEnt entity-string SHA-256: `4a7966ac877fd5fe57746ad4e71bc765660f91d67a108a363cbfb5007524e104`

## Census

- total entities: **1276**
- named model references: **151**
- unique named model tokens: **58**
- script_model entities: **147**
- destructible script models: **64**
- parked/destructible car entities: **6**
- car script-model entities including animated phases: **8**
- fxanim scene entities: **5**

Machine-readable census bytes: **354,194**; SHA-256: `a77fa2145bc4d5be7e9bc9b710136b7a6b4553f9ddc76f6f0e7c5aed21b4c55c`.

All car/fxanim placements in the manifest preserve the exact entity key/value pairs plus parsed source `origin`/`angles`. Duplicate gameplay phases remain separate source entities and are not rendered simultaneously unless runtime semantics prove that behavior.
