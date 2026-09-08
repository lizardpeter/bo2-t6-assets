# T6 Nuketown retail world source sidecars v3 — 2026-09-08

The missing historical GfxWorld sidecar producer is no longer a production blocker. The current audited base-world exporter can now be driven from exact retail Nuketown bytes through an independently proven MaterialMemory ownership boundary, with no top-level Material XAsset assumption and no nearby byte-pattern candidate selection.

## Authoritative input

- retail `mp_nuketown_2020.ff` SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- exact expanded bytes: **154,653,476**
- exact expanded SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`
- MaterialMemory ownership proof JSON SHA-256: `6b5786897436f9c291e38aacab75ba73baef64bcc86e60d542982754e956be7a`

## v3 ownership gate

`tools/t6_nuketown_world_source_sidecars_v3.py` requires the authoritative ownership proof as an explicit input and then independently reparses the retail source. It refuses output unless all **327** slot bindings agree on:

- GfxSurface packed alias value;
- VIRTUAL block and offset;
- physical MaterialMemory record start;
- Material identity;
- TechniqueSet identity;
- worldVertFormat.

Exact MaterialMemory boundary retained:

- physical: **84,463,050 .. 84,465,666**
- VIRTUAL block: **5**
- virtual: **71,642,512 .. 71,645,128**
- slot count: **327**
- slot stride: **8 bytes**

No local candidate scan is used in v3.

## Exact regenerated population

- GfxSurfaces: **5,614**
- Materials: **327**
- MaterialMemory ownership slot agreements: **327 / 327**
- referenced TechniqueSets: **59**
- vertex groups: **340**
- mixed-format groups: **0**
- unresolved surface Materials: **0**

Material worldVertFormat census:

- 0: **207**
- 1: **95**
- 2: **7**
- 3: **17**
- 6: **1**

Vertex-group worldVertFormat census:

- 0: **220**
- 1: **95**
- 2: **7**
- 3: **17**
- 6: **1**

Lightmap-index census remains exact:

- 0: **4,779**
- 1: **750**
- no-lightmap sentinel 31: **85**

## Current strict vertex audit

The v3 compatibility projection was immediately fed back through `tools/t6_world_vertex_audit_v2.py`:

- surfaces: **5,614**
- groups: **340**
- bad groups: **0**
- vd0 bytes: **5,285,088**
- vd1 bytes: **33,764**
- observed formats: **0 / 1 / 2 / 3 / 6** with the exact 220 / 95 / 7 / 17 / 1 group census.

Pass: `GREEN V3 NUKETOWN WORLD VERTEX AUDIT`.

## Base-world deterministic export

The exact v3 sidecars were then consumed by `tools/t6_world_export_pipeline_v1.py` with no old GLB input:

- all surface Materials resolved: **true**
- unresolved Materials: **0**
- vertex audit bad groups: **0**
- GLB regeneration byte-identical: **true**
- groups: **340**
- primitives: **5,614**
- Materials: **327**
- serialized vertices: **146,764**
- triangles: **100,280**
- base world export manifest SHA-256: `1772d9888558dd3b5d75bb0eddc309b6a2920ba36ca7125d36c6947d3b1d94ca`

Pass: `GREEN BASE WORLD EXPORT FROM V3 RETAIL SIDECARS`.

## Hosted execution

- adapter: `tools/t6_nuketown_world_source_sidecars_v3.py`
- adapter commit: `10b7c5be7aba08ad3ade74c4d47877c782709bd4`
- workflow: `.github/workflows/t6_nuketown_world_source_sidecars_v3.yml`
- workflow commit: `314da533370d7281773f245d40c3d99bc2976752`
- run: **34278658949**
- job: **102237823336**
- conclusion: **success**
- sidecar manifest: **4,268 bytes**
- sidecar manifest SHA-256: `dfa000d7dc7bb75a271b266a74d50f1d42e87d0250c8410aba926f00d393ea59`
- artifact ID: **10076723807**
- artifact bytes: **154,172,373**
- artifact ZIP SHA-256: `0111accf456b96f421ac9cf2fd70f86c052291a3aadcd70f07141c66587ae938`

Machine-readable hosted proof: `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_WORLD_SOURCE_SIDECARS_V3_HOSTED_PROOF.json`.

## Promotion boundary

This closes raw retail Nuketown → source-derived GfxWorld sidecars → strict current vertex audit → deterministic base-world GLB generation.

It does **not** promote the resulting world-only GLB as a user-facing full-map successor. The retained v25 full-map release floor still applies. The next gate is to feed these v3 retail sidecars into the complete v51/v52 texture/lightmap/reflection/generated-material production stack, require v51/v52 BIN identity where v52 is metadata-only, and retain the two generated-material sampler ambiguities as blockers until separately closed.
