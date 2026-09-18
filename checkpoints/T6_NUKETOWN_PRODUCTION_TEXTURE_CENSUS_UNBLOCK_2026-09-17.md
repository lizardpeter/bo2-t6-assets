# T6 Nuketown production texture census unblock — 2026-09-17

The exact GfxWorld v3 retail ownership run is green, but promotion run `35297430330` / job `105452754530` failed only at its final push. The job had already revalidated both v3 catalogs and produced the intended workflow edit. GitHub rejected the push because the Actions token lacked `workflows` permission: `refusing to allow a GitHub App to create or update workflow ... without workflows permission`.

No reversal evidence failed. The validated v3 identities remain authoritative: lightmap catalog SHA-256 `b3a4387b43eb0404b5080effd376bb8c1e018299bee98b415a525706eee7fdeb`, reflection catalog SHA-256 `5f0951204d7b7f3976787e80c1cf0aa33f9a33c1f0a80dca86dcd8f674d0f947`, with an exact 27-identity GfxWorld union.

To avoid weakening the gate or requiring a workflow-file mutation, this commit adds V2-named **identity-only compatibility projections** at the two paths already watched and consumed by the production census. They contain only the exact fields the census parser consumes: contiguous indices plus primary/secondary lightmap identities and reflection-image identities. Their `source` blocks bind them to the SHA-verified v3 retail catalogs. They do not invent or copy unneeded origin, SH, probe-volume, sampler, render-state, or renderer semantics.

This push should therefore trigger `.github/workflows/t6_nuketown_production_texture_dependency_census_v1.yml` without editing that workflow. The census remains responsible for rebuilding the 327-Material manifest and exact 81-image DDS bridge and for computing the identity-level set union. Do not report `423 + 27` as the denominator before that census completes because Material/GfxWorld overlap must be measured, not assumed.

Next gate: inspect the production-census run triggered by these two watched paths. If green, persist its full V2 census and promote the exact deduplicated denominator/coverage. If it fails, recover the exact failing step and preserve the same fail-closed boundary.
