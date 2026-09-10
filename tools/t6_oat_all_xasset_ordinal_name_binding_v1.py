#!/usr/bin/env python3
"""Bind pinned-OAT canonical T6 XAsset names to exact retail table ordinals.

The retail expanded XFile is the authority for ordinal/type/raw-pointer identity.
Pinned OAT is used only as a native loader/name-accessor oracle. A result is
accepted only if the native trace covers every physical XAsset ordinal exactly
once and reports the same type at every ordinal.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import struct
from pathlib import Path

FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
TRACE_MARKER = "T6_XASSET_ORDINAL_NAME\t"
PINNED_OAT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"

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
assert len(TYPE_NAMES) == 60

NAME_ACCESSORS = {
    1: "PhysPreset.name",
    2: "PhysConstraints.name",
    3: "DestructibleDef.name",
    4: "XAnimParts.name",
    5: "XModel.name",
    6: "Material.info.name",
    7: "MaterialTechniqueSet.name",
    8: "GfxImage.name",
    9: "SndBank.name",
    10: "SndPatch.name",
    11: "clipMap_t.name",
    12: "clipMap_t.name",
    13: "ComWorld.name",
    14: "GameWorldSp.name",
    15: "GameWorldMp.name",
    16: "MapEnts.name",
    17: "GfxWorld.name",
    18: "GfxLightDef.name",
    20: "Font_s.fontName",
    21: "FontIcon.name",
    22: "MenuList.name",
    23: "menuDef_t.window.name",
    24: "LocalizeEntry.name",
    25: "WeaponVariantDef.szInternalName",
    29: "WeaponAttachment.szInternalName",
    30: "WeaponAttachmentUnique.szInternalName",
    31: "WeaponCamo.name",
    32: "SndDriverGlobals.name",
    33: "FxEffectDef.name",
    34: "singleton:ImpactFx",
    41: "RawFile.name",
    42: "StringTable.name",
    43: "LeaderboardDef.name",
    44: "XGlobals.name",
    45: "ddlRoot_t.name",
    46: "Glasses.name",
    47: "singleton:EmblemSet",
    48: "ScriptParseTree.name",
    49: "KeyValuePairs.name",
    50: "VehicleDef.name",
    51: "MemoryBlock.name",
    52: "AddonMapEnts.name",
    53: "TracerDef.name",
    54: "SkinnedVertsDef.name",
    55: "Qdb.name",
    56: "Slug.name",
    57: "FootstepTableDef.name",
    58: "FootstepFXTableDef.name",
    59: "ZBarrierDef.name",
}
UNSUPPORTED_NATIVE_TYPES = sorted(set(range(60)) - set(NAME_ACCESSORS))
assert UNSUPPORTED_NATIVE_TYPES == [0, 19, 26, 27, 28, 35, 36, 37, 38, 39, 40]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cstring_end(data: bytes, pos: int, label: str) -> int:
    if pos < 0 or pos >= len(data):
        raise ValueError(f"{label} starts outside expanded stream: {pos}")
    end = data.find(b"\0", pos)
    if end < 0:
        raise ValueError(f"unterminated {label} at {pos}")
    return end + 1


def parse_xasset_table(data: bytes) -> dict:
    if len(data) < 64:
        raise ValueError("expanded XFile shorter than T6 XAssetList front")
    block_sizes = list(struct.unpack_from("<8I", data, 8))
    script_count, script_ptr, dep_count, dep_ptr, asset_count, asset_ptr = struct.unpack_from("<6I", data, 40)
    if script_count and script_ptr != FOLLOWING:
        raise ValueError(f"ScriptString list is not FOLLOWING: 0x{script_ptr:08X}")
    if dep_count and dep_ptr != FOLLOWING:
        raise ValueError(f"dependency list is not FOLLOWING: 0x{dep_ptr:08X}")
    if asset_count and asset_ptr != FOLLOWING:
        raise ValueError(f"XAsset array is not FOLLOWING: 0x{asset_ptr:08X}")

    pos = 64
    for label, count in (("ScriptString", script_count), ("dependency", dep_count)):
        ptr_bytes = count * 4
        if pos + ptr_bytes > len(data):
            raise ValueError(f"{label} pointer table truncated")
        ptrs = struct.unpack_from(f"<{count}I", data, pos) if count else ()
        pos += ptr_bytes
        for index, raw in enumerate(ptrs):
            if raw in (FOLLOWING, INSERT):
                pos = cstring_end(data, pos, f"{label}[{index}]")

    asset_array = pos
    asset_bytes = asset_count * 8
    if asset_array + asset_bytes > len(data):
        raise ValueError("physical XAsset array truncated")
    assets = []
    for index in range(asset_count):
        off = asset_array + index * 8
        asset_type, raw_pointer = struct.unpack_from("<II", data, off)
        if asset_type >= len(TYPE_NAMES):
            raise ValueError(f"XAsset {index} has invalid T6 type {asset_type}")
        assets.append({
            "index": index,
            "assetType": asset_type,
            "assetTypeName": TYPE_NAMES[asset_type],
            "rawPointer": raw_pointer,
            "tableSourceOffset": off,
        })
    return {
        "blockSizes": block_sizes,
        "scriptCount": script_count,
        "dependencyCount": dep_count,
        "assetCount": asset_count,
        "assetArraySourceOffset": asset_array,
        "assetBodySourceOffset": asset_array + asset_bytes,
        "assets": assets,
    }


def parse_trace(text: str) -> dict[int, tuple[int, str]]:
    rows: dict[int, tuple[int, str]] = {}
    for line_no, line in enumerate(text.splitlines(), 1):
        marker_at = line.find(TRACE_MARKER)
        if marker_at < 0:
            continue
        payload = line[marker_at + len(TRACE_MARKER):]
        fields = payload.split("\t", 2)
        if len(fields) != 3:
            raise ValueError(f"malformed all-XAsset trace line {line_no}: {line!r}")
        ordinal_text, type_text, name = fields
        if not re.fullmatch(r"[0-9]+", ordinal_text) or not re.fullmatch(r"[0-9]+", type_text):
            raise ValueError(f"invalid ordinal/type on trace line {line_no}: {line!r}")
        ordinal = int(ordinal_text)
        asset_type = int(type_text)
        if ordinal in rows:
            raise ValueError(f"duplicate native XAsset trace ordinal {ordinal}")
        if not name or name == "<null>":
            raise ValueError(f"native XAsset ordinal {ordinal} type {asset_type} has null/empty canonical name")
        if "\t" in name or any(ord(ch) < 0x20 or ord(ch) > 0x7E for ch in name):
            raise ValueError(f"native XAsset ordinal {ordinal} has non-printable canonical name {name!r}")
        rows[ordinal] = (asset_type, name)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--native-log", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--oat-commit", default=PINNED_OAT)
    args = ap.parse_args()
    if args.oat_commit != PINNED_OAT:
        raise SystemExit(f"refusing unpinned OAT commit {args.oat_commit!r}")

    expanded = args.expanded.read_bytes()
    native_log_bytes = args.native_log.read_bytes()
    native_log = native_log_bytes.decode("utf-8", "strict")
    table = parse_xasset_table(expanded)
    native = parse_trace(native_log)

    expected_ordinals = list(range(table["assetCount"]))
    native_ordinals = sorted(native)
    if native_ordinals != expected_ordinals:
        missing = sorted(set(expected_ordinals) - set(native_ordinals))
        extra = sorted(set(native_ordinals) - set(expected_ordinals))
        raise SystemExit(f"native all-XAsset trace population mismatch: missing={missing[:20]} extra={extra[:20]}")

    rows = []
    type_counts = collections.Counter()
    typed_names: dict[tuple[int, str], list[int]] = collections.defaultdict(list)
    for source in table["assets"]:
        ordinal = source["index"]
        native_type, name = native[ordinal]
        if native_type != source["assetType"]:
            raise SystemExit(
                f"XAsset {ordinal}: native type {native_type} != retail table type {source['assetType']}"
            )
        if native_type not in NAME_ACCESSORS:
            raise SystemExit(
                f"XAsset {ordinal}: type {native_type} ({TYPE_NAMES[native_type]}) native-loaded despite no pinned name accessor"
            )
        type_counts[native_type] += 1
        typed_names[(native_type, name)].append(ordinal)
        rows.append({
            "xassetIndex": ordinal,
            "assetType": native_type,
            "assetTypeName": TYPE_NAMES[native_type],
            "rawXAssetPointer": f"0x{source['rawPointer']:08X}",
            "tableSourceOffset": source["tableSourceOffset"],
            "nameAccessor": NAME_ACCESSORS[native_type],
            "nativeResolvedName": name,
        })

    duplicate_typed = [
        {
            "assetType": asset_type,
            "assetTypeName": TYPE_NAMES[asset_type],
            "name": name,
            "xassetIndices": indices,
        }
        for (asset_type, name), indices in sorted(typed_names.items())
        if len(indices) > 1
    ]
    observed = {
        TYPE_NAMES[t]: {
            "assetType": t,
            "count": type_counts[t],
            "nameAccessor": NAME_ACCESSORS[t],
            "resolvedNameCount": type_counts[t],
        }
        for t in sorted(type_counts)
    }
    absent_unsupported = [TYPE_NAMES[t] for t in UNSUPPORTED_NATIVE_TYPES if type_counts[t] == 0]
    if len(rows) != table["assetCount"]:
        raise SystemExit("all-XAsset row accounting drift")

    output = {
        "format": "t6-oat-all-xasset-ordinal-name-binding-v1",
        "authority": "SHA-pinned expanded retail XFile physical XAsset table + pinned OAT native family loaders + pinned OAT canonical asset-name accessors",
        "oatCommit": args.oat_commit,
        "expandedSha256": sha256_bytes(expanded),
        "nativeLogSha256": sha256_bytes(native_log_bytes),
        "xassetCount": table["assetCount"],
        "tracedNameCount": len(rows),
        "unresolvedNameCount": table["assetCount"] - len(rows),
        "distinctObservedAssetTypeCount": len(type_counts),
        "observedAssetTypes": observed,
        "unsupportedNativeTypeIds": UNSUPPORTED_NATIVE_TYPES,
        "unsupportedNativeTypeNames": [TYPE_NAMES[t] for t in UNSUPPORTED_NATIVE_TYPES],
        "unsupportedTypesAbsentFromThisZone": absent_unsupported,
        "uniqueTypedNameCount": len(typed_names),
        "duplicateTypedNameGroupCount": len(duplicate_typed),
        "duplicateTypedNameGroups": duplicate_typed,
        "rows": rows,
        "proofBoundary": "Every physical retail XAsset ordinal must appear exactly once in the native trace, and its native type must equal the independently parsed retail XAsset table type at that ordinal. Names come only from pinned OAT's canonical T6 asset-name accessors after the normal family loader has resolved pointers. Null/empty/non-printable names, missing ordinals, extra ordinals, type disagreement, unsupported native types, and partial native loads all fail closed. No dump filename, filesystem order, naming heuristic, or neighboring pointer is used.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k not in ("rows", "duplicateTypedNameGroups")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
