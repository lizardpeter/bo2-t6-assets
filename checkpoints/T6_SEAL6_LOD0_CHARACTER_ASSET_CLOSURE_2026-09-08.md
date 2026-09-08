# T6 SEAL6 LOD0 character asset closure — 2026-09-08

This checkpoint seals the source-derived third-person SEAL6 LOD0 character asset path on **Blender 5.2.1 LTS** without broadening the proof boundary.

## Final authoritative assembly

- GitHub Actions run: `34188975695`
- Artifact: `T6_SEAL6_SMG_LOD0_FULL_RETAIL_EXACT_MATERIALS_BLENDER_5_2_1`
- Artifact ID: `10041519642`
- Artifact ZIP SHA-256: `e47668047bb68e09359f6f88407dc6686337ca1c2a64c85c641c83a0caffe7ab`
- Final `.blend`: `T6_SEAL6_SMG_LOD0_FULL_RETAIL_EXACT_MATERIALS_BLENDER_5_2_1.blend`
- Final `.blend` SHA-256: `77cdc7abe79a13c0ea52ccb38190f1932d31c6381037e11e5089c7f851c683c1`
- Runtime: `Blender 5.2.1 LTS`
- Exact Blender 5.2.1 Linux archive SHA-256: `a31f524fa99a527d3d52b7f5aaa68c34e1a19d5a1c9473f79c5cc610fd5b10e9`

The file was saved, reopened in a fresh Blender 5.2.1 process, and all final canaries passed.

## Geometry / skeleton / animation authority

LOD0 remains:

- 14 primitives
- 13,490 vertices
- 14,968 triangles
- 102 joints
- 12 retail Material identities
- six exact retail animations
- no standard glTF / Blender `COLOR_0`
- no standard derived tangent

The exact shader-only retail vertex inputs survive natively in Blender 5.2.1 as POINT-domain attributes:

- `_T6_COLOR_RGBA`
- `_T6_XMODEL_NORMAL`
- `_T6_XMODEL_TANGENT`
- `_T6_TANGENT_HANDEDNESS`

The old Blender 4.0.2 binding-stripping / reinjection transport is historical diagnostics only and is not part of the authoritative production path.

## Complete LOD0 native Material input closure

All 12 LOD0 Materials are represented by exact native OAT Material records.

Final role graph:

- 12 Materials
- 41 native texture slots
- 40 streamed retail slots
- 39 unique exact streamed retail images
- one exact non-streamed built-in alias: cornea `sw_radiant_default`
- zero fabricated payloads for the shared built-in alias

All 40 streamed slots retain exact-key + CRC29-validated retail payload identity.

## Ordinary-lit shader closure

Exact all-LOD0 ordinary-lit ABI:

- 36 native texture slots referenced by the exact executable
- 5 native slots preserved but not referenced by ordinary `lit`
- 22 native Material constants
- 58 exact VS/PS Material argument bindings

Exact shader families present:

1. hero skin
2. standard skin
3. cornea
4. cloth

The seven cloth Materials use their independently closed cloth pixel shader rather than being inferred equivalent to the skin family.

Final Blender local-shader graph census:

- 4 skin local diffuse graphs
- 7 cloth local diffuse graphs
- 1 hero detail-normal graph
- 1 cornea local graph
- 22 native Material constant nodes
- 21 exact executable-literal unit nodes for the seven cloth Materials

All five native slots absent from ordinary `lit` remain present and have zero outgoing links in the final file.

## Exact ordinary-lit pipeline state

The selected state remains the exact native lookup:

`stateBits[stateBitsEntry[4]]`

where pinned T6 TechniqueType index 4 is ordinary `lit`.

Final state census:

- 12 selected pipeline states closed
- 11 opaque Materials
- 1 translucent cornea Material
- 2 unique selected state payloads
- every selected state invariant across physical Material copies

Exact T6/D3D state is stored verbatim as metadata. Any Blender viewport culling/transparency mapping remains authoring-only and is not asserted D3D-equivalent.

## Head duplicate boundary

The head whole-Material duplicate winner remains unresolved for the retail client because the two physical copies differ in `thermalMaterial` and retail `t6mp.exe` duplicate precedence has not been source-closed.

This no longer blocks the ordinary-lit character asset path because:

- the complete head texture-role table is invariant across both copies;
- the TechniqueSet name is invariant;
- the ordinary-lit executable VS+PS bytes are invariant;
- the selected ordinary-lit pipeline state is invariant.

No retail-client whole-Material winner is inferred.

## Closure claim

`characterLocalAssetReversalExact = true`

This claim covers the standalone third-person SEAL6 LOD0 asset data: geometry, skin, six animations, Material identities, all native Material inputs, exact retail streamed payloads, exact shader-only vertex attributes, ordinary-lit material-local shader equations, and selected ordinary-lit D3D pipeline state.

`completeRetailPixelOutput = false`

That remaining false value is intentional. Model-lighting volumes, reflection probes, SH/grid/sun state, fog and HDR are scene/runtime inputs owned outside the standalone character asset. They must be provided by exact runtime/map state or an exact bake; they are not fabricated inside this character file.

This distinction is the boundary between a closed character asset reversal and a complete in-map retail frame reconstruction.
