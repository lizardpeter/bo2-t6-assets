# T6 progress checkpoint — 2026-09-04 corpus recovery and map-export example

This checkpoint exists so the September 4 retail-world recovery, reflection-normal boundary, and concrete Nuketown export state cannot be lost or reconstructed from chat history.

## 1. Canonical five-world retail corpus is locally reproducible

The five raw retail FastFiles used by the retained world/reflection proof corpus were recovered from the archived BO2 FastFile collection and independently expanded. The generated expanded streams match the repository's pre-existing SHA-256 guards exactly.

Machine-readable source/expanded hashes and sizes are retained in:

`manifests/corpus/T6_RETAIL_FIVE_WORLD_CORPUS_RECOVERY_V1.json`

The reproduced expansion path is the T6 four-stream encrypted XFile path:

- four interleaved streams;
- Salsa20 decryption;
- per-stream evolving SHA-1/XOR IV schedule;
- raw-DEFLATE decompression after decryption;
- fail closed unless the final expanded SHA-256 exactly matches the existing pinned world hash.

Nuketown additionally reproduces the retained audit exactly:

- raw bytes: `38,472,064`
- raw SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- record count: `4,730`
- stream counts: `1183 / 1183 / 1182 / 1182`
- expanded bytes: `154,653,476`
- expanded SHA-256: `7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505`

The other four expanded outputs also match their original guards byte-for-byte:

| Map | Expanded bytes | Expanded SHA-256 |
| --- | ---: | --- |
| `mp_raid` | 156,092,603 | `d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8` |
| `mp_hijacked` | 141,043,798 | `8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b` |
| `zm_prison` | 344,067,743 | `e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487` |
| `zm_tomb` | 359,627,377 | `4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219` |

This removes the prior execution blocker: downstream retained-byte verifiers can again run against the exact original corpus rather than relying on old manifests alone.

## 2. Reflection-normal closure boundary remains fail-closed

The measured physical-semantic closure remains:

- `5,823 / 5,888` reflection fetches closed;
- `65 / 5,888` unresolved;
- `98.89605978260869%` closed.

Residual families:

- 21 × `TEXCOORD2 <-> TEXCOORD1`;
- 20 × `TEXCOORD3 <-> TEXCOORD1`;
- 24 × `TEXCOORD2 <-> TEXCOORD0` named Tomb sphere-electric bank.

The earlier 24-fetch shifted tangent-basis `TEMP_OP50 <-> TEXCOORD0` population is distinct and is already included in the 5,808 pre-TEMP15 baseline. It must never be counted again as the sphere-electric 24.

The independently reproduced 15 mixed-writer TEMP surface normals remain part of the measured 5,823 boundary. Their durable verifier/regression preserve the corrected logical-component handling, including the single `yzw` storage case whose logical Z is physical storage W.

## 3. Real-corpus sphere-electric owner probe exposed a calibration assumption

Running the packed-PS ownership machinery against the recovered pinned corpus confirms:

- all five broad TechniqueSet scans reproduce their expected pass populations;
- exactly 76 structural packed-PS anchors are present;
- all 24 named `pimp_shader_sw4_3d_zm_sphere_elec_*` direct pixel-shader objects are physically present in Tomb;
- Tomb sphere packed-PS pointers live in block 5;
- 82 unique Tomb packed-PS pointer identities are present in the inspected population.

The exploratory owner probe's old hardcoded `EXPECTED_TOMB_DIRECT_CONTROLS = 10` assumption does **not** hold under its actual direct-object scanner on the pinned Tomb bytes: only 7 qualifying exact structural/direct controls are recovered.

This is a verifier-assumption failure, not a corpus mismatch. Do not weaken it to `7` and call the bank closed. The next step is piecewise/local serializer calibration: calibrate pointer/object differential behavior within local serialization regions, then require a uniquely bounded 24-member sphere-electric pointer bank before running the paired-VS TC2/TC0 physical closure gate.

Until that passes, the sphere-electric 24 remain uncounted.

## 4. Concrete Nuketown map export example retained

A real standard glTF/GLB scene export is archived as:

`mp_nuketown_2020_PLAYABLE_CORE_PLUS_ALL_STATIC_v6.glb`

Retained identity:

- bytes: `33,745,604`
- SHA-256: `1e97fb62f148036a84abf781a29bbc723eef9b686fcc1ef6cbfcd351c01d0066`

The corresponding static-assembly proof records:

- playable core plus `1,943` static instances;
- `297` unique static XModels used by that playable assembly;
- `0` unresolved static instances;
- `1,945` nodes;
- `298` mesh definitions;
- `1,944` mesh instances;
- `639` material identities;
- `5,648` rendered primitives;
- `1,006,478` rendered triangles including instances;
- `0` structural validation errors;
- bounds approximately `143.14 m x 24.77 m x 128.09 m`.

This is the preferred current human-viewable example because it contains the playable world core and all static placements relevant to the playable assembly without the enormous distant vista/background span of the archival-all-static scene.

A larger archival scene is also retained:

`mp_nuketown_2020_FULL_ALL_STATIC_ARCHIVE_v6.glb`

with 2,992 static placement instances and the far vista/background included.

### Important proof boundary for the v6 example

The v6 static assembly proves geometry/placement assembly and structural validity. It must **not** be presented as final retail renderer parity. The retained proof explicitly leaves materials/textures/lightmaps and dynamic/animated map systems outside that v6 completion claim.

The repository's newer world pipeline (`tools/t6_oat_world_textured_export_pipeline_v4.py`) is the stronger production architecture for exact material dependency preservation, DDS staging, lightmap dependency archival and future T6-aware shader reconstruction. The v6 scene is therefore a concrete visual/export milestone, not the final total-accuracy exporter.

## 5. Durability policy from this checkpoint forward

For every meaningful discovery or promotion:

1. retain exact source hashes/byte counts;
2. add or update a deterministic verifier;
3. preserve machine-readable result manifests/digests;
4. add synthetic/negative regression coverage where useful;
5. record corrected assumptions rather than rewriting history;
6. keep mathematical closure separate from physical producer/ownership closure;
7. never count a family in global closure until its fail-closed verifier passes on the pinned retail corpus;
8. retain example exports by exact SHA-256 and a proof boundary describing what they do and do not prove.

This checkpoint intentionally documents the state even where execution is still incomplete, so a later session can resume from exact evidence rather than conversational memory.
