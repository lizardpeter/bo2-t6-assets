# T6 Lightmap Shader Provenance / DXBC Chain — 2026-09-01

This checkpoint records the path from a T6 world Material to exact DXBC instruction evidence. It is deliberately separate from the claim that primary/secondary lightmap channel semantics or the final lighting equation are solved.

## Critical upstream discovery

Pinned stock OpenAssetTools (`Laupetin/OpenAssetTools` commit `7d027e8f89118196713e955b0e11f8404149c54d`) already enables shader dumping for T6.

In its T6 `TechsetDumper` path:

```text
MaterialPixelShader.prog.loadDef.program
MaterialPixelShader.prog.loadDef.programSize
```

are written directly for DX11 T6 shaders. No custom bo2-t6-assets patch is required to obtain the pixel shader bytecode itself.

OAT output identity rules:

```text
Material JSON techniqueSet
  -> techsets/<MaterialTechniqueSet.name>.techset
  -> techniques/<MaterialTechnique.name>.tech
  -> pixelShader <major>.<minor> "<MaterialPixelShader.name>"
  -> shader_bin/ps_<MaterialPixelShader.name>.cso
```

The `.tech` writer uses OAT's DX11 shader reflection to resolve the game's MaterialShaderArgument destination texture index to the actual DXBC resource name. For code samplers it emits:

```text
<shaderResource> = sampler.<T6 code sampler>;
```

When both names are already identical and debug output is enabled, OAT writes an `Omitted due to matching accessors` comment. That comment is still an exact binding statement and is intentionally parsed by our tooling.

## Permanent commits

| Commit | Artifact |
|---|---|
| `df2ced2` | `tools/t6_lightmap_shader_inventory_v1.py` — Material/techset/technique/pixel-shader worklist + exact DXBC hashes |
| `bb69ca7` | v1 inventory regression |
| `c4ca2e2` | `tools/t6_dxbc_inspect_v1.py` — strict DXBC container, SHDR/SHEX and RDEF inspector |
| `e6fdd34` | DXBC inspector synthetic regression |
| `e2843f8` | retained inspection of OAT's independent real T6 test DXBC fixture |
| `eef67f6` | `tools/t6_lightmap_shader_inventory_v2.py` — exact T6 code sampler -> shader resource destination bridge |
| `4cc0a89` | v2 resource-bridge regression |
| `344af4b` | `tools/t6_lightmap_shader_dxbc_manifest_v1.py` — resource destination -> RDEF texture register (`t#`) resolution |
| `256ca1b` | register-resolution regression |
| `cbcc6d7` | `tools/t6_dxbc_disassemble_v1.py` — exact fxc/dxc dumpbin archival stage |
| `a215406` | disassembly archival regression |
| `9d5876c` | `tools/t6_lightmap_disassembly_evidence_v1.py` — exact t# instruction/context extraction |
| `7b8e722` | disassembly evidence regression |

## Exact chain now represented

For every selected retail edge the intended manifest chain is:

```text
GfxWorld surface
  -> exact Material identity
  -> Material.techniqueSet
  -> technique type / MaterialTechnique name
  -> pass index
  -> MaterialPixelShader name
  -> exact shader_bin/ps_<name>.cso bytes + SHA-256
  -> DXBC container/chunk hashes
  -> RDEF shader-resource name + bind point
  -> T6 code sampler identity
  -> dumpbin instruction lines touching that t#
```

The T6 code sampler identities remain:

```text
TEXTURE_SRC_CODE_LIGHTMAP_PRIMARY   = 0x4 -> lightmapSamplerPrimary
TEXTURE_SRC_CODE_LIGHTMAP_SECONDARY = 0x5 -> lightmapSamplerSecondary
```

## DXBC inspection proof boundary

`t6_dxbc_inspect_v1.py` validates:

- `DXBC` magic;
- declared container size;
- chunk table bounds and non-overlap;
- per-chunk payload SHA-256;
- exactly one SHDR/SHEX program chunk;
- RDEF presence;
- SHDR/SHEX shader model/program type;
- RDEF shader model;
- RDEF bound-resource table bounds;
- resource name/type/return type/dimension/bind point/bind count;
- exact lightmap resource names where those names are used directly.

It does **not** decode shader instructions.

### Independent real DXBC fixture

OpenAssetTools' T6 unit-test `ps_simple.hlsl.cso` was inspected independently from its retained upstream bytes:

```text
size       432 bytes
SHA-256    1c2b91c52e8a3c2d2fddd8153c3679ee9e59eba15796f52eb956c968e9f3bdf5
chunks     RDEF, ISGN, OSGN, SHDR, STAT
program    pixel shader 4.0
RDEF       creator = "OpenAssetTools Test Shader"
```

This proves our DXBC container model against a real compiled DXBC fixture. It is **not** retail Black Ops II lightmap evidence.

## Resource/register bridge

Inventory v2 parses both forms:

```text
renamedResource = sampler.lightmapSamplerPrimary;
```

and:

```text
// Omitted due to matching accessors: lightmapSamplerSecondary = sampler.lightmapSamplerSecondary;
```

The DXBC manifest then requires that each destination name resolves to exactly one RDEF `TEXTURE` entry and records:

```text
codeSampler
shaderResource
textureRegister = t#
bindPoint
bindCount
returnType
dimension
RDEF resource index
```

It also requires the `.tech` shader-model declaration to agree with the DXBC SHDR/SHEX model and re-verifies byte count + SHA-256 before inspection.

## Disassembly archive

`t6_dxbc_disassemble_v1.py` accepts an explicit executable path and kind:

```text
fxc /dumpbin shader.cso
```

or:

```text
dxc -dumpbin shader.cso
```

The executable itself is hashed. For each shader, input bytes are re-verified from the DXBC manifest before launch. Raw stdout is retained byte-for-byte and hashed; stderr is also retained if present.

This avoids treating a disassembler's text rendering as the primary source artifact: the exact `.cso` remains authoritative.

## Instruction evidence extraction

`t6_lightmap_disassembly_evidence_v1.py` uses the already-proven `t#` bindings and extracts every non-comment dumpbin line containing those registers.

Each record preserves:

- line number;
- exact line text;
- opcode;
- declaration vs executable classification;
- sample/gather/load classification;
- t# references and operand swizzles;
- configurable surrounding line context;
- shader/disassembly hashes and full Material/Technique/pass provenance.

It can optionally fail if a bound lightmap register has no executable instruction use.

## Current proof statement

The tooling chain from OAT text/bytecode outputs to deterministic shader worklists/register evidence is synthetic-regression covered and source-grounded. The OAT real test DXBC supplies an independent non-synthetic container fixture.

What remains **not retail-proven in this repository** is the actual Nuketown/world lightmap shader inventory because the local retail OAT dump has not yet been retained here.

What remains **semantically unsolved** even after that inventory is produced:

- which primary image channels carry which lighting quantities;
- which secondary image channels carry which lighting quantities;
- channel swizzles actually consumed by representative T6 world shaders;
- exact arithmetic/combine equation;
- variation of that equation across technique families;
- whether any special world material bypasses or repurposes the normal lightmap pair.

## Next semantic stage

Add a conservative component-lineage pass over dumpbin assembly. Its job is not to reconstruct HLSL. It should:

1. tag the result channels of sample/load instructions from the known primary/secondary t# registers;
2. propagate those channel-dependency tags through temporary registers conservatively;
3. report which primary/secondary channels can reach each output register/channel;
4. detect branches/loops and lower confidence rather than flattening them as exact straight-line logic;
5. preserve every instruction used in a dependency trace;
6. keep the final algebraic equation as a separate, stronger proof target.

Only actual retail shader data can promote T6 channel semantics beyond hypothesis.
