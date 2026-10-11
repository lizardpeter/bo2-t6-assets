# Durable T6 Ghidra evidence and fast AI-to-C++ reconstruction

## Why the original pseudocode is not all in Git

The earlier whole-executable exporters wrote each Ghidra function to `unreviewed/<address>.c`, recorded disassembly and reference TSVs, and uploaded compressed shard bundles to **expiring GitHub Actions artifacts**. Final collection jobs committed **summaries and metrics**, not the complete pseudocode for both binaries.

Do not conflate decompilation success with reconstructed/accepted C++:
- Retail `t6mp.exe`, SHA256 `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`: **24,612** completed of **24,617** Ghidra functions.
- Server `CoDMPServer_PC.exe`, SHA256 `f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d`: **27,730** completed of **27,734** Ghidra functions.

## Archive into Git without regenerating successful decompilations

1. Create a **private Git repository** for complete original-executable-derived pseudocode.
2. Set an Actions variable `T6_PRIVATE_CORPUS_REPOSITORY=owner/private-repo` and Actions secret `T6_CORPUS_TOKEN` with Contents read/write to that repository. Do not print the token.
3. Manually dispatch `.github/workflows/t6_durable_reverse_corpus_v1.yml`. The default retail run ID `36988725442` was confirmed on October 10, 2026 to contain eight unexpired complete enriched Ghidra shard artifacts. The server and PDB run IDs may be provided explicitly or discovered from latest successful workflow runs.
4. The workflow downloads and unpacks all eight original retail and all eight server shards. `tools/t6_preserve_ghidra_corpus.py` validates source bodies and unique function identities against the original results, stores deterministic compressed Git-sized shards, and writes a searchable `functions.jsonl` manifest for each binary.
5. The same workflow downloads the existing complete PDB semantics artifact and persists recovered types, global symbols, and existing MAP/exact-byte-match proof evidence alongside the server corpus.
6. It **refuses to push full code to a public repository**. This source tools repository can remain public, while proprietary-derived source lives in the designated private Git repository.

**No complete archive upload is claimed until this workflow succeeds.** If any temporary artifact has expired, rerun only the relevant SHA-pinned exporter to produce a fresh copy; the archiver fails explicitly instead of silently recording partial coverage.

## What the AI stage should do over tens of thousands of functions

**0. Reuse the existing PDB.** The Ghidra/PDB server census already records 58,988 types, 5,937 structs/unions, 21,314 typedefs, 1,720 enums and 27,734 typed functions. Our prior ABI generator emitted 5,927 collision-safe C++ struct-layout views. Include offsets, calling conventions, source object/map associations, globals and PDB signatures in the context of relevant functions. Never assume the server's named function or structure is identical to retail without verified identity evidence.

**1. Build a type/callgraph index without AI.** Deduplicate libraries, thunks, trivial wrappers; resolve function targets and graph strongly connected components; index every reference to globals, type fields and object-file ownership. Prioritize routines with many dependents, high-confidence PDB information, and tractable signatures.

**2. Recover shared types first.** Perform a small number of high-value AI type inference jobs per object or subsystem, using PDB-backed constraints and machine-code reads/writes. Feed verified types back into Ghidra, then refresh affected pseudocode. Propagate knowledge once to all callers instead of paying for independent function rewrites.

**3. Generate compilable C++ in *dependency clusters*, not one AI call per function.** Batch perhaps 16–64 small related functions, fewer for complex ones. Supply only required neighbor functions, prototypes, type definitions, and exact provenance. Have bounded parallel workers output deterministic patches, tests, unresolved symbol lists, and evidence-tagged type hypotheses. Cache jobs by source/type hashes and resume interrupted work.

**4. Keep a compiler in the loop.** Compile modules with x86 32-bit ABI/type-layout checks, preserve exact machine-code semantics where necessary, and feed diagnostics to the owning jobs. A stub may unblock a link test but is never classified as reconstructed.

**5. Verify behavior before accepting.** Differential-test selected routines using original execution traces when possible. Count separately: cataloged, pseudocode exported, typed, C++ emitted, compiling, linkable, and behaviorally verified. Compiler success alone is not equivalence.

A useful first batch is high-confidence PDB-backed server leaf and utility code, followed by shared high-fan-out core subsystems, then retail-only code and gameplay logic. The existing `tools/t6_server_bulk_cpp_candidates_v1.py` and `tools/t6_server_pdb_x86_cpp_views_v1.py` can be reused as part of the deterministic front end.


## Deterministic AI work queue (added to this branch)

Run after recovering the private corpus:

```bash
python3 tools/t6_reconstruction_worklist.py \
  --corpus /path/to/private-corpus/t6/ghidra-12.1.3/server-f67eb68a \
  --output /path/to/private-corpus/server-ai-jobs.jsonl \
  --batch-size 32 \
  --type-revision <SHA256-of-the-frozen-PDB-type-revision>
```

The worklist generator reads the actual archived reference TSVs, validates archive hashes, joins *server* function addresses to the original PDB prototypes and the verified linker MAP object-file ownership, and emits JSONL tasks grouped by source-object/subsystem with shared dependencies. The retail corpus can use the same planner, **without** assigning server PDB names to retail functions from unverified similarity. These work items are a queue, **not yet executed AI jobs or compiled source**. A production model adapter should consume the immutable task IDs with bounded concurrency, append results and compiler failures, and avoid reprocessing identical input/type revisions. Route dependencies and large functions to smaller batches when needed.
