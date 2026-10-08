# T6 native recompilation lane (C++26)

This is **not** a replacement for the universal Rust engine or renderer. It is a separate, compilation-driven recovery lane for original Black Ops II / T6 runtime behavior, using exact-build executable evidence from `bo2-t6-assets` and `uregraph`.

## First runnable milestone

`CMakeLists.txt` compiles the previously recovered, source-addressed `current_client/simd_candidates_v1.cpp` leaf candidates into a static library and tests their 16x16 predictions/stride boundaries. A second source file reconstructs two buffer-state functions at 0x009A7D00 and 0x009A7D60 from preserved graph evidence; a **test-only** fake for their unresolved 0x00A72BF0 copy dependency permits checking state changes and short/refill/empty paths. This is a multi-file native library and multi-executable link, **not** an integrated game-runtime link. The source already existed in this repository; this lane turns it into an independently buildable target with a named test. Passing the test **does not** prove binary equivalence or a working game. It does not link any BO2 subsystem or produce a BO2 executable.

From repository root, using CMake 3.31+ and a compiler with a C++26 switch:

```sh
cmake -S reconstruction/native -B build/t6-native -DCMAKE_BUILD_TYPE=Debug
cmake --build build/t6-native --parallel
ctest --test-dir build/t6-native --output-on-failure
python3 tools/t6_native_manifest_audit_v1.py
```

On Windows use an up-to-date Visual Studio/MSVC toolchain and select x86 as needed for ABI validation. Host tests here are platform-neutral behavior checks; **retail T6 is x86/MSVC and ABI parity still requires Windows x86-specific builds and differential evidence**.

## Source admission rules

1. Ghidra output remains generated evidence, not native source automatically admitted to the build. No mass `glob()` of pseudocode.
2. Every candidate has an exact build SHA, original entry address, source path, admission state, and separate compile / synthetic-test / retail-validation fields in `manifest.json`.
3. `compiled` means the declared leaf translation unit compiled; it is not equivalent to an integrated whole-engine link.
4. Only independently proved retail behavior may be marked `retail-validated`, and that requires a retained evidence ID.
5. Matching PDB/server symbols are carried across to the current client only when the correspondence evidence is accepted, not because the name or address looks similar.
6. Maintain separate counts for cataloged functions, Ghidra-decompiled functions, admitted C++ functions, linked engine functions, and behaviorally validated functions.

## Next build milestones

- **M1:** Restore high-confidence server-PDB units, types and object boundaries and compile them individually with the original x86/MSVC assumptions.
- **M2:** Create a native program shell with explicit platform/import boundaries; make the first multi-unit link. No pretend stubs silently claiming game features.
- **M3:** Recover initialization/loading/network/gameplay call chains and test against retail.
- **M4:** Build and run a playable native T6 subsystem, followed by broader MP/Zombies/SP coverage.

The parallel universal Rust renderer and importers remain separate consumers of recovered knowledge. The eventual Rust rewrite is validated against retail/native execution, not mistaken for a recompilation.

## Multi-unit checkpoint (2026-10-07)

- Source 1: `reconstruction/current_client/simd_candidates_v1.cpp` — two predictor candidate functions.
- Source 2: `reconstruction/native/current_client/stream_buffer_candidates_v1.cpp` — two recovered state-machine candidates with the exact retail call address `0x00A72BF0` retained as an **unresolved production dependency**.
- `t6_native_stream_tests` supplies that missing dependency with a synthetic virtual-source-memory adapter. This is test scaffolding, not recovered BO2 gameplay or a production copy-helper implementation.
- CI compiles/links and tests on GCC C++26/Linux, and separately on **MSVC x86/Windows**. Passing cannot establish parity with retail bytes, calling conventions or actual engine initialization.
- Recovery provenance for the two newly compiled candidates is stored as native graph `source:c` representations and listed explicitly in `manifest.json`. They remain structural candidates until differential retail tests.

This does **not** satisfy milestone M2 (real BO2 engine shell); it provides the earliest verifiable multi-unit link and exposes what still needs actual reconstruction.

## Next-source inventory: exact-byte PDB matches

`tools/t6_native_pdb_queue_v1.py` deterministically produces a separate **symbol-identity queue** from `proof/current_client/pdb_exact_hash_join_v1_strict/join.json`, rejecting all cross-build matches with ambiguous instruction-byte hashes. The pinned V1 proof contains **269 unique exact-byte correspondences** and **580 ambiguous match rows (excluded)**. Of the accepted entries, **15 have unprefixed object-file identities** (not automatically proof of first-party game source); the other 254 carry library or other object categories. None is claimed to be a rebuilt source unit simply because a symbol matches. The queue prioritizes larger unprefixed-object candidates for manual type/body recovery while preventing generated pseudocode from being auto-linked.

```sh
python3 tools/test_t6_native_pdb_queue_v1.py
python3 tools/t6_native_pdb_queue_v1.py --output build/t6-native-pdb-queue.json
```

The Windows GitHub Actions runner uses the Visual Studio 2026 generator (`Visual Studio 18 2026 -A Win32`), rather than assuming a VS 2022 instance exists on `windows-2025`.

### C++26 toolchain selection

Linux/GCC 14 is tested with the explicit C++26 dialect. Windows MSVC 19.51 (VS 2026, x86) uses `/std:c++latest` because the current MSVC/CMake pairing does not expose a named `CXX26` feature; CMake therefore uses its recognized C++23 baseline only for project generation, while the actual MSVC compile uses the explicit latest-mode switch. This is not a claim that every final C++26 proposal is implemented by MSVC.
