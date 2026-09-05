# T6 First-Person / Human Benchmark v1 — 2026-09-05

**Track:** `reversal/nonmap-assets`  
**Benchmark:** `manifests/nonmap/benchmarks/seal6_smg_mp7_v1.json`  
**Purpose:** turn the existing generic XModel/XAnim work into one complete, retail-proven human + viewhands + weapon bundle before scaling to every T6 asset.

## Concrete benchmark

The first target is a SEAL6 SMG player paired with the MP7.

Candidate identities from independently dumped BO2 data:

| Role | Exact identity | Discovery source |
|---|---|---|
| third-person player body | `c_usa_mp_seal6_smg_fb` | `faction_seals_mp/mpbody/class_smg_usa_seals.gsc` |
| first-person viewhands | `c_usa_mp_seal6_shortsleeve_viewhands` | same script; used by `setviewmodel` |
| MP7 view model | `t6_wpn_smg_mp7_view` | dumped MP7 weapon definition |
| MP7 world model | `t6_wpn_smg_mp7_world` | dumped MP7 weapon definition |
| MP7 view magazine | `t6_attach_mag_mp7_view` | dumped MP7 weapon definition |
| MP7 world magazine | `t6_attach_mag_mp7_world` | dumped MP7 weapon definition |

These identities are **not** automatically promoted to proof. The benchmark spec records the external sources as discovery evidence and requires exact retained-retail resolution before a closure gate can pass.

## Retail animation proof already in this repository

`manifests/stage18d/xanim_raw_proof_summary.json` already pins the expanded `common_mp` stream:

```text
SHA-256 fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce
bytes   206493911
XAnimParts assets 4233
```

The direct raw proof finds **23 `viewmodel_mp7_*` records** and reports all 23 direct walks exact with exact consecutive boundaries.

The retained reload canary is:

```text
viewmodel_mp7_reload
raw fixed offset 18001446
86 frames @ 30 Hz
76 bone tracks
17 notetracks
serialized SHA-256 371936182a1a71a25d391da7d6a224aabea2d5d0aeae1fdfaed414dbc67b373a
```

The notetracks include exact MP7 magazine-out/magazine-in and cloth events, so the benchmark can later validate animation, attachment visibility/state, and audio-event linkage together rather than as disconnected exports.

## Cross-zone expectation

The player script path and independent retail installation inventories identify `faction_seals_mp.ff` as a real BO2 zone. The current working hypothesis is therefore:

- `faction_seals_mp` — SEAL6 body/viewhands ownership;
- `common_mp` and weapon-related layers — MP7 model/definition/animation dependencies;
- base/common patch layers — shared materials, images, FX, sound and reused model/animation assets as discovered.

This is only a search-order hint. Actual ownership and winning patch precedence must come from retained source hashes and exact asset resolution.

## New exact-target raw probe

`tools/t6_xmodel_target_probe_v1.py`

Given one expanded retail XFile plus the benchmark spec, it:

1. searches only for the exact target identity;
2. requires the name to immediately follow a **248-byte PC32 XModel fixed record**;
3. validates bone/root/surface/LOD metadata;
4. validates every top-level XModel pointer against the zone's declared block sizes;
5. validates active LOD surface spans;
6. hashes the fixed record and fixed+inline-name span;
7. reports packed/reused-name cases unresolved instead of guessing them.

A raw occurrence of the string alone is explicitly insufficient proof.

## Pinned OAT XModel catalog

`tools/t6_oat_xmodel_catalog_v1.py`

Pinned OpenAssetTools emits:

```text
xmodel/<asset-name>.json
model_export/<asset-name>_lodN.<configured extension>
```

The adapter requires the source zone name and retail source SHA-256, then hashes every XModel descriptor and every present LOD payload.

This gives us an important independent classification gate. Pinned OAT classifies a T6 XModel as `viewhands` only when:

```text
IsAnimated(model)
&& HasNulledTrans(model)
&& HasNonNullBoneInfoTrans(model)
```

So `c_usa_mp_seal6_shortsleeve_viewhands` must eventually be structurally classified as `viewhands`; its filename is not enough. The SEAL6 third-person body is expected to classify as `animated`.

## Bundle closure planner

`tools/t6_first_person_bundle_plan_v1.py` joins:

- the benchmark spec;
- one or more direct XModel probe results;
- one or more source-hash-pinned OAT XModel catalogs;
- raw and/or normalized XAnim JSON artifacts.

It keeps separate gates for:

- exact retail model identity;
- body/viewhands structural classification;
- the expected 23-member MP7 animation family;
- required core animation identities;
- normalized XAnim availability;
- source-layer duplication / patch precedence.

It emits `readyForBundleExport=true` only after those prerequisites are satisfied. Material/image, weapon-definition, FX, audio and independent-consumer closure remain later gates in the benchmark spec and cannot be silently treated as solved.

## First run sequence when retained streams are mounted

Example shape only; real paths must point to the project's retained expanded streams and OAT outputs:

```powershell
python tools/t6_xmodel_target_probe_v1.py `
  --stream <faction_seals_mp.expanded> `
  --raw-parser tools/t6_raw_xasset_inventory.py `
  --targets manifests/nonmap/benchmarks/seal6_smg_mp7_v1.json `
  --out work/nonmap/seal6/faction_seals_mp_xmodel_probe.json

python tools/t6_xmodel_target_probe_v1.py `
  --stream <common_mp.expanded> `
  --raw-parser tools/t6_raw_xasset_inventory.py `
  --targets manifests/nonmap/benchmarks/seal6_smg_mp7_v1.json `
  --out work/nonmap/seal6/common_mp_xmodel_probe.json

python tools/t6_oat_xmodel_catalog_v1.py `
  --dump-root <oat-faction-seals-output> `
  --zone-name faction_seals_mp `
  --source-sha256 <exact-retail-or-expanded-source-sha256> `
  --out work/nonmap/seal6/faction_seals_mp_oat_xmodels.json

python tools/t6_first_person_bundle_plan_v1.py `
  --spec manifests/nonmap/benchmarks/seal6_smg_mp7_v1.json `
  --xmodel-probe work/nonmap/seal6/faction_seals_mp_xmodel_probe.json `
  --xmodel-probe work/nonmap/seal6/common_mp_xmodel_probe.json `
  --oat-xmodel-catalog work/nonmap/seal6/faction_seals_mp_oat_xmodels.json `
  --xanim-json <mp7_base_xanim_raw.json> `
  --xanim-json <normalized-mp7-xanim-directory> `
  --out work/nonmap/seal6/bundle_plan_v1.json
```

`tools/t6_xmodel_target_probe_v1.py` accepts both retained raw-parser pointer APIs (`zone_pointer` and `decode_zone_pointer`).

## Next closure work

1. Run the benchmark probes across retained `faction_seals_mp`, `common_mp`, common patch and any owning layers.
2. Retain a source-hash-pinned OAT XModel catalog for the winning model definitions and verify the body=`animated`, hands=`viewhands` classifications.
3. Normalize the complete 23-member retail MP7 XAnim family with the current strongest XAnim decoder.
4. Determine which skeleton owns/binds the weapon viewmodel animation family and prove compatibility against the viewhands + weapon composition.
5. Export SEAL6 body and viewhands through the current skinned XModel pipeline, retaining all skin rows and inverse-bind validation.
6. Close XModel -> Material -> GfxImage dependencies for all six model targets.
7. Resolve MP7 WeaponVariantDef/WeaponDef/attachment dependencies directly from retail data and compare them to the candidate weapon dump without promoting mismatches.
8. Resolve the reload notetrack sound/event identities, muzzle/shell FX and player/NPC sounds through the retail FX/audio assets.
9. Produce one portable benchmark bundle plus lossless sidecars and independently validate it in Blender/another glTF consumer.
10. Generalize the exact same contracts across all player factions/classes, weapons, AI, animals, vehicles and remaining non-map asset types.

Nothing in this checkpoint changes the map/world pipeline.
