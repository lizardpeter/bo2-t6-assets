#!/usr/bin/env python3
"""Instrument pinned OAT T6 ContentLoader with a WeaponCamo semantic trace.

Diagnostic only. The trace runs after the normal T6 loader has fully loaded the
current XAsset and before varXAsset advances. It therefore observes native
resolved pointers without changing stream, registration, or dump semantics.
Relevant IMAGE, MATERIAL and WEAPON_CAMO XAssets are also emitted as pointer
anchors so every camo dependency can be joined back to an exact retail ordinal
without relying on name uniqueness.
"""
from __future__ import annotations

import argparse
from pathlib import Path

TARGET = "src/ZoneLoading/Game/T6/ContentLoaderT6.cpp"
MARKER = "T6_WEAPON_CAMO_ROOT"

HELPER = r'''
namespace
{
    const char* T6WeaponCamoImageName(const GfxImage* image)
    {
        return image && image->name ? image->name : "<null>";
    }

    const char* T6WeaponCamoMaterialName(const Material* material)
    {
        return material && material->info.name ? material->info.name : "<null>";
    }

    void TraceT6WeaponCamoTarget(const size_t ordinal, const XAsset& asset)
    {
        const char* name = nullptr;
        switch (asset.type)
        {
        case ASSET_TYPE_IMAGE:
            name = T6WeaponCamoImageName(asset.header.image);
            break;
        case ASSET_TYPE_MATERIAL:
            name = T6WeaponCamoMaterialName(asset.header.material);
            break;
        case ASSET_TYPE_WEAPON_CAMO:
            name = asset.header.weaponCamo && asset.header.weaponCamo->name ? asset.header.weaponCamo->name : "<null>";
            break;
        default:
            return;
        }
        std::fprintf(stderr,
                     "T6_WEAPON_CAMO_TARGET\t%zu\t%u\t%p\t%s\n",
                     ordinal,
                     static_cast<unsigned>(asset.type),
                     asset.header.data,
                     name ? name : "<null>");
    }

    void TraceT6WeaponCamo(const size_t ordinal, const XAsset& asset)
    {
        if (asset.type != ASSET_TYPE_WEAPON_CAMO)
            return;

        const auto* camo = asset.header.weaponCamo;
        if (!camo)
        {
            std::fprintf(stderr, "T6_WEAPON_CAMO_VIOLATION\t%zu\tnull_root\n", ordinal);
            return;
        }

        std::fprintf(stderr,
                     "T6_WEAPON_CAMO_ROOT\t%zu\t%p\t%s\t%u\t%u\t%p\t%s\t%p\t%s\n",
                     ordinal,
                     static_cast<const void*>(camo),
                     camo->name ? camo->name : "<null>",
                     camo->numCamoSets,
                     camo->numCamoMaterials,
                     static_cast<const void*>(camo->solidBaseImage),
                     T6WeaponCamoImageName(camo->solidBaseImage),
                     static_cast<const void*>(camo->patternBaseImage),
                     T6WeaponCamoImageName(camo->patternBaseImage));

        if (camo->numCamoSets && !camo->camoSets)
        {
            std::fprintf(stderr, "T6_WEAPON_CAMO_VIOLATION\t%zu\tnull_camo_sets\n", ordinal);
            return;
        }
        if (camo->numCamoMaterials && !camo->camoMaterials)
        {
            std::fprintf(stderr, "T6_WEAPON_CAMO_VIOLATION\t%zu\tnull_camo_material_sets\n", ordinal);
            return;
        }

        for (unsigned setIndex = 0; setIndex < camo->numCamoSets; ++setIndex)
        {
            const auto& set = camo->camoSets[setIndex];
            std::fprintf(stderr,
                         "T6_WEAPON_CAMO_SET\t%zu\t%u\t%p\t%s\t%p\t%s\t%a\t%a\t%a\n",
                         ordinal,
                         setIndex,
                         static_cast<const void*>(set.solidCamoImage),
                         T6WeaponCamoImageName(set.solidCamoImage),
                         static_cast<const void*>(set.patternCamoImage),
                         T6WeaponCamoImageName(set.patternCamoImage),
                         static_cast<double>(set.patternOffset.x),
                         static_cast<double>(set.patternOffset.y),
                         static_cast<double>(set.patternScale));
        }

        for (unsigned materialSetIndex = 0; materialSetIndex < camo->numCamoMaterials; ++materialSetIndex)
        {
            const auto& materialSet = camo->camoMaterials[materialSetIndex];
            std::fprintf(stderr,
                         "T6_WEAPON_CAMO_MATERIAL_SET\t%zu\t%u\t%u\n",
                         ordinal,
                         materialSetIndex,
                         materialSet.numMaterials);
            if (materialSet.numMaterials && !materialSet.materials)
            {
                std::fprintf(stderr,
                             "T6_WEAPON_CAMO_VIOLATION\t%zu\tnull_materials\t%u\n",
                             ordinal,
                             materialSetIndex);
                continue;
            }

            for (unsigned materialIndex = 0; materialIndex < materialSet.numMaterials; ++materialIndex)
            {
                const auto& material = materialSet.materials[materialIndex];
                std::fprintf(stderr,
                             "T6_WEAPON_CAMO_MATERIAL\t%zu\t%u\t%u\t%u\t%u\t%a\t%a\t%a\t%a\t%a\t%a\t%a\t%a\n",
                             ordinal,
                             materialSetIndex,
                             materialIndex,
                             static_cast<unsigned>(material.replaceFlags),
                             static_cast<unsigned>(material.numBaseMaterials),
                             static_cast<double>(material.shaderConsts[0]),
                             static_cast<double>(material.shaderConsts[1]),
                             static_cast<double>(material.shaderConsts[2]),
                             static_cast<double>(material.shaderConsts[3]),
                             static_cast<double>(material.shaderConsts[4]),
                             static_cast<double>(material.shaderConsts[5]),
                             static_cast<double>(material.shaderConsts[6]),
                             static_cast<double>(material.shaderConsts[7]));

                if (material.numBaseMaterials && (!material.baseMaterials || !material.camoMaterials))
                {
                    std::fprintf(stderr,
                                 "T6_WEAPON_CAMO_VIOLATION\t%zu\tnull_material_pair_array\t%u\t%u\n",
                                 ordinal,
                                 materialSetIndex,
                                 materialIndex);
                    continue;
                }

                for (unsigned overrideIndex = 0; overrideIndex < material.numBaseMaterials; ++overrideIndex)
                {
                    const auto* baseMaterial = material.baseMaterials[overrideIndex];
                    const auto* camoMaterial = material.camoMaterials[overrideIndex];
                    std::fprintf(stderr,
                                 "T6_WEAPON_CAMO_OVERRIDE\t%zu\t%u\t%u\t%u\t%p\t%s\t%p\t%s\n",
                                 ordinal,
                                 materialSetIndex,
                                 materialIndex,
                                 overrideIndex,
                                 static_cast<const void*>(baseMaterial),
                                 T6WeaponCamoMaterialName(baseMaterial),
                                 static_cast<const void*>(camoMaterial),
                                 T6WeaponCamoMaterialName(camoMaterial));
                }
            }
        }
    }
}
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oat_root", type=Path)
    args = ap.parse_args()
    path = args.oat_root.resolve() / TARGET
    if not path.is_file():
        raise SystemExit(f"pinned OAT source missing: {TARGET}")

    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"already-patched: {TARGET}")
        return 0

    include_needle = '#include <cassert>\n'
    if text.count(include_needle) != 1:
        raise SystemExit("unexpected pinned ContentLoaderT6 include layout")
    text = text.replace(include_needle, '#include <cassert>\n#include <cstdio>\n', 1)

    helper_needle = 'using namespace T6;\n\n'
    if text.count(helper_needle) != 1:
        raise SystemExit("unexpected pinned ContentLoaderT6 namespace layout")
    text = text.replace(helper_needle, helper_needle + HELPER + '\n', 1)

    loop_needle = '''    for (size_t index = 0; index < count; index++)\n    {\n        LoadXAsset(false);\n        varXAsset++;\n'''
    loop_replacement = '''    for (size_t index = 0; index < count; index++)\n    {\n        LoadXAsset(false);\n        TraceT6WeaponCamoTarget(index, *varXAsset);\n        TraceT6WeaponCamo(index, *varXAsset);\n        varXAsset++;\n'''
    if text.count(loop_needle) != 1:
        raise SystemExit("unexpected pinned ContentLoaderT6 XAsset loop layout")
    text = text.replace(loop_needle, loop_replacement, 1)

    if text.count(MARKER) != 1 or text.count('TraceT6WeaponCamo(') != 2 or text.count('TraceT6WeaponCamoTarget(') != 2:
        raise SystemExit("WeaponCamo semantic trace patch did not close exactly")
    path.write_text(text, encoding="utf-8")
    print(f"patched: {TARGET}: native WeaponCamo semantic trace with pointer anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
