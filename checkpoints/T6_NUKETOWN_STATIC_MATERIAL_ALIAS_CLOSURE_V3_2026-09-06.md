# T6 Nuketown static material alias closure v3 — 2026-09-06

This checkpoint opens and validates exact cross-XModel VIRTUAL-cursor propagation for the fresh `mp_nuketown_2020` static rebuild.

## Exact control

The route carries the block-5 VIRTUAL cursor across source-contiguous top-level XModels. `XModel` fixed records themselves live in TEMP, while the inline XModel name participates in the persistent VIRTUAL stream before the bone/base/surface allocations. That accounting is independently controlled by the retail XAsset 30 -> 31 transition:

- source: `nt_2020_books_row03` -> `nt_2020_books_row01`
- source boundary is exactly contiguous
- XAsset 30 material-handle base: `1,867,060`
- predicted XAsset 31 material-handle base: `1,878,856`
- independently v2-anchored XAsset 31 base: `1,878,856`
- mismatch: **0 bytes**

The route fails closed on inline Material/PhysPreset/Collmap/PhysConstraints tails, source drift, independently anchored base disagreement, or alias conflict.

## First propagation chain

A clean no-inline-material chain is now closed:

- XAsset 251 `nt_2020_foliage_hedge_boxy01`
- -> XAsset 252 `nt_2020_foliage_hedge_boxy_2_set`
- -> XAsset 253 `mlv/nt_vista_red_tent`

The exact propagated material-handle base for XAsset 252 is `25,019,596`. Continuing through XAsset 252 yields the exact XAsset 253 base and promotes one previously unresolved referenced material slot:

- block 5 / offset `25,121,504` -> `mlv/mtl_nt_vista_red_tent`

No material-name similarity or ordering-only guess is involved; the identity is admitted because the inline Material occupies the exact propagated handle slot.

## Closure improvement

- v2: **106 / 286** unique packed material targets, **548 / 901** packed references
- v3: **107 / 286** unique packed material targets, **549 / 901** packed references
- remaining: **179 unique targets / 352 references**
- alias conflicts: **0**
- known exact material-handle-array bases: **33**
- exact cross-XModel propagations completed: **3**
- independent cross-XModel controls: **1**, pass

The current v3 stops rather than guessing when the source XModel tail contains an inline Material. The next extension is the already retail-proven T6 Material/GfxImage dispatcher from `t6_clipmap_serialized_walker_v3.py`, which will let the VIRTUAL cursor traverse those inline-material tails and unlock many of the remaining source-contiguous runs.

## Artifacts

Local exact source:

- `t6_nuketown_static_material_alias_resolve_v3.py`
  - bytes: 14,662
  - SHA-256: `b33e28e355ee62e869a4a9c44b8a2740a87d5b66896fefab48e1e8656ac4fbad`
- `T6_NUKETOWN_STATIC_MATERIAL_ALIAS_CLOSURE_V3.json`
  - bytes: 47,588
  - SHA-256: `ad8629fda4a2e32414bb0c21667610db35cc87a4bf15747fc5fa684ca1e9b78b`

Repository payloads are zlib+base64 encodings of those exact bytes. Decode with `zlib.decompress(base64.b64decode(payload))` and verify the SHA-256 values above before use.

## Forward-only boundary

This is still a source-closure checkpoint, not a downloadable visual successor. It must eventually be merged with the fresh GfxWorld, all 2,992 statics, exact textures/materials, lighting/reflections, collision/gameplay layers, MapEnt cars and v31+ shader contracts, then pass both the v25 visual floor and the full-asset integration floor.
