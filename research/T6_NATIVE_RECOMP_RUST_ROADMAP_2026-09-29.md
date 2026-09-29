# T6 native recompilation and Rust rewrite roadmap

**Date:** 2026-09-29
**Scope:** whole-program T6 executable recovery, native recompilation, and later Rust rewrite

This repository remains the T6 reverse-engineering / proof oracle. The live shared semantic state is the `uregraph` FalkorDB graph.

## Agent entry points

Before doing executable reverse engineering, read these live graph nodes:

- `urn:ure:t6:representation:project-roadmap:native-recomp-rust-v1` — master project directive.
- `urn:ure:t6:coverage:native-recomp-readiness-20260929-v1` — measured readiness snapshot.
- `urn:ure:ontology:extension-policy:v1`
- `urn:ure:ontology:partition-policy:v1`
- `urn:ure:ontology:server-graph-policy:v1`

The graph, not chat history, is the shared multi-agent project state.

## Three layers that must remain distinct

1. **Retail evidence** — exact SHA-pinned binaries/assets, disassembly, runtime observations, server MAP/PDB, strings, tables, calls, xrefs, and other immutable observations.
2. **Recovered native** — reviewed C/C++ reconstructions, recovered signatures/types/globals/ABI/source organization, compilation results, and differential validation. Derived source is never silently promoted into retail fact.
3. **Modern Rust** — a clean rewrite validated subsystem-by-subsystem against the retail/native oracle. Enhancements are explicit divergences after parity is established.

## Exact build identities

- Current client `games/t6mp.exe`: `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`
- Gold retail MP artifact `t6mp.exe`: `7c6aa5e703ea096a981e6fb8962d2d13a1e80f80d3498e4836e8c8466322810d`
- Related 2013-03-11 dedicated MP server EXE: `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`
- Server MAP: `34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf`
- Server PDB: `7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc`

Never infer that server symbols/types/source are identical to a client occurrence merely because the names are plausible. Cross-build transfers require explicit evidence.

## Existing executable-recovery machinery

Do not duplicate these paths:

- `tools/t6_current_client_whole_image_mechanical_inventory_v1.py` — exact whole-image entry/call/string/import inventory.
- `tools/t6_ghidra_catalog_to_uregraph_v1.py` — Ghidra catalog/decompile evidence projection.
- `tools/select_t6_current_client_low_hanging_v1.py` — throughput-oriented decompile selection.
- `tools/join_t6_current_client_pdb_exact_hashes_v1.py` — exact instruction-byte hash bridge from current client into server/PDB variants.
- `tools/join_t6_current_client_pdb_exact_hashes_v2.py` — graph-ready successor; unique exact hashes become evidence-backed accepted correspondence witnesses, while duplicate hashes remain candidate-only.
- `tools/test_join_t6_current_client_pdb_exact_hashes_v2.py` — regression locking the unique-versus-ambiguous hash policy.
- `proof/current_client/ghidra_low_hanging_v1/uregraph/` — graph-ready catalog chunks.
- `proof/current_client/ghidra_low_hanging_v3/` — later sharded Ghidra evidence.

Generated Ghidra C is evidence, not accepted reconstructed source.

## Immediate frontier

The highest-leverage task is to project the existing current-client Ghidra catalog into `uregraph`, then expand high-confidence server-PDB → current-client identity using exact byte equality first and progressively stronger structural evidence (CFG/call topology/strings/constants/imports/globals/object-file context) for changed functions.

This runs in parallel with client-only reverse engineering for renderer, UI/input/platform/presentation and other code without a server analogue.

## Recompile completion standard

A named function is not automatically recompile-ready. The applicable recovered unit ultimately needs enough evidence for exact occurrence/boundary, signature/calling convention, types, globals/side effects, calls/dispatch, structures/offsets, constants/tables, source/object ownership where recoverable, external ABI, reviewed native representation, successful compilation, and behavioral/differential validation.

## Graph projection caveat

The 2026-09-29 projection audit found migration/projection debt: imported semantic knowledge and materialized graph relationships are not always identical. Missing `HAS_VARIANT` or scope edges are not by themselves proof that semantic knowledge is absent. Inspect IDs/properties/evidence before recreating concepts.

## Rust policy

The Rust implementation should preserve retail behavior where compatibility matters, but it is not required to mechanically preserve obsolete implementation choices. After parity is established, improvements may include safer ownership, modern job/thread systems, low-latency input/render/audio, high-refresh support, modern rendering, larger limits, improved networking abstractions, portability, and tooling/mod improvements. Every intentional divergence should be recorded and validated.
