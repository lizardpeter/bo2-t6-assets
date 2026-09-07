# T6 native OAT Material / TechniqueSet dump contract — 2026-09-06

Pinned OpenAssetTools revision: `9dca965366541504b71fa8cfb7ac049cb9b717e1`.

This checkpoint records the exact native dump contract used by the Car01 proof path. It is source-level tooling evidence, not an inferred T6 shader interpretation.

## Canonical T6 Unlinker asset selectors

At the pinned revision, `src/Common/Game/T6/GameT6.cpp` defines the top-level asset type names. The relevant canonical names are:

```text
material
techniqueset
```

It also registers `techset` as an alias for `techniqueset`.

Therefore the earlier Car01 workflows that passed `--include-assets technique_set` used a nonexistent T6 asset selector. That spelling is retired. New native dumps must use `--include-assets techniqueset` (or the proven `techset` alias).

## Material binding is direct after loader resolution

At the pinned OAT revision, `src/ObjWriting/Material/MaterialJsonDumper.cpp.template` writes the JSON `techniqueSet` field from:

```cpp
if (material.techniqueSet && material.techniqueSet->name)
    jMaterial.techniqueSet = AssetName(material.techniqueSet->name);
```

Therefore the emitted Material JSON records the name reached by the already-resolved `Material::techniqueSet` pointer. The Car01 proof does not need to infer a TechniqueSet owner from a block-5 offset or q-index.

`src/ObjCommon/Material/MaterialCommon.cpp` fixes the output path to:

```text
materials/<material-asset-name>.json
```

(non-retail generated `*...` material names have a separate sanitization rule that is irrelevant to the five Car01 targets).

## TechniqueSet -> technique contract

`src/ObjWriting/Techset/CommonTechsetDumper.cpp` serializes each populated TechniqueSet slot as one or more quoted technique-type headers followed by the referenced technique asset name and `;`. Shared technique pointers are represented by multiple slot/type headers followed by one technique value.

`src/ObjCommon/Techset/TechsetCommon.cpp` fixes the paths to:

```text
techsets/<techset-name>.techset
techniques/<technique-name>.tech
```

## Technique -> pass / shader / argument contract

For T6, `src/ObjWriting/Techset/TechsetDumper.cpp.template` converts every `MaterialTechnique` pass and preserves:

- technique flags (debug output),
- `MaterialPass::customSamplerFlags`,
- T6 `materialType` and `precompiledIndex` in the debug comment,
- vertex shader name and binary,
- pixel shader name and binary,
- vertex declaration stream routing,
- every shader argument across `perPrimArgCount + perObjArgCount + stableArgCount`.

The T6 argument conversion preserves the native DX11 destination information (`buffer`, constant-buffer byte offset/size, or texture/sampler indices) and its source class/value: code constant, material constant/name hash, code sampler, material sampler/name hash, or literal constant.

`src/ObjWriting/Techset/CommonTechniqueDumper.cpp` then resolves those native destinations against the DX11 shader reflection data and emits readable assignments such as `... = material.<property>;`, `... = constant.<source>;`, and `... = sampler.<source>;`. If a material name hash cannot be resolved to a known property name, it remains explicit as `material.#0x...`; it is not guessed.

## Exact shader payload paths

T6 has `DUMP_SHADERS` enabled in `TechsetDumper.cpp.template`. `src/ObjCommon/Shader/ShaderCommon.cpp` fixes the raw shader payload output paths to:

```text
shader_bin/vs_<vertex-shader-name>.cso
shader_bin/ps_<pixel-shader-name>.cso
```

For T6 / DX11, `DumpVertexShader` and `DumpPixelShader` write exactly `programSize` bytes from the native loaded shader program buffer.

## Repository parser

`tools/t6_oat_techset_binding_manifest_v1.py` consumes only the above native OAT outputs after Material -> TechniqueSet resolution and records:

- exact Material -> TechniqueSet names,
- TechniqueSet slot/type -> technique names,
- exact `.tech` pass text,
- shader names/models,
- material/constant/sampler assignments,
- vertex routing,
- exact CSO sizes and SHA-256 hashes.

Its proof boundary deliberately stops before assigning any Blender/PBR interpretation to the retail shader inputs.
