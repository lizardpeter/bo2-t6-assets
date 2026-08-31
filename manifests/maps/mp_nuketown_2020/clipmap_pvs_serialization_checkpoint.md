# Nuketown 2025 T6 ClipMap_PVS serialization checkpoint

Map: `mp_nuketown_2020`
Source FastFile: `mp_nuketown_2020.ff`
Decompressed byte-stream SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`

## Acceptance rule

This proof is for the native T6 collision asset, not a triangles-only approximation. A completed decoder must preserve the full `clipMap_t`/PVS structure, collision materials and flags, BSP/leaf/brush topology, submodels, DynEnt relationships, constraints/ropes, MapEnts, triggers where present, and standard engine-friendly collision geometry without discarding lossless T6 metadata.

## Asset identity

The raw 840-entry T6 `XAssetList` directly proves this neighborhood:

- asset **624**: `GFXWORLD`
- asset **625**: `GAMEWORLD_MP`
- asset **626**: `TECHNIQUE_SET`
- asset **627**: `TECHNIQUE_SET`
- asset **628**: `GLASSES`
- asset **629**: **`CLIPMAP_PVS`**
- asset **630**: `FX`

Therefore the Nuketown `CLIPMAP_PVS` top-level asset index is **629**. An earlier draft of this checkpoint incorrectly described raw index 625 as `CLIPMAP_PVS`; that was rejected after re-reading the exact XAsset array.

## Fixed `clipMap_t` header

- Fixed start: **87,882,673** (`0x053CFBB1`)
- Fixed size: **332 bytes**
- Fixed end: **87,883,005**

Header counts decode coherently as:

| Component | Count |
| --- | ---: |
| planes | 15,197 |
| materials | 704 |
| brush sides | 38,928 |
| leaf-brush nodes | 12,115 |
| leaf brushes | 24,563 |
| brush vertices | 79,670 |
| uinds | 50,224 |
| brushes | 9,284 |
| collision static models | 1,712 |
| BSP nodes | 2,753 |
| BSP leaves | 2,938 |
| terrain collision verts | 26,150 |
| terrain collision tris | 37,480 |
| partitions | 7,411 |
| collision AABB trees | 19,322 |
| submodels | 184 |
| PVS clusters | 1 |
| bytes per cluster | 184 |
| original DynEnt count | 131 |
| DynEnt counts | 387 / 0 / 131 / 0 |
| constraints | 0 |
| max ropes | 32 |

The MapEnts field uses an INSERT-style identity-preserving pointer sentinel, so the MapEnts object follows inline while retaining asset identity semantics.

## Exact replay through MapEnts

The pre-MapEnts cursor closes exactly:

```text
fixed clipMap_t                    ->  87,883,005
704 ClipMaterials + names          ->  87,897,926
38,928 brush sides                 ->  88,365,062
12,115 leaf-brush nodes + refs     ->  88,656,894
79,670 brush verts                 ->  89,612,934
50,224 uinds                       ->  89,713,382
9,284 brushes                      ->  90,604,646
1,712 collision static models      ->  90,748,454
2,753 BSP nodes                    ->  90,770,478
2,938 BSP leaves                   ->  90,899,750
26,150 collision verts             ->  91,213,550
37,480 triangle index triplets     ->  91,438,430
14,056 walkability bytes           ->  91,452,486
7,411 partitions                   ->  91,571,062
19,322 CollisionAabbTrees          ->  92,189,366
184 cmodels                        ->  92,203,350
1 x 184-byte PVS                   ->  92,203,534
MapEnts fixed header               ->  92,203,570
177,971-byte entity string         ->  92,381,541
```

The walkability count is the native T6 formula:

`((3 * triCount + 31) / 32) * 4`

For `triCount = 37,480`, this is exactly **14,056 bytes**.

Visibility is exactly `numClusters * clusterBytes = 1 * 184 = 184` bytes, and lands on the independently located MapEnts fixed header at byte **92,203,534**. Nuketown's 184 PVS bytes are all `0xFF`.

## MapEnts correction

This Nuketown MapEnts has:

- compiled trigger models: **0**
- compiled trigger hulls: **0**
- compiled trigger slabs: **0**

The T6 format supports these structures and the generalized decoder must preserve them on maps that contain them. Nuketown itself is not a trigger-layout oracle.

## Tail closure

The remaining **serialized-source** tail is now closed.

### Box collision brush

The entity string ends at byte **92,381,541**. A valid 96-byte PC32 `cbrush_t` begins immediately there:

- `mins = (0,0,0)`
- `contents = -1`
- `maxs = (0,0,0)`
- `numsides = 0`
- `sides = null`
- `numverts = 0`
- `verts = null`

Span: **92,381,541 -> 92,381,637**.

There are no nested sides/vertices for this box brush.

### DynEntityDef list

`dynEntDefList[0]` starts immediately at byte **92,381,637**.

- count: **387**
- PC32 record size: **84 bytes**
- serialized bytes: **32,508**
- end: **92,414,145**
- type counts: **256 type 0, 119 type 1, 12 type 2**

All 387 fixed records decode coherently. The first record places a type-1 dynamic entity at approximately `(1069.78, 119.934, 2.5)` with a normalized-looking quaternion and packed XModel/PhysPreset references.

Critically, `destroyPieces` is null for **all 387** records, so Nuketown contributes no inline `XModelPieces` payload in this DynEntityDef list. Observed non-null XModel, destroyed-XModel, destroy-FX and PhysPreset pointers are packed reusable asset references rather than FOLLOWING/INSERT payloads.

`dynEntDefList[1]` has count 0 and consumes no source bytes.

### Runtime block arrays do not consume FastFile bytes

The following ClipMap fields are assigned to `XFILE_BLOCK_RUNTIME_VIRTUAL` by the T6 serialization contract:

- `dynEntPoseList[0..1]`
- `dynEntClientList[0..1]`
- `dynEntServerList[0..1]`
- `dynEntCollList[0..3]`
- `ropes`

This is now resolved from the actual OpenAssetTools loader implementation. `ZoneInputStream::LoadDataFromBlock` handles `BLOCK_TYPE_RUNTIME` using `memset(dst, 0, size)` instead of `m_stream.Load(dst, size)`. Runtime arrays therefore advance/occupy destination runtime-block memory but consume **zero serialized source bytes**.

That is why treating byte 92,414,145 as a `DynEntityPose` produced garbage: it was already the next top-level asset.

`num_constraints = 0`, so constraints also consume zero source bytes on Nuketown.

### Exact next-asset boundary

Byte **92,414,145** is independently proven as top-level asset **630 `FX`**:

- `FxEffectDef` fixed size: **76 bytes**
- fixed start: **92,414,145**
- `name = 0xFFFFFFFF` (FOLLOWING)
- all three element counts = 0
- `elemDefs = null`
- inline name starts exactly at `fixedStart + 76 = 92,414,221`
- inline name: `,impacts/fx_small_impact_core`

Therefore asset 629 cannot extend past byte 92,414,145.

## Exact asset-629 serialized span

**`CLIPMAP_PVS` source-byte closure is complete for Nuketown.**

- start: **87,882,673**
- end: **92,414,145**
- total serialized bytes: **4,531,472**
- serialized-span SHA-256: `5f275dbae3110a5f402405be9a3f69baa674f816832e8f736b0167dadd5270f0`

Machine-readable section hashes and tail evidence are recorded in `clipmap_pvs_tail_proof.json` beside this file.

## Alignment rule learned

Do **not** treat native `alignas`/`type_align32` requirements as a blanket instruction to align every FastFile source cursor. The existing raw-XAsset proof establishes the actual T6 rule: XBlock alignment advances destination memory only and consumes **no serialized source bytes**. The Nuketown collision replay confirms this directly; forcing source-cursor padding before aligned native structures breaks valid downstream records.

## Generalization status

What is proven here is the exact **retail Nuketown oracle**. Production code must not hardcode the offsets above. The generalized decoder must derive the same sequence from:

1. the XAsset identity/type,
2. the fixed `clipMap_t` fields,
3. pointer sentinel/reusable-pointer semantics,
4. native structure sizes/counts,
5. XBlock type behavior,
6. nested-object rules.

Next core task: encode this replay as a self-validating ClipMap walker/normalized decoder, then validate it against additional T6 maps—especially one with non-zero MapEnt trigger geometry, non-zero constraints, and/or different DynEnt composition.
