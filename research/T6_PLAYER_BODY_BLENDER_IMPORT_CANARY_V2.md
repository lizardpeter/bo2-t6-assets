# T6 multiplayer player-body Blender import canary v2

Status: **visual revalidation required**

The first 30-body LOD0 GLB inspection batch passed structural GLB, XModel, skeleton, triangle-index, weight-coverage and bind-hierarchy checks, but a Blender inspection of `c_chn_mp_pla_assault_fb` showed an obviously unusable flattened/top-down-looking result. Therefore the first batch must not be treated as Blender-validated.

## What is still proven

For retail `c_chn_mp_pla_assault_fb` in `faction_pla_mp`:

- XModel fixed start: `814186`
- XModel fixed SHA-256: `888e96ab962d932eccf2a337ca3df2d504203de7af81271e883854c58f88f769`
- expanded stream SHA-256: `d853e71040dc1fabc78bf9a65d53d25b69043d0312ceda52153a4054e34ae5c3`
- 102 bones / 1 root
- LOD0: 17 surfaces, 11,643 vertices, 13,490 triangles
- 0 unweighted LOD0 vertices
- native XModel bounds in T6 inches:
  - min `[-11.4172344208, -21.0440578461, -0.0463970453]`
  - max `[14.4817829132, 21.0440540314, 71.8889999390]`
- decoded LOD0 vertex extrema reproduce those native XModel bounds exactly.
- independent raw-vertex projections are recognizably a complete human player body; the source vertex decode is not a spherical/blob mesh.

## Suspected export/import failure boundary

The first inspection GLBs carried the T6 Z-up/inches -> glTF Y-up/meters conversion on a parent `__T6_WORLD_TO_GLTF__` node shared by the skinned mesh and joint hierarchy. Structural glTF validation does not prove Blender preserves that wrapper relationship when reconstructing an Armature from a glTF skin.

The Blender screenshot is consistent with the body being observed approximately along its native height axis rather than with corrupt source positions. This makes the wrapper/skin import boundary the current leading hypothesis, but it is **not promoted as closed until Blender visual revalidation**.

## v2 canary strategy

The replacement canary removes the corrective wrapper entirely. Instead it bakes the basis and unit conversion into all dependent data:

- vertex positions: T6 Z-up inches -> glTF Y-up meters
- vertex normals: same basis rotation, no scale
- bone local translations: same basis + meter conversion
- bone local rotations: basis conjugation
- global base-matrix translations/rotations: same conversion
- inverse-bind matrices: recomputed from the converted global bind transforms

The resulting PLA glTF-space bounds are:

- min `[-0.2899977543, -0.00117848495, -0.5345189724]`
- max `[0.3678372860, 1.8259805984, 0.5345190693]`

Converted bind hierarchy maximum errors:

- quaternion: `2.9900917409e-08`
- translation: `9.0257176621e-08` meters
- decoded glTF joint-global × inverse-bind maximum identity error: approximately `2.6e-07`

Two inspection canaries were emitted locally from the same converted geometry:

1. `PLA_ASSAULT_RIGGED_LOD0_BLENDER_V2.glb`
   - SHA-256 `3d4734b33fda0952a3d5031d35542c8947d6bc93e6b9f33e093c5ff7bbd8b62b`
   - complete 102-joint skin
2. `PLA_ASSAULT_STATIC_LOD0_BLENDER_V2.glb`
   - SHA-256 `3ee9f230b7733a3c82097d813cedd74496f5387ec54306d14d631a98798cad43`
   - same converted mesh, skin/armature removed to isolate Blender mesh-coordinate import from Blender skin reconstruction

A matching SEAL6 SMG rigged v2 canary was also emitted:

- `SEAL6_SMG_RIGGED_LOD0_BLENDER_V2.glb`
- SHA-256 `c3bc5d08f2b8c03ed8c4d54379d910601f77d7831ba2eae27bb71421e03bef92`

## Promotion rule

Do not regenerate/promote the full 30-body Blender batch until the PLA static-v2 and rigged-v2 pair are visually checked in Blender. If static is correct but rigged is not, the remaining fault is specifically in the glTF skin/Armature import path. If both are correct, the baked-basis exporter can replace the wrapper-based inspection export for the 30-body corpus.
