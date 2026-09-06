# T6 final-output cbuffer/value checkpoint — production v42

Date: 2026-09-05

This checkpoint is the durable continuation point for the generated-world final-output reversal branch. It supersedes older statements that final-output constant-buffer inputs are only opaque `cbN[R].component` symbols.

## Production state

Current production chain has advanced through `t6_oat_world_textured_export_pipeline_v42.py`.

Visual GLB/glTF bytes remain inherited unchanged across v24-v42 forensic promotions unless an earlier visual-production stage explicitly changed them. v39-v42 are proof/sidecar-only.

## v39 — exact cbuffer identities

`tools/t6_generated_final_output_cbuffer_signature_v1.py`

For every cbuffer symbol actually used by the exact slot-4 final-output DAG:

`cbN[R].component -> byte offset -> exact same-CSO RDEF cbuffer -> exact RDEF variable byte range -> relative scalar index`

For every owning TechniqueSet, exact `.tech` right-hand assignments are also retained. Source prefix classification is syntax-only:

- `material.*`
- `code.*`
- `other`
- unassigned

Names/source classes are identities, not physical semantics.

Production: `tools/t6_oat_world_textured_export_pipeline_v39.py`
Regression: `tools/test_t6_oat_world_textured_export_pipeline_v39.py`

## v40 — cbuffer-enriched unknown-term census

`tools/t6_generated_final_output_unclassified_term_census_v3.py`

Preserves the earlier v38/v2 channel-agnostic unknown-term census unchanged and adds a second structural grouping containing exact cbuffer identities for each unknown term and immediate child.

This permits two terms with identical arithmetic/resource topology to split if they use different exact RDEF variables/.tech sources.

Production: `tools/t6_oat_world_textured_export_pipeline_v40.py`
Regression: `tools/test_t6_oat_world_textured_export_pipeline_v40.py`

## v41 — exact per-material MaterialConstantDef values

Direct retained-world source:

`tools/t6_retail_world_material_constants_v1.py`

Each generated Material's serialized `MaterialConstantDef` table is read directly from the expanded retail GfxWorld:

- uint32 name hash
- exact stored 12-byte name fragment
- exact float4 literal
- serialized 32-byte record SHA-256
- material archive SHA/start/index

Final-output value join:

`tools/t6_generated_final_output_material_cbuffer_values_v1.py`
`tools/t6_generated_final_output_material_cbuffer_values_v2.py`

For each exact `.tech` assignment `shaderVariable = material.foo`:

`foo -> T6 zero-seed R_HashString -> exactly one MaterialConstantDef hash -> matching 12-byte fragment -> exact float4 -> RDEF relative scalar component`

The join is material-specific. Shared TechniqueSet/CSO identity never implies shared values.

`code.*`, `other`, and unassigned sources remain unresolved by this stage.

v2 corrects variation accounting: a shader varies only when multiple material owners have distinct complete resolved-value signatures.

Production: `tools/t6_oat_world_textured_export_pipeline_v41.py`
Regression: `tools/test_t6_oat_world_textured_export_pipeline_v41.py`

## v42 — unknown-term exact material-value overlay

`tools/t6_generated_final_output_unclassified_term_material_values_v1.py`

For every still-unclassified final-RGB term cbuffer dependency, records the source/value state for every material owner of that exact shader.

Material sources retain:

- exact scalar float32 value
- exact scalar float32 bits
- exact float4 literal
- exact float4 component bits
- MaterialConstantDef hash/fragment/serialized SHA
- material archive SHA

Non-material sources remain explicit unresolved rows.

The overlay reports exact per-owner variation without assigning physical meaning from numeric patterns.

Production: `tools/t6_oat_world_textured_export_pipeline_v42.py`
Regression: `tools/test_t6_oat_world_textured_export_pipeline_v42.py`

## Important proof boundaries

Do not regress these rules:

1. Never infer a material constant from its 12-byte fragment alone. Full reflected name -> T6 hash -> unique hash row + fragment agreement is mandatory.
2. Never share material constant values merely because materials share a TechniqueSet or pixel shader.
3. Never assign physical meaning from RDEF/.tech names alone.
4. `code.*` is not a static material value and remains unresolved until its engine code-constant source is separately proved.
5. Unknown-term numeric variation is evidence only; it does not promote a final-lighting formula.
6. Final visual GLB bytes remain unchanged by v39-v42.

## Next target

Resolve `code.*` final-output cbuffer sources to their exact T6 engine code-constant identities/enums/slots using pinned source/tooling evidence. Preserve dynamic/runtime-dependent values as unresolved unless their exact source/value construction is independently closed.
