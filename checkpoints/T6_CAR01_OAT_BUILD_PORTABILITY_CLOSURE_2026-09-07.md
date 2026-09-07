# T6 Car01 OAT build portability closure — 2026-09-07

This checkpoint records the exact reasons the first native OpenAssetTools Car01 Material/TechniqueSet dumps did not reach the retail loader, and the narrowly scoped compatibility changes used by the replacement proof path.

## Pinned inputs

- OpenAssetTools revision: `9dca965366541504b71fa8cfb7ac049cb9b717e1`
- Nuketown retail FastFile SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- Initial build diagnostic run: `34080018895`
- Initial diagnostic artifact: `10003518366`, `T6_NUKETOWN_CAR01_OAT_BUILD_DIAGNOSTIC_V1`
- Initial artifact digest: `sha256:1e4fa4f9381d9053a0335dd8450f1ac32fb5367ce55cea491df01e71659f2513`
- Native Car01 proof run 1: `34126267752`
- Run-1 proof artifact: `10020480749`, `T6_NUKETOWN_CAR01_OAT_MATERIAL_BINDING_V3`
- Run-1 artifact digest: `sha256:9896a3c9d4804a8e9899aedbc29f5725077871c37d7bd0ef87a1d6959a360747`
- Native Car01 proof run 2: `34127252627`
- Run-2 proof artifact: `10021036521`, `T6_NUKETOWN_CAR01_OAT_MATERIAL_BINDING_V3`
- Run-2 artifact digest: `sha256:a6fc3dd632a71101b327879318ae69c0a8cd28627c8dc41037526735da3a1def`
- Native Car01 proof run 3: `34129496060`, launched from `f86615de246dd11ce3fb8b32ace4221e6051850a`

## Exact build failures

The initial diagnostic completed package installation, clone, checkout, recursive submodules and `generate.sh`. `make-debug.sh` then returned 2 under Ubuntu 24.04 / GCC 13.3.0.

The first compiler stop exposed `std::format` without a visible declaration in these translation units:

- `src/ObjWriting/Game/IW3/Menu/MenuWriterIW3.cpp`
- `src/ObjWriting/Game/IW4/Menu/MenuWriterIW4.cpp`
- `src/ObjWriting/Game/IW5/Menu/MenuWriterIW5.cpp`

Native Car01 proof run 1 applied `<format>` only to those three files. The build then advanced substantially farther and exposed the same omission in:

- `src/ObjWriting/Game/T4/Menu/MenuWriterT4.cpp`

Run 2 applied `<format>` to all four menu writers. The build advanced through the full ObjWriting compilation and exposed the second independent standard-library include omission in:

- `src/ObjLoading/XAnim/FlatXAnimDataWriter.cpp`

The exact run-2 errors are at the two uses of `std::numeric_limits<uint8_t>::max()` (source lines 37 and 122): GCC reports `incomplete type ‘std::numeric_limits<unsigned char>’ used in nested name specifier`. The pinned translation unit includes `<cassert>` and `<iterator>` but not `<limits>`. Run 2 therefore ended with `build_rc.txt = 2`; the exact retail FastFile, Material, and TechniqueSet dump stages were correctly skipped.

These failures are host compiler/header portability defects in the pinned OAT source. They are not evidence of a T6 FastFile, Material, TechniqueSet, shader, or pointer-resolution failure because compilation stopped before the Unlinker could run on the retail zone.

## Compatibility patch boundary

Repository helper `tools/t6_oat_9dca_format_compat_patch_v1.py` was introduced at `457dd417e326ec0d6221c4d971b7196aca203155` and extended at `321146ed3f11f31de0e1c41621670e93445ddcb6`. It inserts only `<format>` into the four affected legacy menu-writer translation units.

The replacement helper `tools/t6_oat_9dca_gcc_compat_patch_v2.py`, introduced at `8942e94b591d65371a8e09130171def7e949c107`, preserves those four edits and additionally inserts only:

```cpp
#include <limits>
```

into `src/ObjLoading/XAnim/FlatXAnimDataWriter.cpp`. It fails closed if the exact pinned source layout differs or if the target files are in a mixed patch state.

Neither compatibility helper modifies any T6 loader, generated ZoneCode, XAsset structure, Material dumper, TechniqueSet dumper, shader dumper, stream, pointer, compression, or FastFile code. Therefore native T6 asset semantics remain those of the exact pinned OAT revision.

## Replacement proof path

`.github/workflows/t6_nuketown_car01_oat_material_binding_v3.yml`, introduced at `05f310a8790befe29125d9686fbec9ae49c80668`, was extended for T4 at `c8ec25778d42900e9119be18a415d3e408236f79` and for the `numeric_limits` portability defect at `f86615de246dd11ce3fb8b32ace4221e6051850a`. It captures the exact OAT compatibility diff, builds pinned OAT, verifies the exact retail Nuketown FastFile, and then uses canonical T6 Unlinker selectors:

```text
material
techniqueset
```

It resolves the five visible Car01 Materials by their exact native OAT output paths and feeds the resulting `Material::techniqueSet->name` bindings into `tools/t6_oat_techset_binding_manifest_v1.py`. Pinned OAT's Material JSON dumper itself assigns `jMaterial.techniqueSet` directly from `material.techniqueSet->name`, so this proof crosses the retail Material pointer through OAT's native resolved object rather than q-index or additive stream-offset inference.

The resulting proof is designed to capture exact TechniqueSet slot/type bindings, `.tech` pass text, shader argument assignments, vertex routing, and shader binary hashes without assigning any Blender/PBR interpretation.

The proof remains open until the replacement run closes successfully and its artifact is inspected. No Car01 shader behavior or portable PBR mapping is promoted by this checkpoint alone.
