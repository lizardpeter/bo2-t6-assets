# Nuketown v31 generated-shader checkpoint

This checkpoint records the internal `mp_nuketown_2020` v31 state and the renderer-contract work that followed it. It exists specifically so later work does not silently collapse proven retail T6 shader semantics back into generic glTF/PBR guesses.

## Internal v31 artifact

The v31 combined-map artifact is an internal build checkpoint; the binary itself is not committed here.

- SHA-256: `6aff8a3c8e44dd5d0c20a7f229d2102677b092add054341b265aec74547882df`
- v25 non-regression: **0 failures**
- v25 binary is an **exact prefix** of v31
- Independent `trimesh` import passed
- Nodes, meshes, materials, textures, all 809 images, three animations, skins, scenes, and scene-root placement were retained

### Added shader-facing data in v31

- exact secondary material UV1 on **507** full-world surfaces
- exact secondary material UV2 on **48** surfaces
- exact secondary material UV3 on **1** surface
- exact per-vertex normal-transform data on **34 surfaces / 548 vertices**
- all **933 generated-material primitives** use `_T6_LAYER_WEIGHTS` for the T6 packed generated-layer controls
- zero generated-material packed-color streams are exposed as ordinary Blender `COLOR_0`
- all **120 generated materials** had complete retail shader recipes in the internal v31 build state
- **34 / 34** retail pixel-shader archetypes were resolved
- exact diffuse-operation census:
  - **8 additive**
  - **84 alpha blend**
  - **47 multiply**
- **9 generated normal-layer material recipes** were source-closed
- **7 secondary-specular cases** were identified and texture-resolved

## Important provenance boundary

The repository does **not** currently contain a canonical serialized per-material v31 recipe field that can be proven to be the exact schema used by the internal v31 build. Earlier exports/documentation preserve generated material/component identity (historically including `BO2_material`), but that is not evidence for a v31 `TechniqueSet`/pixel-shader-recipe extras key.

Therefore adapters MUST NOT guess a v31 key. A canonical repository-owned recipe schema is being introduced separately and exporters should attach it explicitly going forward.

## Source-closed universal shader semantics after v31

The retail shader corpus closes more of the problem than the original v31 summary implied.

### Generated color recurrence

The ordered T6 layer compositor is source-closed:

- A: `prev.rgb + layer.rgb * exactWeight`
- B: `prev.rgb + (layer.rgb - prev.rgb) * exactWeight`
- M: `prev.rgb * (1 + (layer.rgb - 1) * exactWeight)`
- T: `select(exactThresholdCondition, layer.rgb, prev.rgb)`

Exact weight dispatch:

- ordinary A: `layerAlpha * vertexWeight`
- ordinary B: `layerAlpha * vertexWeight`
- `xN` B: `vertexWeight`
- M: `vertexWeight`
- T: `(layerAlpha * vertexWeight) >= 0.5`
- `vN`: exact retained per-shader height DAG; **no universal shortcut is allowed**

Generated color is composed in the retail encoded texture domain before the explicit shader RGB square used by the later lighting path.

### Layered normal recurrence

Secondary normal RG is decoded and, where required, transformed by the exact per-vertex 2x2 transform.

Stored transform byte order:

`[m00, m11, m01, m10]`

Logical shader matrix after UNORM8 -> `[-1,+1]`:

`[[m00,m01],[m10,m11]]`

Normal-layer XY state uses the same exact RGB compositor weight/threshold recurrence. The later universal retail reconstruction is:

`rawNormal = baseNormal + layeredNormalX * xBasis + layeredNormalY * yBasis`

followed by normalization.

### Layered specular recurrence

The remaining seven Nuketown secondary-specular cases are no longer seven unknown compositor equations. The retained retail corpus proves the ordered XYZW recurrence across 73 unique layered-specular shaders:

- blend: `prevSpecRGBA + (layerSpecRGBA - prevSpecRGBA) * exactRgbWeight`
- threshold: `select(exactRgbThresholdCondition, layerSpecRGBA, prevSpecRGBA)`

Observed proof corpus:

- **82** layered-specular steps
- **74** blend transitions
- **8** threshold/select transitions
- **328** XYZW recurrence checks
- **0** recurrence failures

When the base specular map is absent, the proven initial RGB fallback is `(0.2,0.2,0.2)`. The W channel comes from base-color alpha for `x0` techniques and is zero otherwise.

The unresolved portion is downstream interpretation/application in the retail lighting/reflection path, not the layer recurrence itself. Do not map the XYZW state to generic Principled roughness/metallic without proof.

## Repository implementation added after v31

### `tools/t6_generated_world_shader_semantics_v1.py`

Now contains map-independent:

- generated layer token parsing
- exact A/B/M/T operation contract
- exact ordinary/x/threshold weight dispatcher
- fail-closed `vN` height handling
- normal-transform unpack/decode
- normal-layer XY recurrence
- universal basis reconstruction + normalization
- layered-specular XYZW recurrence
- no-base-spec fallback
- normalized T6 -> glTF vertex contract

### Regression coverage

`tools/test_t6_generated_world_shader_semantics_v1.py` covers:

- generated token parsing
- ordinary/x/threshold/height weight dispatch
- height fail-closed behavior
- normal transform decode
- normal weighting
- normal XY recurrence
- normal basis reconstruction
- A/B/M/T diffuse recurrence
- specular fallback
- blend/threshold specular recurrence

### Blender/Tour visual application layer

`tools/t6_blender_generated_layer_preview_v1.py` and `v2.py` are the first fail-closed Blender-facing adapters.

They:

- join textures by exact source identity from glTF T6 dependency metadata
- reconstruct supported generated diffuse layers in the retail encoded texture domain
- apply the explicit retail RGB square
- consume `_T6_LAYER_WEIGHTS`
- use exact secondary material UV sets
- support current Blender `Separate Color` and legacy `Separate RGB`
- preserve normal/specular dependency identity
- refuse unsupported `vN` execution rather than approximating it
- deliberately do **not** fabricate a T6-to-Principled specular/lightmap/reflection conversion

Current Blender output is therefore a **visual generated-diffuse preview under Blender lighting**, not a declaration that the complete Treyarch lighting shader is solved.

`tools/test_t6_blender_generated_layer_preview_v2.py` adds pure-Python preflight regression coverage for GLB parsing, recipe precedence, dependency flattening, exact embedded-dependency preference, and ambiguity/missing-dependency fail-closed behavior.

## Next exact steps

1. Introduce one canonical serialized generated-shader recipe schema and attach it explicitly to exporters going forward. Do not infer the internal v31 field name.
2. Compile the exact retained `vN` height DAGs into the Blender/Tour application layer.
3. Wire the already source-closed normal XY transform/reconstruction into the visual adapter after confirming Blender tangent-basis orientation against the glTF/T6 basis contract.
4. Carry the source-closed layered-specular XYZW state through the consumer without generic PBR reinterpretation.
5. Reproduce the retail lightmap/directional-lightmap/reflection/lighting portion of the shader.
6. Only then promote the next large downloadable map build as the visual successor to v31.
