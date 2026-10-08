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

## Generated C evidence retention and staging (corrected)

The early v1 and v2 Ghidra bundles were stored as split `bundle.tar.zst.part-000` files rather than as monolithic `bundle.tar.zst`. The source-availability audit now handles **both formats**, validates the compressed SHA-256 receipts, checks exact per-function instruction-byte hashes, and reconstructs split archive streams before extracting pseudocode.

All **269/269 accepted unique client↔server PDB exact-byte matches** are indexed in the **10 retained archive groups** (8 monolithic plus 2 split). The first version's 57/269 count was an archive-discovery error, not a missing-source conclusion.

`tools/t6_native_decompile_availability_v1.py` stages only the corresponding generated Ghidra `unreviewed/<VA>.c` bodies and writes per-function provenance + SHA-256 into a separate CI artifact. This is *not* an automatic promotion to compilable or retail-equivalent C++.

```sh
python3 tools/test_t6_native_decompile_availability_v1.py
python3 tools/t6_native_decompile_availability_v1.py --output build/t6-decompile-availability.json --stage-dir build/t6-native-ghidra-staging
```


## First named-function source wave

The exact-hash PDB archive audit produced readable Ghidra C for all 269 matching functions. Nine small functions have now been manually translated into a third C++26 translation unit: Actor_ClearMoveHistory, cCurve::Reinit, Actor_ClearScriptOrient, Actor_ClearPileUp, XAnimClientNotifyList initialization, mover previous-origin selection, GJK OBB type, session QoS payload-size, and hunk default-buffer offset. Their exact client addresses, the source Ghidra SHA-256s, unique PDB instruction-byte witness hashes, and explicit non-retail-validated states are recorded in `manifest.json`.

These nine are **host-callable semantic candidates**. Their C wrappers are *not* proof of correct MSVC `__fastcall`/member-function ABI or source-level names in the original binary. The new test validates field writes, guard bytes, both orientation branches, pointer offsets, and constant returns. Future production admission requires recovered true layouts/signatures, linkage and retail differential tests.


## ABI-focused x86 recovery wave

The T6 current-client PDB archive also contains the byte-identical SHA-1 initialisation function in db_auth_sha1.obj at 0x00622F10. We now compile its seven 32-bit state writes in a standalone C++26 source file and test all IV values, both zero counters, and unchanged guard bytes. This is candidate behavioral reconstruction, not SHA-1 subsystem completeness.

The **separate** t6_native_msvc_pdb_abi Win32/MSVC library exposes the server-PDB symbol names for **five previously recovered functions**: Actor_ClearMoveHistory, Actor_ClearScriptOrient, Actor_ClearPileUp, Session_GetQosPayloadBufferSize, and offsetOfBufInHunkUserDefault. The first three use the __fastcall signature encoded by their PDB names; the latter two use __cdecl. CI checks COFF link-member decorations with MSVC dumpbin and links a Win32 calling-convention smoke test.

**Important:** These are *ABI bridges*, not five additional independently recovered game functions. Matching mangled symbols plus smoke tests does **not** prove exact retail object layouts, prologue, instruction bytes, or full gameplay behavior. Full executable integration remains open.

## Native T6 glass-client allocator constructor

The unique exact-byte match at `0x005F2550` is identified by its 2013 server PDB as `StaticFixedSizeAllocator<TempPackedOutline,350>::StaticFixedSizeAllocator()` in `glass_client.obj`. Its existing generated Ghidra body has now been promoted into a **Windows x86-only structural reconstruction** with the actual MSVC C++ constructor name, a 28-byte header, 350 entries of 96 bytes, linked free-list pointers, and a per-allocation cookie computed from the object address. The test traverses *all 350 nodes* and verifies their forward/backward pointers, sentinel endpoints, and unchanged payload bytes. A separate COFF test requires the original PDB-decorated constructor name. We do not yet know the allocation/free APIs or whether the constructor is fully instruction/behavior-equivalent under retail conditions. This is the **fifteenth** candidate source function; the five ABI bridges are not counted as additional game code.

## Direct-call source reconstruction frontier

The `tools/t6_native_callgraph_frontier_v1.py` audit decompresses the existing exact-current-client Ghidra callgraph, validates its SHA-256 receipt and 79,161 expected unique edges, and produces full incoming/outgoing **direct** callsite inventories for every presently admitted native source function. It joins *only* unique cross-build exact-byte PDB identities for labels, and preserves unrecognized callers by exact address. This report provides the next targeted source-recovery frontier (particularly the new glass allocator). The report is staged as a separate CI artifact; it does not claim that virtual, pointer-table, or indirect call references are covered.
