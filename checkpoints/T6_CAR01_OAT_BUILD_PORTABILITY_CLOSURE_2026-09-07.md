# T6 Car01 OAT build portability closure — 2026-09-07

This checkpoint records the exact reason the first native OpenAssetTools Car01 Material/TechniqueSet dump did not reach the retail loader, and the narrowly scoped compatibility change used by the replacement proof path.

## Pinned inputs

- OpenAssetTools revision: `9dca965366541504b71fa8cfb7ac049cb9b717e1`
- Nuketown retail FastFile SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- Initial build diagnostic run: `34080018895`
- Initial diagnostic artifact: `10003518366`, `T6_NUKETOWN_CAR01_OAT_BUILD_DIAGNOSTIC_V1`
- Initial artifact digest: `sha256:1e4fa4f9381d9053a0335dd8450f1ac32fb5367ce55cea491df01e71659f2513`
- Native Car01 proof run 1: `34126267752`
- Run-1 proof artifact: `10020480749`, `T6_NUKETOWN_CAR01_OAT_MATERIAL_BINDING_V3`
- Run-1 artifact digest: `sha256:9896a3c9d4804a8e9899aedbc29f5725077871c37d7bd0ef87a1d6959a360747`

## Exact build failures

The initial diagnostic completed package installation, clone, checkout, recursive submodules and `generate.sh`. `make-debug.sh` then returned 2 while compiling `ObjWriting` under Ubuntu 24.04 / GCC 13.3.0.

The first compiler stop exposed `std::format` without a visible declaration in these translation units:

- `src/ObjWriting/Game/IW3/Menu/MenuWriterIW3.cpp`
- `src/ObjWriting/Game/IW4/Menu/MenuWriterIW4.cpp`
- `src/ObjWriting/Game/IW5/Menu/MenuWriterIW5.cpp`

Native Car01 proof run 1 applied `<format>` only to those three files. The build then advanced substantially farther and exposed the same omission in:

- `src/ObjWriting/Game/T4/Menu/MenuWriterT4.cpp`

The run-1 artifact's `oat_build.log` reaches T6 Material dumper compilation and then stops at T4 `MenuWriterT4.cpp` lines 358/360 with `error: ‘format’ is not a member of ‘std’`. Its `build_rc.txt` is `2`; the retail FastFile and Unlinker dump stages were therefore correctly skipped.

All four menu-writer translation units use `std::format` but, at the pinned OAT revision, include `<cassert>`, `<cmath>`, `<limits>` and `<sstream>` without including `<format>`. The pinned T4 source was independently checked after run 1 and has the same include pattern.

This is a host compiler/header portability defect in the pinned OAT source. It is not evidence of a T6 FastFile, Material, TechniqueSet, shader, or pointer-resolution failure because compilation stopped before the Unlinker could run on the retail zone.

## Compatibility patch boundary

Repository helper `tools/t6_oat_9dca_format_compat_patch_v1.py` was introduced at `457dd417e326ec0d6221c4d971b7196aca203155` and extended at `321146ed3f11f31de0e1c41621670e93445ddcb6`. It inserts only:

```cpp
#include <format>
```

into the four affected legacy menu-writer translation units (IW3, IW4, IW5, T4). It fails closed if their pinned source layout differs or if those files are in a mixed patch state.

The patch does **not** modify any T6 loader, generated ZoneCode, XAsset structure, Material dumper, TechniqueSet dumper, shader dumper, stream, pointer, compression, or FastFile code. Therefore native T6 asset semantics remain those of the exact pinned OAT revision.

## Replacement proof path

`.github/workflows/t6_nuketown_car01_oat_material_binding_v3.yml`, introduced at `05f310a8790befe29125d9686fbec9ae49c80668` and extended for T4 at `c8ec25778d42900e9119be18a415d3e408236f79`, applies the compatibility includes, captures their exact Git diff, builds pinned OAT, verifies the exact retail Nuketown FastFile, and then uses canonical T6 Unlinker selectors:

```text
material
techniqueset
```

It resolves the five visible Car01 Materials by their exact native OAT output paths and feeds the resulting `Material::techniqueSet->name` bindings into `tools/t6_oat_techset_binding_manifest_v1.py`. The resulting proof captures exact TechniqueSet slot/type bindings, `.tech` pass text, shader argument assignments, vertex routing, and shader binary hashes without assigning any Blender/PBR interpretation.

The proof remains open until the replacement run closes successfully and its artifact is inspected. No Car01 shader behavior or portable PBR mapping is promoted by this checkpoint alone.
