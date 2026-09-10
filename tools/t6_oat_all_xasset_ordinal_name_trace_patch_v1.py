#!/usr/bin/env python3
"""Instrument pinned OAT T6 ContentLoader with an all-XAsset ordinal/name trace.

This is diagnostic-only instrumentation. It changes no loader stream, pointer,
asset registration, or dump semantics. The trace is emitted only after the
normal T6 family loader has completed for the current physical XAsset entry and
before varXAsset advances to the next ordinal.

The accessor switch is copied from pinned OAT's T6 asset-name accessors. Types
that pinned OAT does not load are deliberately absent; if one occurs, normal
ContentLoaderT6 throws before a trace row can be emitted and the consuming
workflow fails closed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TARGET = "src/ZoneLoading/Game/T6/ContentLoaderT6.cpp"
MARKER = "T6_XASSET_ORDINAL_NAME"

HELPER = r'''
namespace
{
    const char* TraceT6XAssetName(const XAsset& asset)
    {
        switch (asset.type)
        {
        case ASSET_TYPE_PHYSPRESET: return asset.header.physPreset ? asset.header.physPreset->name : nullptr;
        case ASSET_TYPE_PHYSCONSTRAINTS: return asset.header.physConstraints ? asset.header.physConstraints->name : nullptr;
        case ASSET_TYPE_DESTRUCTIBLEDEF: return asset.header.destructibleDef ? asset.header.destructibleDef->name : nullptr;
        case ASSET_TYPE_XANIMPARTS: return asset.header.parts ? asset.header.parts->name : nullptr;
        case ASSET_TYPE_XMODEL: return asset.header.model ? asset.header.model->name : nullptr;
        case ASSET_TYPE_MATERIAL: return asset.header.material ? asset.header.material->info.name : nullptr;
        case ASSET_TYPE_TECHNIQUE_SET: return asset.header.techniqueSet ? asset.header.techniqueSet->name : nullptr;
        case ASSET_TYPE_IMAGE: return asset.header.image ? asset.header.image->name : nullptr;
        case ASSET_TYPE_SOUND: return asset.header.sound ? asset.header.sound->name : nullptr;
        case ASSET_TYPE_SOUND_PATCH: return asset.header.soundPatch ? asset.header.soundPatch->name : nullptr;
        case ASSET_TYPE_CLIPMAP:
        case ASSET_TYPE_CLIPMAP_PVS: return asset.header.clipMap ? asset.header.clipMap->name : nullptr;
        case ASSET_TYPE_COMWORLD: return asset.header.comWorld ? asset.header.comWorld->name : nullptr;
        case ASSET_TYPE_GAMEWORLD_SP: return asset.header.gameWorldSp ? asset.header.gameWorldSp->name : nullptr;
        case ASSET_TYPE_GAMEWORLD_MP: return asset.header.gameWorldMp ? asset.header.gameWorldMp->name : nullptr;
        case ASSET_TYPE_MAP_ENTS: return asset.header.mapEnts ? asset.header.mapEnts->name : nullptr;
        case ASSET_TYPE_GFXWORLD: return asset.header.gfxWorld ? asset.header.gfxWorld->name : nullptr;
        case ASSET_TYPE_LIGHT_DEF: return asset.header.lightDef ? asset.header.lightDef->name : nullptr;
        case ASSET_TYPE_FONT: return asset.header.font ? asset.header.font->fontName : nullptr;
        case ASSET_TYPE_FONTICON: return asset.header.fontIcon ? asset.header.fontIcon->name : nullptr;
        case ASSET_TYPE_MENULIST: return asset.header.menuList ? asset.header.menuList->name : nullptr;
        case ASSET_TYPE_MENU: return asset.header.menu ? asset.header.menu->window.name : nullptr;
        case ASSET_TYPE_LOCALIZE_ENTRY: return asset.header.localize ? asset.header.localize->name : nullptr;
        case ASSET_TYPE_WEAPON: return asset.header.weapon ? asset.header.weapon->szInternalName : nullptr;
        case ASSET_TYPE_ATTACHMENT: return asset.header.attachment ? asset.header.attachment->szInternalName : nullptr;
        case ASSET_TYPE_ATTACHMENT_UNIQUE: return asset.header.attachmentUnique ? asset.header.attachmentUnique->szInternalName : nullptr;
        case ASSET_TYPE_WEAPON_CAMO: return asset.header.weaponCamo ? asset.header.weaponCamo->name : nullptr;
        case ASSET_TYPE_SNDDRIVER_GLOBALS: return asset.header.sndDriverGlobals ? asset.header.sndDriverGlobals->name : nullptr;
        case ASSET_TYPE_FX: return asset.header.fx ? asset.header.fx->name : nullptr;
        case ASSET_TYPE_IMPACT_FX: return "ImpactFx";
        case ASSET_TYPE_RAWFILE: return asset.header.rawfile ? asset.header.rawfile->name : nullptr;
        case ASSET_TYPE_STRINGTABLE: return asset.header.stringTable ? asset.header.stringTable->name : nullptr;
        case ASSET_TYPE_LEADERBOARD: return asset.header.leaderboardDef ? asset.header.leaderboardDef->name : nullptr;
        case ASSET_TYPE_XGLOBALS: return asset.header.xGlobals ? asset.header.xGlobals->name : nullptr;
        case ASSET_TYPE_DDL: return asset.header.ddlRoot ? asset.header.ddlRoot->name : nullptr;
        case ASSET_TYPE_GLASSES: return asset.header.glasses ? asset.header.glasses->name : nullptr;
        case ASSET_TYPE_EMBLEMSET: return "EmblemSet";
        case ASSET_TYPE_SCRIPTPARSETREE: return asset.header.scriptParseTree ? asset.header.scriptParseTree->name : nullptr;
        case ASSET_TYPE_KEYVALUEPAIRS: return asset.header.keyValuePairs ? asset.header.keyValuePairs->name : nullptr;
        case ASSET_TYPE_VEHICLEDEF: return asset.header.vehicleDef ? asset.header.vehicleDef->name : nullptr;
        case ASSET_TYPE_MEMORYBLOCK: return asset.header.memoryBlock ? asset.header.memoryBlock->name : nullptr;
        case ASSET_TYPE_ADDON_MAP_ENTS: return asset.header.addonMapEnts ? asset.header.addonMapEnts->name : nullptr;
        case ASSET_TYPE_TRACER: return asset.header.tracerDef ? asset.header.tracerDef->name : nullptr;
        case ASSET_TYPE_SKINNEDVERTS: return asset.header.skinnedVertsDef ? asset.header.skinnedVertsDef->name : nullptr;
        case ASSET_TYPE_QDB: return asset.header.qdb ? asset.header.qdb->name : nullptr;
        case ASSET_TYPE_SLUG: return asset.header.slug ? asset.header.slug->name : nullptr;
        case ASSET_TYPE_FOOTSTEP_TABLE: return asset.header.footstepTableDef ? asset.header.footstepTableDef->name : nullptr;
        case ASSET_TYPE_FOOTSTEPFX_TABLE: return asset.header.footstepFXTableDef ? asset.header.footstepFXTableDef->name : nullptr;
        case ASSET_TYPE_ZBARRIER: return asset.header.zbarrierDef ? asset.header.zbarrierDef->name : nullptr;
        default: return nullptr;
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
    loop_replacement = '''    for (size_t index = 0; index < count; index++)\n    {\n        LoadXAsset(false);\n        const auto* traceName = TraceT6XAssetName(*varXAsset);\n        std::fprintf(stderr, "T6_XASSET_ORDINAL_NAME\\t%zu\\t%u\\t%s\\n",\n                     index,\n                     static_cast<unsigned>(varXAsset->type),\n                     traceName ? traceName : "<null>");\n        varXAsset++;\n'''
    if text.count(loop_needle) != 1:
        raise SystemExit("unexpected pinned ContentLoaderT6 XAsset loop layout")
    text = text.replace(loop_needle, loop_replacement, 1)

    if text.count(MARKER) != 1 or text.count('TraceT6XAssetName') != 2:
        raise SystemExit("all-XAsset trace patch did not close exactly")
    path.write_text(text, encoding="utf-8")
    print(f"patched: {TARGET}: all-XAsset ordinal/name trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
