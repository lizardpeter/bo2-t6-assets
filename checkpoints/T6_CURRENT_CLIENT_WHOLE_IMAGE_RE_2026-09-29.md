# T6 current-client whole-image RE checkpoint — 2026-09-29

Exact current client:
- SHA-256: `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`
- image base: `0x00400000`
- entrypoint: `0x00A7FD5C`

## Verified completed
- Whole-image mechanical inventory: 26,778 function-entry occurrences, 95,522 strings, 140,674 direct calls, 390 imports, 9 sections.
- All 26,778 mechanical function entries were loaded into `uregraph` and checkpointed.
- Ghidra catalog: 24,617 recognized functions.
- All 24,617 Ghidra catalog rows were projected to current-client FunctionOccurrence nodes with exact instruction-byte SHA-256 and generated body metadata.
- Whole-catalog generated C attempts: 24,609 completed in the first passes; 8 initially failed/timed out.
- Strict current-client <-> server PDB exact-hash join was regenerated with two-sided uniqueness:
  - 321 current-client functions have at least one exact server/PDB full-function hash hit.
  - 269 exact hash match rows are accepted one-to-one machine-body identity witnesses.
  - 52 current-client functions remain ambiguous across 41 duplicate hashes.
  - 580 match rows remain candidate-only.
  - proof: `proof/current_client/pdb_exact_hash_join_v1_strict/`

## Live graph transport state
- Function-entry ingestion complete and checkpointed.
- Imports/sections loaded.
- String ingestion had reached at least 6,000 verified string-literal occurrences before later concurrent progress.
- Large MCP writes remain unsafe: client timeout can leave the graph worker occupied long after the caller returns.
- The strict PDB graph-ready corpus exists in four 250-row-or-smaller chunks plus corpus metadata, but must not be claimed loaded until verified live.
- Do not retry the old all-at-once dynamic hash join. Use the precomputed strict proof/cypher corpus.

## Current active work
- `T6 Ghidra eight-failure retry v2` retries the 8 initial decompiler exceptions with a 120-second budget.
- The 269 strict exact-byte anchors are the next seed set for cross-build propagation using call topology, strings/constants/imports, CFG shape, source/object context, and already-proven neighbors.
- Propagated matches are candidate evidence unless independently corroborated; never merge by address/name alone.

## Proof boundary
Ghidra output is generated/unreviewed evidence, not reconstructed source. Exact complete function-byte equality is a strong implementation-identity witness but does not automatically transfer every server-side type/global/source/ABI property to the current client.
