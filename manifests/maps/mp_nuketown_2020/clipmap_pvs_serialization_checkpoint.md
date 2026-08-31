# Nuketown 2025 T6 ClipMap_PVS serialization checkpoint

Map: `mp_nuketown_2020`
Source FastFile: `mp_nuketown_2020.ff`
Decompressed byte-stream SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`

## Acceptance rule

This proof is for the native T6 collision asset, not a triangles-only approximation. A completed decoder must preserve the full `clipMap_t`/PVS structure, collision materials and flags, BSP/leaf/brush topology, submodels, DynEnt relationships, constraints/ropes, MapEnts, triggers where present, and standard engine-friendly collision geometry without discarding lossless T6 metadata.

## Asset numbering

Two asset indices are retained because they describe different things:

- Raw `XAssetList` index: **625** (`CLIPMAP_PVS`)
- Serialized/walked asset index: **629**

The walked index is four higher because four inserted/alias slots occur earlier in the serialized walk. Do not silently collapse these numbering systems.

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

The pre-MapEnts cursor now closes exactly:

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

## Alignment rule learned

Do **not** treat native `alignas`/`type_align32` requirements as a blanket instruction to align every FastFile stream cursor. Actual retail serialization must be followed field-by-field. Forcing a 16-byte file-cursor alignment before the Nuketown `CollisionAabbTree` stream produces invalid records; the unforced cursor produces coherent T6 structures and the exact downstream MapEnts boundary.

## Remaining tail to close

The fixed header already constrains the remaining serialized tail. Next proof target:

`box collision -> DynEntityDef -> DynEntityPose -> DynEntityClient -> DynEntityServer -> DynEntityColl -> constraints -> ropes -> exact asset end / next-asset boundary`

Any nested `XModelPieces` / destroy-pieces data must be walked rather than skipped. The final generalized decoder must derive all offsets from the T6 structure/count/pointer contract and must contain no Nuketown-specific byte offsets.
