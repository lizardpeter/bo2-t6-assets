# T6 Nuketown special unlit/emissive full-output symbolic closure v1 — 2026-09-08

## Result

The exact `mp_nuketown_2020` non-lightmapped special pixel-shader tail is now arithmetic/dataflow closed rather than excluded by the earlier lightmap-dependent symbolic filter.

The eleven exact `unlit` / `emissive` Technique groups selected by the native OAT census reduce to five unique pixel-shader payloads. All five compile to complete `o0.xyzw` DAGs with strict fail-closed parsing:

- unique pixel shaders: **5 / 5**
- complete output components: **20 / 20**
- total symbolic nodes: **179**
- exact texture-sample instructions: **5**
- control-flow shaders: **0**
- discard/other side-effect shaders: **0**
- symbolic blockers: **0**
- unique DAGs: **5**

Every shader performs exactly one ordinary SM4 `sample` using **texture register `t0` and sampler register `s0`**. No second texture register participates in these five final-output programs.

The set-level DAG identity is:

`b2feaffde261ab1f4500761bffd0df03bc18184e055c84909e4fe3a3cdc2a052`

## Exact shader closures

1. `pimp_shader_unlit_4ea12045.hlsl`
   - PS SHA-256 `19d4d2ce53fa78e1f3bb5cc3cc472f3b71d15c715eff0f5adc731d8ce1fc0370`
   - 47 nodes / 1 sample / 4 outputs
   - DAG SHA-256 `f62b2b1b754cccf47d7531cf5eb101a4aeaaa340adf4f54f35246a8af8b65093`

2. `pimp_shader_vertcolorsimple_b871d333.hlsl`
   - PS SHA-256 `2a2510a4df2ae2c98a7c421ed3cb96fc617e5201747577dc36c158235e7c78c7`
   - 40 nodes / 1 sample / 4 outputs
   - DAG SHA-256 `2f2f325e732a4fb085751fe7e4c54a3280d6cda8131519f253e3bcadd0351708`

3. `pimp_shader_radiant_46ce1b1c.hlsl`
   - PS SHA-256 `cffae8606c1d91c9f9b2bb773053d05689b3f67dce7702507d61acf81878befc`
   - 33 nodes / 1 sample / 4 outputs
   - DAG SHA-256 `59580002896ee8b124a5ce3d47be60a6a797e1b166b3fc91d9bc8b735ab8f471`

4. `pimp_shader_unlitdecalblend_5c3f6d9c.hlsl`
   - PS SHA-256 `e9820077a4df69228fd1626997270d7b31337f82eab6c26c1a14a33257424a0b`
   - 27 nodes / 1 sample / 4 outputs
   - DAG SHA-256 `02f3ecf2da4814a2ea6cbcb84a2e20b8eb10ec97e9eb072c67bee50ea02bd592`

5. `pimp_shader_unlit_4b1d2e0b.hlsl`
   - PS SHA-256 `f483cbb31106fecb6ca2b0c381108c0b0e5ed879ae793476bf92b28d1c2ca262`
   - 32 nodes / 1 sample / 4 outputs
   - DAG SHA-256 `3003daac384143bee0a31661b47e007cfbe57c4c786369d66bc3cadc379408fe`

## Exact remaining leaves

Besides the single `t0/s0` texture sample, the reconstructed DAGs reference only vertex inputs and a very small constant-buffer set:

- `cb0[20]` in four shader variants;
- `cb0[100]` in the radiant variant;
- `cb2[1]` in two unlit variants.

No semantic meaning is assigned to those constant locations in this checkpoint. Their names/ownership must come from each shader's exact RDEF metadata and Material/runtime binding evidence.

## Workflow / artifact

Run: `34269131978`

Artifact:

- ID: `10073069231`
- name: `T6_NUKETOWN_PC_SERVER_MATERIAL_SHADER_CENSUS_V1`
- ZIP SHA-256: `1e3320561546c97e4dacf1504dc5a487cc267dacd0bc1656f6e64f74b4a7ef3d`

Generated symbolic result:

- `T6_NUKETOWN_SPECIAL_FULL_OUTPUT_SYMBOLIC_V1.json`
- SHA-256 `3df9fadb2b40136312359327ff178f74bb7f3068d6022bc386ccfec051a83206`

Repository seal:

- `manifests/render/T6_NUKETOWN_SPECIAL_FULL_OUTPUT_SYMBOLIC_V1.json`

## Proof boundary

The five shader payloads are inherited from the exact native Material/Technique/pass census and are SHA-256 checked from their exact OAT Technique owner before disassembly. Complete `o0` dataflow is then reconstructed from SM4 instructions.

This closes shader arithmetic/dataflow only. It does not infer:

- what RDEF name owns `t0`/`s0`;
- which exact Material texture entry binds it;
- what `cb0[20]`, `cb0[100]` or `cb2[1]` mean;
- the D3D sampler state;
- the blend/depth/alpha-test/framebuffer state.

Those are the immediate next closure layers. No family-name or generic-PBR substitution is allowed.
