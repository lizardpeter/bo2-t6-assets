# T6 Car01 OAT build portability closure — 2026-09-07

This checkpoint records the exact reason the first native OpenAssetTools Car01 Material/TechniqueSet dump did not reach the retail loader, and the narrowly scoped compatibility change used by the replacement proof path.

## Pinned inputs

- OpenAssetTools revision: `9dca965366541504b71fa8cfb7ac049cb9b717e1`
- Nuketown retail FastFile SHA-256: `6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0`
- Failed diagnostic run: `34080018895`
- Diagnostic artifact: `10003518366`, `T6_NUKETOWN_CAR01_OAT_BUILD_DIAGNOSTIC_V1`
- Artifact digest: `sha256:1e4fa4f9381d9053a0335dd8450f1ac32fb5367ce55cea491df01e71659f2513`

## Exact failure

The diagnostic completed package installation, clone, checkout, recursive submodules and `generate.sh`. `make-debug.sh` then returned 2 while compiling `ObjWriting` under Ubuntu 24.04 / GCC 13.3.0.

The compiler errors were `std::format` not being a member of `std` in exactly three translation units:

- `src/ObjWriting/Game/IW3/Menu/MenuWriterIW3.cpp`
- `src/ObjWriting/Game/IW4/Menu/MenuWriterIW4.cpp`
- `src/ObjWriting/Game/IW5/Menu/MenuWriterIW5.cpp`

Each translation unit uses `std::format` but, at the pinned OAT revision, includes `<cassert>`, `<cmath>`, `<limits>` and `<sstream>` without including `<format>`. Other OAT translation units using `std::format` include `<format>` directly.

This is a host compiler/header portability defect in the pinned OAT source. It is not evidence of a T6 FastFile, Material, TechniqueSet, shader, or pointer-resolution failure because compilation stopped before the Unlinker could run on the retail zone.

## Compatibility patch boundary

Repository helper `tools/t6_oat_9dca_format_compat_patch_v1.py`, introduced at `457dd417e326ec0d6221c4d971b7196aca203155`, inserts only:

```cpp
#include <format>
```

into those three non-T6 menu-writer translation units. It fails closed if their pinned source layout differs or if the three files are in a mixed patch state.

The patch does **not** modify any T6 loader, generated ZoneCode, XAsset structure, Material dumper, TechniqueSet dumper, shader dumper, stream, pointer, compression, or FastFile code. Therefore native T6 asset semantics remain those of the exact pinned OAT revision.

## Replacement proof path

`.github/workflows/t6_nuketown_car01_oat_material_binding_v3.yml`, introduced at `05f310a8790befe29125d9686fbec9ae49c80668`, applies the compatibility include, captures its exact Git diff, builds pinned OAT, verifies the exact retail Nuketown FastFile, and then uses canonical T6 Unlinker selectors:

```text
material
techniqueset
```

It resolves the five visible Car01 Materials by their exact native OAT output paths and feeds the resulting `Material::techniqueSet->name` bindings into `tools/t6_oat_techset_binding_manifest_v1.py`. The resulting proof captures exact TechniqueSet slot/type bindings, `.tech` pass text, shader argument assignments, vertex routing, and shader binary hashes without assigning any Blender/PBR interpretation.

The proof remains open until that workflow closes successfully and its artifact is inspected. No Car01 shader behavior or portable PBR mapping is promoted by this checkpoint alone.
