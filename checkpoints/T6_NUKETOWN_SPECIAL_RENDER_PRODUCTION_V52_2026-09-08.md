# T6 Nuketown special-render production v52 checkpoint — 2026-09-08

This checkpoint records the promotion of the exact ordinary-special Material replay contract into the production world-export chain without weakening the existing generated-Material renderer proofs.

## Production position

The pre-existing production chain reaches `t6_oat_world_textured_export_pipeline_v51.py`, whose renderer-neutral replay contract covers the 120 generated `*` Materials. The new v52 layer is complementary: it adds the exact replay contract for the 11 ordinary special Nuketown Materials while preserving all v51 outputs and generated-material replay evidence.

Files:

- `tools/t6_world_special_render_contract_overlay_v1.py`
- `tools/test_t6_world_special_render_contract_overlay_v1.py`
- `tools/t6_oat_world_textured_export_pipeline_v52.py`
- `tools/test_t6_oat_world_textured_export_pipeline_v52.py`
- `.github/workflows/t6_world_special_render_contract_overlay_v1.yml`

Primary implementation commit:

`8d2b065afc9f5be6536fe7ac02d7d1f92ad04653`

Production wiring regression commit:

`4b69f2b43fab231ff46eca7bb6c0bee2cb4ba2cb`

## Special-render contract boundary

The v52 overlay requires the exact sealed Nuketown special-render contract and refuses mismatched SHA/digest/map identity. It joins only by retained `material.extras.T6.sourceMaterial` identity; display-name-only matching is not accepted.

Expected exact population:

- 11 special ordinary Materials total
- 1 raw-normal family Material
- 2 shadowcaster Materials
- raw-normal: 22 lit program variants / 20 unique pixel shaders
- 3 static Material-owned image identities
- 6 runtime texture identities
- 39 distinct runtime constant-variable identities
- exact shadow depth states retained

The overlay writes only `extras.T6` replay metadata. It does not rewrite geometry, PBR preview bindings, images, textures, samplers, or the logical GLB BIN payload.

## Upstream production repair found by clean import

The first clean-checkout v52 regression exposed a real pre-existing production import break:

`tools/t6_generated_final_output_texture_resource_binding_v2.py`

imported `resolve_slot_shader` from resolver v2, but resolver v2 exports `resolve_slot_shaders`. The call was corrected at:

`8664020acc51a88534c71bf32948fb4a329e182a`

This does not widen the proof boundary. The binding still resolves the exact slot-4 TechniqueSet/Technique/pixel-shader chain and checks the exact pixel-shader SHA.

The next clean run exposed only missing test-environment production image dependencies. The v52 workflow now mirrors the repository's existing production image setup by installing Pillow + NumPy. Dependency setup commit:

`1070671d808f74952a996c0e93fa68b360374473`

Workflow trigger/dependency coverage was then updated at:

`564f442c115038ebe04d21f77733e661acd23ad2`

## Green clean-checkout proof

GitHub Actions:

- run: `34275122394`
- job: `102226134751`
- tested head: `1070671d808f74952a996c0e93fa68b360374473`

The clean hosted runner passed all production-import and regression steps, including:

- `PASS t6_world_special_render_contract_overlay_v1 regression`
- `PASS t6_oat_world_textured_export_pipeline_v52 production wiring regression`

The v52 regression additionally carries a synthetic v51 generated-final-output replay sidecar through unchanged, specifically guarding against ordinary-special integration breaking the generated-material path.

## Promotion boundary

What is proven now:

- v52 production code is importable from a clean checkout;
- exact special-contract seal verification is wired;
- all 11 expected exact ordinary-special identities are required by the production wrapper;
- v51 generated replay evidence is preserved;
- v52 logical BIN preservation is enforced;
- regressions are green on a clean hosted runner.

What is **not** promoted by this checkpoint:

- this is not yet a complete real-retail Nuketown v52 export execution;
- the green wiring fixture is synthetic at the v51 handoff boundary;
- no claim is made that every generated-material replay blocker is closed;
- no portable PBR approximation is promoted to native shader equivalence.

The next promotion gate is a real retained-Nuketown production v52 run using the exact retail world sidecars/OAT/material/image/lightmap/reflection inputs, with all 11 special Materials matched and the v51 logical BIN payload independently shown unchanged.
