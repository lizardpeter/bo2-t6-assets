#!/usr/bin/env python3
"""Exact front-of-zone inventory for the six T6 character ownership XAsset classes.

This probe intentionally stops at the XAsset table. It does not need serializers
for AiType/MpType/MpBody/MpHead/Character/XModelAlias and therefore can establish
which classes occur in a retail FastFile before their body layouts are recovered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

TYPE_NAMES = [
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
]
TARGET_IDS = set(range(35, 41))
PTR_FOLLOWING = 0xFFFFFFFF


def cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(b"\0", pos)
    return data[pos:end].decode("latin1"), end + 1


def parse_front(data: bytes) -> dict:
    if len(data) < 64:
        raise ValueError("expanded FastFile is too small")
    size, external = struct.unpack_from("<II", data, 0)
    blocks = list(struct.unpack_from("<8I", data, 8))
    pos = 40
    string_count, strings_ptr, dependency_count, dependencies_ptr, asset_count, assets_ptr = struct.unpack_from("<6I", data, pos)
    pos += 24

    if string_count:
        if strings_ptr != PTR_FOLLOWING:
            raise ValueError("ScriptStringList is not inline")
        pointers = struct.unpack_from(f"<{string_count}I", data, pos)
        pos += string_count * 4
        for pointer in pointers:
            if pointer == PTR_FOLLOWING:
                _, pos = cstring(data, pos)

    if dependency_count:
        if dependencies_ptr != PTR_FOLLOWING:
            raise ValueError("dependency list is not inline")
        pointers = struct.unpack_from(f"<{dependency_count}I", data, pos)
        pos += dependency_count * 4
        for pointer in pointers:
            if pointer == PTR_FOLLOWING:
                _, pos = cstring(data, pos)

    if assets_ptr != PTR_FOLLOWING:
        raise ValueError("XAsset array is not inline")

    table_offset = pos
    entries = []
    counts = Counter()
    target_entries = []
    for index in range(asset_count):
        asset_type, header = struct.unpack_from("<II", data, pos)
        pos += 8
        if not 0 <= asset_type < len(TYPE_NAMES):
            raise ValueError(f"bad XAsset type {asset_type} at index {index}")
        name = TYPE_NAMES[asset_type]
        counts[name] += 1
        entry = {
            "index": index,
            "assetType": asset_type,
            "assetTypeName": name,
            "rawHeaderPointer": f"0x{header:08X}",
        }
        entries.append(entry)
        if asset_type in TARGET_IDS:
            target_entries.append(entry)

    return {
        "format": "t6-character-xasset-front-probe-v1",
        "expandedBytes": len(data),
        "expandedSha256": hashlib.sha256(data).hexdigest(),
        "declaredZoneSize": size,
        "declaredExternalSize": external,
        "blockSizes": blocks,
        "scriptStringCount": string_count,
        "dependencyCount": dependency_count,
        "assetCount": asset_count,
        "assetTableRawOffset": table_offset,
        "assetBodyStreamRawOffset": pos,
        "assetTypeCounts": dict(sorted(counts.items())),
        "characterOwnershipCounts": {
            TYPE_NAMES[i]: counts.get(TYPE_NAMES[i], 0) for i in sorted(TARGET_IDS)
        },
        "characterOwnershipEntries": target_entries,
        "assetEntries": entries,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--source-sha256")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    result = parse_front(data)
    result["zone"] = args.zone
    if args.source_sha256:
        result["sourceFastFileSha256"] = args.source_sha256.lower()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "zone": args.zone,
        "assetCount": result["assetCount"],
        "assetBodyStreamRawOffset": result["assetBodyStreamRawOffset"],
        "characterOwnershipCounts": result["characterOwnershipCounts"],
        "expandedSha256": result["expandedSha256"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
