# T6 Lightmap Shader Lineage / One-Command Research Pipeline v2 — 2026-09-01

This checkpoint extends `T6_PROGRESS_2026-09-01_LIGHTMAP_SHADER_CHAIN.md` without rewriting that earlier historical state.

The goal remains exact T6 closure, not a plausible generic-lighting approximation. The chain now reaches from a dumped retail Material/Technique pass to exact DXBC texture registers, exact retained disassembly text, bounded instruction evidence, and conservative primary/secondary channel dependency lineage.

## Critical parser correction discovered after lineage v1

The first lineage implementation (`tools/t6_lightmap_dxbc_lineage_v1.py`) assumed undecorated assembly opcodes such as:

```text
sample r0.xyzw, v0.xyxx, t3.xyzw, s0
```

Real SM4/SM5 `fxc /dumpbin` text commonly uses decorated opcodes such as:

```text
sample_indexable(texture2d)(float,float,float,float) r0.xyzw, v0.xyxx, t3.xyzw, s0
```

and source modifiers such as:

```text
|r3.x|
-|r3.xyzx|
```

Those forms could be skipped or under-propagated by v1. That is a parser-proof defect, not a reason to infer shader semantics.

V2 therefore adds explicit support for:

- decorated opcode suffixes;
- optional numeric dumpbin prefixes such as `17: mad ...`;
- `|r#|`, `-|r#|`, `+|r#|` and `abs(r#)`-style temp/output source recognition;
- discard instructions as control/coverage blockers;
- explicit recording of plausible but unparsed lines that contain `r#`, `o#`, or `t#` tokens.

A v2 trace is closure-usable only when it is straight-line, has no unsupported destination write, and has no relevant unparsed instruction candidate.

## New permanent commits

| Commit | Artifact |
|---|---|
| `d6da5e0` | initial lineage-v1 regression checkpoint |
| `ec12c2d` | corrected lineage-v1 regression against the real `provenance` manifest schema |
| `7bf6057` | one-command `t6_lightmap_shader_research_pipeline_v1.py` |
| `47d4153` | v1 research-pipeline orchestration regression |
| `70bcca5` | `t6_lightmap_dxbc_lineage_v2.py` — dumpbin-faithful lineage parser |
| `9d1f498` | lineage-v2 decorated-opcode/source-modifier regression |
| `841edb5` | `t6_lightmap_shader_research_pipeline_v2.py` — authoritative lineage v2, v1 retained as legacy |
| `c9561dc` | pipeline-v2 promotion/determinism regression |
| `afe70ca` | `.cso` / `.dxbc` binaries added to the repository Git-LFS archival policy |

## Current one-command chain

The authoritative research entry point is now:

```text
tools/t6_lightmap_shader_research_pipeline_v2.py
```

It produces and retains:

```text
OAT materials/*.json
OAT techsets/*.techset
OAT techniques/*.tech
OAT shader_bin/ps_*.cso
        |
        v
`t6-lightmap-shader-inventory-v2`
        |
        v
`t6-lightmap-shader-dxbc-manifest-v1`
        |
        v
`t6-dxbc-disassembly-archive-v1`
        |
        +--> `t6-lightmap-disassembly-evidence-v1`
        |
        +--> `t6-lightmap-dxbc-lineage-v1`  [retained legacy comparison]
        |
        `--> `t6-lightmap-dxbc-lineage-v2`  [authoritative]
        |
        v
`t6-lightmap-shader-research-pipeline-manifest-v2`
```

The v1 research pipeline runs all earlier independently-tested stages. V2 then rebuilds lineage with the corrected dumpbin parser and preserves both lineage generations so the semantic change is auditable.

## Reproducibility policy

The pipeline regenerates deterministic in-process stages and compares canonical JSON.

By default it also invokes the selected external disassembler twice and requires:

- the disassembly archive manifest to regenerate identically;
- every retained stdout disassembly artifact to be byte-identical;
- every retained stderr artifact, when present, to be byte-identical.

The selected `fxc.exe` or `dxc.exe` is itself retained by path, byte count and SHA-256 in the disassembly archive.

If double-disassembly verification is intentionally disabled, the top-level validation manifest records that rather than silently treating the result as regeneration-proven.

## Current proof boundary

### Source/procedure closed by the tooling

The implemented chain can preserve:

```text
Material identity
  -> MaterialTechniqueSet
  -> technique type / MaterialTechnique
  -> pass index
  -> MaterialPixelShader identity
  -> exact .cso bytes + hash
  -> DXBC chunks/RDEF
  -> shader resource accessor
  -> exact t# bind point
  -> exact dumpbin text + disassembler hash
  -> all exact t# references with bounded context
  -> conservative primary/secondary sampled-channel lineage
```

### Still NOT claimed

The tooling still does not claim:

- the physical meaning of primary lightmap R/G/B/A;
- the physical meaning of secondary lightmap R/G/B/A;
- an exact algebraic primary/secondary lighting equation;
- CFG/SSA-correct lineage through branches/loops;
- cross-technique equivalence of lightmap arithmetic;
- retail T6 shader proof until an actual retained retail OAT shader dump is archived and processed.

## Important repository state

At this checkpoint, no retained retail `shader_bin/ps_*.cso` lightmap fixture is surfaced in this repository. Code search finds the tooling/documentation chain, not an archived retail shader binary.

Therefore no retail channel/equation promotion is made in this checkpoint.

`.gitattributes` now routes `.cso` and `.dxbc` through Git LFS so the exact retail shader inputs can be retained once collected without losing the authoritative binary evidence.

## Exact Windows research command

After running the pinned stock OpenAssetTools dumper on a retail T6 map/zone and retaining its normal output directories, run:

```bat
py tools\t6_lightmap_shader_research_pipeline_v2.py ^
  --material-root "<OAT_DUMP_ROOT>\materials" ^
  --techset-root "<OAT_DUMP_ROOT>\techsets" ^
  --technique-root "<OAT_DUMP_ROOT>\techniques" ^
  --shader-root "<OAT_DUMP_ROOT>\shader_bin" ^
  --tool "<PATH_TO_FXC_OR_DXC>" ^
  --tool-kind fxc ^
  --out-dir "<OUTPUT_ROOT>\lightmap_shader_research_v2"
```

Use `--tool-kind dxc` only when the supplied executable is `dxc.exe`.

Default behavior is intentionally strict:

- missing selected shader binaries fail;
- an empty lightmap-shader inventory fails;
- a bound lightmap register with no executable disassembly use fails;
- deterministic stages must regenerate identically;
- external disassembly must regenerate byte-identically.

Relaxation flags exist only for explicitly incomplete research runs and are recorded in the top-level manifest.

## What should be archived from the first retail run

For Nuketown first, retain at minimum:

1. the exact relevant OAT Material JSONs;
2. exact referenced `.techset` and `.tech` files;
3. exact selected `shader_bin/ps_*.cso` files;
4. `t6_lightmap_shader_inventory_v2.json`;
5. `t6_lightmap_shader_dxbc_manifest_v1.json`;
6. `t6_dxbc_disassembly_archive_v1.json`;
7. all `disassembly/*.dumpbin.txt` artifacts;
8. `t6_lightmap_disassembly_evidence_v1.json`;
9. legacy `t6_lightmap_dxbc_lineage_v1.json`;
10. authoritative `t6_lightmap_dxbc_lineage_v2.json`;
11. `t6_lightmap_shader_research_manifest_v2.json`;
12. SHA-256 of the owning retail fastfile and the pinned OAT version/commit used to dump it.

The `.cso` binaries remain authoritative. Dumpbin text is reproducible evidence derived from those exact bytes and the exact hashed disassembler.

## Immediate next semantic promotion after retail bytes exist

For every selected world-lightmap shader:

1. enumerate actual sampled channels from primary and secondary;
2. classify straight-line vs control-flow shaders;
3. preserve per-output lineage from v2;
4. group equivalent instruction signatures by technique family;
5. construct an exact instruction-level expression only for straight-line candidates;
6. validate that expression against the original instruction stream;
7. compare the same channel/equation behavior across multiple retail materials and maps;
8. only then assign physical channel meaning using the paired retail lightmap image data.

The final T6 lightmap reconstruction must be supported by both sides of the equation: the exact shader program and the exact primary/secondary pixel data. Neither side alone is sufficient.

## Test execution status

The new regression scripts are committed, but this private repository currently exposes no CI/status run for these commits through the connected GitHub interface. They must therefore be described as **regressions committed**, not remotely executed/proven in this checkpoint.

That distinction is intentional and follows `research/T6_PROOF_STANDARD.md`.
