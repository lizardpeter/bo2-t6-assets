# T6 Multiplayer Body Closure v1 — 2026-09-05

## Scope

This checkpoint records the multiplayer third-person player-body extraction path on branch `reversal/nonmap-assets` after the 30-body discovery matrix was separated from retail promotion.

The goal is not to infer player bodies from naming conventions. The goal is a deterministic path from direct retail faction-zone bytes to a registry-ready body proof that can feed the character × player-animation selector matrix.

## Current multiplayer body universe

The retained retail viewhands census yields six multiplayer faction prefixes:

- SEAL6 — `c_usa_mp_seal6`
- FBI — `c_usa_mp_fbi`
- PLA — `c_chn_mp_pla`
- PMC — `c_mul_mp_pmc`
- ISA — `c_usa_mp_isa`
- Cordis — `c_mul_mp_cordis`

The discovery generator combines each with five body classes:

- `assault`
- `lmg`
- `shotgun`
- `smg`
- `sniper`

This produces 30 non-authoritative full-body XModel search targets. Ten SEAL6/PLA names are independently enumerated discovery targets; the other twenty are convention-derived. Neither evidence tier is allowed to promote a body without an exact retail XModel definition.

Current checked-in promotion state remains:

- 30 candidate bodies
- 1 retail-proven full body
- 29 unresolved candidates

The one retail-proven body remains `c_usa_mp_seal6_smg_fb` from `faction_seals_mp.ff`:

- 102 bones
- 1 root bone
- 42 surfaces
- 21,188 decoded vertices
- 21,283 decoded triangles
- fixed XModel record SHA-256 `399b9902fadc56e9ad025b19abf404675bd0ce872ea86c4c100e0a286fe3f056`
- fixed+name SHA-256 `f452b7b51c175d206c688839d6ccb3d5c6cdbdef80781d6fd50cb20622778d83`
- normalized skeleton SHA-256 `151fdfa7cfbcfa4a27fe0792965a76ba279058c455c937928ef97442227fa426`
- normalized mesh SHA-256 `a8c71af373f955f26cbc92f210345712f42c5727e69c9893a614d428303dd9ba`
- source fastfile SHA-256 `1a075434760751551158b7d62cc2761649e2d2c7606b27b3bbe066b998b77c88`
- expanded stream SHA-256 `21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30`

No additional faction body is promoted by this checkpoint because the raw faction FF/expanded binaries are not available to the current execution runtime.

## 54 weapons → 24 reusable selector profiles

The independent animation side remains unchanged:

- 54 directly proven `common_mp` player-facing weapon rows
- 24 distinct reusable player-animation selector profiles
- selector-profile compatibility is kept independent from named-weapon final precedence

The integrated matrix is therefore 30 bodies × 24 selector profiles = 720 cells.

Current retained-proof matrix state:

- 2 closed cells
- 22 cells pending retained SEAL6 compatibility proof regeneration
- 696 cells blocked on unresolved body identity
- 0 failed cells

No historical verbal result is silently upgraded into a checked-in proof artifact.

## New one-command body closure path

`tools/t6_player_body_close_v1.py` now provides the fail-closed path:

`exact XModel identity → exact top-level XAsset index → skeleton-v2 → mesh-v2 → retail body proof → body registry`

For one target body it emits durable intermediate artifacts and records the exact blocker stage if closure stops.

Blocker stages are:

1. `xmodel-identity`
2. `xasset-index-binding`
3. `skeleton`
4. `mesh`
5. `promotion`

A blocked run never emits `player_body_retail_proof_v1.json`.

## Retail body proof promoter

`tools/t6_player_body_retail_proof_v1.py` joins independent artifacts rather than decoding bytes itself.

Promotion requires all of the following:

- exact `t6-xmodel-target-probe-v1` identity
- exact fixed-record start and hash provenance
- exact expanded-stream byte count and SHA-256 agreement
- `t6-xmodel-skeleton-normalized-v2`
- all bone names resolved
- valid skeleton hierarchy
- exact bone/root cardinality match
- complete mesh normalized artifact
- exact mesh identity and expanded-stream match
- exact bone/root/surface/LOD cardinality match
- every emitted surface vertex/triangle array matches its declared count
- all local triangle indices are validated in range
- hash-pinned source fastfile and expanded stream

The resulting `t6-player-body-retail-proof-v1` is intentionally accepted by the existing `t6_player_body_identity_registry_v1.py` proof contract without a parallel registry format.

The promoter does **not** prove:

- player-script ownership
- materials or textures
- named-weapon precedence
- third-person animation compatibility
- complete player-bundle closure

## Packed skeleton reuse: closed narrowly

`tools/t6_xmodel_skeleton_normalize_v2.py` already resolves packed VIRTUAL skeleton arrays by proving a unique earlier inline XModel owner through allocation replay.

The previous mesh normalizer v1 nevertheless rejected a target immediately when any skeleton-array pointer was packed, even if the target's render surfaces were otherwise independently decodable.

`tools/t6_xmodel_mesh_normalize_v2.py` removes only that unnecessary restriction.

It permits packed skeleton header pointers at:

- `boneNames`
- `parentList`
- `quats`
- `trans`
- `partClassification`
- `baseMat`

only when a supplied skeleton-v2 artifact independently proves the same model, same XModel fixed start, same expanded stream, same bone/root counts, resolved names, valid hierarchy, and `skeletonSource.mode == packed_reusable_owner` when packed fields are present.

The packed skeleton arrays consume no serialized source bytes at the target location. Mesh v2 therefore presents those six pointers as null only to the inherited v1 source-cursor walker while retaining the real packed pointer metadata in its output.

No retail input bytes are modified.

## Explicit remaining render blocker

Mesh v2 still fails closed on packed/reused **render-surface data**.

This includes:

- packed top-level `XModel.surfs`
- packed `vertsBlend`
- packed tension data
- packed `verts0`
- packed rigid `vertList`
- packed triangle indices
- packed nested collision-tree payloads where their source ownership has not been proven

This is deliberate. Skeleton ownership does not automatically prove render-geometry ownership.

## Next exact target

The next narrow closure step is the case where:

1. the target XModel owns an inline `XModel.surfs.fixed` array;
2. the target skeleton-v2 proof identifies one unique reusable earlier XModel owner;
3. target and owner surface scalar signatures match exactly; and
4. the existing reusable-owner replay explicitly matches every packed nested render pointer that would be sourced from the owner.

For that case, a new mesh layer can decode the earlier owner's inline geometry and bind only the explicitly matched packed target payloads while preserving the target's own XModel header and LOD metadata.

It must fail if any packed render field lacks an explicit replay comparison. It must also continue to reject packed top-level `XModel.surfs`, which requires a broader persistent VIRTUAL asset-body allocation ledger.

## Durable commits in this tranche

- `c440a6177b490bb63be0f5a23ef11c55e8c92f2c` — retail player-body proof promoter
- `4951a1536b87fb819a9b388d592f454f8ba32dda` — promoter regression
- `e15887165fb3f1d5c62e15079b9450706c6faa4d` — promoter CI gate
- `4fdd1e52a2c4855fa414b8c2ebea72ebd37c9764` — one-command body closer
- `cb8226220407cab99aae893134b8b7fa5543327c` — body closer regression
- `be82b240221edcb46cd4cfc185f6a30b603f3864` — mesh normalizer v2
- `3fe5cf29293f9870fe6262fd25ef9f0b0c13f06d` — mesh-v2 regression
- `1fa8d1334ca8d66fb037e77efbfc12c8a6ade46b` — body promoter accepts independently proven mesh v2
- `5bc0537ad4b9daf5c7df3b0ff79af60d23541046` — body closer uses mesh v2
- `5d09e7d3aa8695325ac153fcc6e2c2dfc1fd8650` — mesh-v2 promotion regression coverage
- `e8dec221bd3c3c85db1a3be49b3d2000f1ee1879` — full body-closure path in focused CI

## Proof standard

The project remains fail-closed. Discovery names, convention matches, public asset dumps, historical verbal results, or compatible-looking skeletons are not substitutes for direct retail source closure.
