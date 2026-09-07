# T6 stream coordinate systems correction — 2026-09-06

## Scope

This checkpoint closes a diagnostic mistake made while auditing early Nuketown XAssets and Car01 Material -> TechniqueSet bindings.

## Correction

OpenAssetTools' instrumented source-byte counter and this repository's expanded-FastFile/custom-walker offsets are **different coordinate systems**.

- The OAT counter advances when `ZoneInputStream::Load` consumes serialized source bytes during loader traversal.
- `tools/t6_xmodel_serialized_walker.py` walks the repository's expanded FastFile representation and reports offsets in that expanded representation.
- There is **no proven constant additive base** that converts one coordinate system into the other.

Therefore an OAT source span such as q4 `63 -> 660` must not be translated by adding a guessed base and compared with an expanded-stream XModel walk such as `499456 -> ~515650`.

Those measurements are not contradictory; they describe different representations of the same loader traversal.

## Superseded evidence

GitHub Actions run `34070646979`, job `101587229791`, from `.github/workflows/t6_nuketown_q4_q14_oat_endpoint_audit_v1.yml` intentionally failed after asserting equality between those two coordinate systems. That assertion is invalid. The run is retained as historical evidence of the failed assumption, not evidence of an XModel parser regression.

The workflow's former `OAT_SOURCE_BLOCK_BASE=499393` mapping and its derived absolute OAT endpoints are retired from the proof path.

## Proof rule going forward

Never compare or translate OAT source-consumption positions and expanded-FastFile offsets unless the exact loader transformation between those representations has itself been modeled and proven for the data being compared.

For Material identity and Material -> TechniqueSet binding, prefer native T6 loader resolution over q-index/offset inference. At pinned OpenAssetTools commit `9dca965366541504b71fa8cfb7ac049cb9b717e1`, T6 Material and MaterialTechniqueSet both have native dump/load support, and the Material JSON dumper emits `material.techniqueSet->name` after pointer resolution.

## Car01 continuation boundary

The five visible clean Car01 materials remain:

- `mc/mtl_nt_2020_car_01_glass_out`
- `mc/mtl_nt_2020_car_01_exterior`
- `mc/mtl_nt_2020_car_01_interior`
- `mc/mtl_nt_2020_car_01_tire`
- `mc/mtl_nt_2020_car_01_glass_in`

Their retail Material records and already-proven texture bindings remain valid. The next authoritative step is to dump these five Materials through the pinned native OAT T6 loader, read their resolved `techniqueSet` names directly, then dump those exact TechniqueSets and their technique/pass/shader dependencies. No Blender/PBR approximation is promoted from the retired coordinate mapping.
