# T6 complete weapon + character package scope v1 — 2026-09-08

## Completion rule

A weapon or character is **not complete** merely because its mesh, textures or animations can be exported.  Completion means that every asset-local gameplay and presentation dependency reachable through the exact retail graph is represented with provenance, while runtime-global or shared dependencies remain explicitly referenced instead of being fabricated or falsely re-owned.

## Complete weapon package

Every retail weapon family/variant must close, as applicable:

1. **Identity / ownership**
   - exact WeaponVariantDef + underlying WeaponDef identity
   - physical FastFile provenance for every copy
   - no runtime winner claim unless retail-client precedence is independently proven
2. **Geometry / skeleton / first-person presentation**
   - viewmodel, viewmodel additional, ADS model
   - world model and world-model additional
   - view hands/arms and exact skeleton/bone/tag relations
   - attachment model tags, translations, rotations and additive transforms
   - hide tags and left-hand IK overrides
3. **Animation**
   - complete base viewmodel animation table
   - attachment-specific animation overrides
   - exact XAnim curves once float-space decode is closed
   - exact notifies and notetrack sound mappings
4. **Materials / rendering**
   - every Material/TechniqueSet/image dependency
   - exact streamed texture payload identity
   - exact material-local shader lowering where executable semantics are closed
   - exact selected T6/D3D state metadata
5. **Gameplay definition**
   - the complete source-authored WeaponFullDef field set, not a hand-picked stat subset
   - fire timing and derived RPM only after exact retail `iFireTime` closure
   - full six-point damage + range curve
   - player/min-player/melee/explosive/projectile damage fields
   - ammo, clip, shot count, reload timings
   - ADS timings/FOV and relevant view parameters
   - spread, sway, gun/view kick, recoil/recovery
   - burst/delay, melee, movement, projectile/explosive and special-weapon fields where applicable
6. **FX / tracer / camo**
   - every exact view/world FX dependency
   - tracer/enemy-tracer
   - WeaponCamo and attachment/camo variants
7. **Audio**
   - all direct WeaponDef/WeaponVariantDef/WeaponAttachmentUnique sound aliases
   - all XAnim notify / notetrack aliases
   - all attachment sound overrides
   - every concrete alias joined to the exact physical SABS/SABL entry using the 215-FastFile audio closure
   - exact compressed bank payload offsets/sizes/hashes retained
   - decoded PCM/WAV only after the relevant codec path is independently proven

MP7 is the first canary only.  The exporter/planner must be generic and eventually enumerate the complete retail T6 weapon universe across all 215 FastFiles, including MP, campaign, zombies, equipment, launchers, melee and special weapons.

## Complete character package

Every character package must close:

1. exact character/body/head/XModel identity and physical provenance
2. full skeleton, surfaces, materials, TechniqueSets and exact texture payloads
3. all character animation dependencies reachable from the exact retail character/player graph
4. exact per-animation notifies
5. all character-specific voice, exertion, pain/death, movement/cloth/gear/foley and other audio dependencies that the retail graph proves belong to that character/faction/voice set
6. every concrete audio alias joined to its exact SABS/SABL payload identity
7. shared/global sound resources represented as shared dependencies rather than duplicated or re-owned

SEAL6 LOD0 character-local geometry/material/shader closure remains authoritative at `abb3a2f6de68018f5b78cf380eaaa60cf6865676`; its remaining lighting/probe/fog/HDR inputs are runtime-scene globals and are not character omissions.

## Gameplay-field authority

Pinned OpenAssetTools commit:

`9dca965366541504b71fa8cfb7ac049cb9b717e1`

Exact source table:

`src/ObjCommon/Game/T6/Weapon/WeaponFields.h`

Pinned git blob SHA-1:

`913e81a417d14516fc131ff5cb864ada3fcaf661`

The source table proves `fireTime -> WeaponDef.iFireTime` is `CSPFT_MILLISECONDS`; the pinned InfoString writer reads the internal unsigned integer and divides by 1000 when writing authored seconds.  Therefore, after an exact retail `iFireTime` value is bound, the permitted derived RPM is:

`60000 / iFireTime_ms`

The same field table proves a six-point native damage curve:

`damage[0..5]` paired with `damageRange[0..5]`.

Plain `CSPFT_FLOAT` ranges remain native T6 values until world-unit semantics are independently closed; no inch/meter conversion is promoted from convention.

## Audio authority already available

The current branch includes the 215-FastFile audio closure merged from main.  Its concrete aliases are already joined fail-closed to physical SABS/SABL entries.  Weapon and character packaging must consume that closure instead of rebuilding audio identity from filenames.

## Proof boundary

No package may be marked complete from names, visual resemblance, surface order, attachment proximity, presumed patch priority or a plausible stat table.  Every edge must originate from exact retail pointers/tables, exact native dumps whose ownership is closed, or independently source-closed executable/loader semantics.  Unresolved dependencies stay unresolved and block the corresponding completion claim.
