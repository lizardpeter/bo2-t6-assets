#!/usr/bin/env python3
"""Canonical retail T6 PC XAsset type registry.

Keep numeric XAsset ids in one place.  These ids are the serialized enum values
used by the retail T6 XAsset array; they are not per-tool convenience numbers.
Generic parsers and indexes must import this module instead of duplicating the
list locally.
"""
from __future__ import annotations

ASSET_TYPES: tuple[str, ...] = (
    "XMODELPIECES", "PHYSPRESET", "PHYSCONSTRAINTS", "DESTRUCTIBLEDEF",
    "XANIMPARTS", "XMODEL", "MATERIAL", "TECHNIQUE_SET", "IMAGE", "SOUND",
    "SOUND_PATCH", "CLIPMAP", "CLIPMAP_PVS", "COMWORLD", "GAMEWORLD_SP",
    "GAMEWORLD_MP", "MAP_ENTS", "GFXWORLD", "LIGHT_DEF", "UI_MAP", "FONT",
    "FONTICON", "MENULIST", "MENU", "LOCALIZE_ENTRY", "WEAPON", "WEAPONDEF",
    "WEAPON_VARIANT", "WEAPON_FULL", "ATTACHMENT", "ATTACHMENT_UNIQUE",
    "WEAPON_CAMO", "SNDDRIVER_GLOBALS", "FX", "IMPACT_FX", "AITYPE", "MPTYPE",
    "MPBODY", "MPHEAD", "CHARACTER", "XMODELALIAS", "RAWFILE", "STRINGTABLE",
    "LEADERBOARD", "XGLOBALS", "DDL", "GLASSES", "EMBLEMSET", "SCRIPTPARSETREE",
    "KEYVALUEPAIRS", "VEHICLEDEF", "MEMORYBLOCK", "ADDON_MAP_ENTS", "TRACER",
    "SKINNEDVERTS", "QDB", "SLUG", "FOOTSTEP_TABLE", "FOOTSTEPFX_TABLE", "ZBARRIER",
)

ASSET_TYPE_BY_NAME: dict[str, int] = {name: i for i, name in enumerate(ASSET_TYPES)}

XANIMPARTS = ASSET_TYPE_BY_NAME["XANIMPARTS"]
XMODEL = ASSET_TYPE_BY_NAME["XMODEL"]
MATERIAL = ASSET_TYPE_BY_NAME["MATERIAL"]
TECHNIQUE_SET = ASSET_TYPE_BY_NAME["TECHNIQUE_SET"]
IMAGE = ASSET_TYPE_BY_NAME["IMAGE"]

# Hard canaries for the asset classes currently used by the universal exporter.
assert XANIMPARTS == 4
assert XMODEL == 5
assert MATERIAL == 6
assert TECHNIQUE_SET == 7
assert IMAGE == 8


def asset_type_name(value: int) -> str:
    if not 0 <= value < len(ASSET_TYPES):
        raise ValueError(f"invalid T6 XAsset type {value}")
    return ASSET_TYPES[value]


def asset_type_id(name: str) -> int:
    try:
        return ASSET_TYPE_BY_NAME[name]
    except KeyError as exc:
        raise ValueError(f"unknown T6 XAsset type {name!r}") from exc
