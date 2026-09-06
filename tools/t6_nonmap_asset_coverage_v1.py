#!/usr/bin/env python3
"""Build a measurable non-map T6 XAsset extraction coverage report.

Consumes JSON inventories emitted by tools/t6_raw_xasset_inventory.py and maps
every T6 XAsset class to the strongest currently retained extraction family.
Unsupported classes remain explicit and can never disappear into an "other"
bucket.

Pinned upstream baseline:
Laupetin/OpenAssetTools@7d027e8f89118196713e955b0e11f8404149c54d
docs/SupportedAssetTypes.md

"OAT-dumpable" means that pinned Unlinker revision can dump the T6 asset class;
it is deliberately weaker than this repository's own proof-backed "usable"
status until exact outputs are retained and regression-checked here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

FORMAT = "t6-nonmap-asset-coverage-v1"
OAT_REPOSITORY = "Laupetin/OpenAssetTools"
OAT_COMMIT = "7d027e8f89118196713e955b0e11f8404149c54d"
OAT_SUPPORT_DOC = "docs/SupportedAssetTypes.md"

ASSET_TYPES = [
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

# "usable" = retained production-oriented repo path.
# "oat-dumpable" = pinned stock OAT can dump this T6 class, but the repo still
# needs a hash-pinned retention/regression pass before promoting it to usable.
REGISTRY = {
    "XANIMPARTS": ("animation", "usable",
        ["tools/t6_xanim_normalize_v1.py", "tools/t6_xanim_skinned_gltf_export_v7.py"]),
    "XMODEL": ("model", "usable",
        ["tools/t6_xmodel_mesh_normalize_v1.py", "tools/t6_xmodel_skeleton_normalize_v2.py",
         "tools/t6_xanim_skinned_gltf_export_v7.py"]),
    "MATERIAL": ("material", "usable",
        ["tools/t6_oat_material_manifest_v3.py", "tools/t6_oat_material_manifest_v4.py"]),
    "IMAGE": ("texture", "usable", ["tools/t6_dds_texture_stage_v2.py"]),

    "PHYSPRESET": ("physics", "oat-dumpable", ["OpenAssetTools:T6/PhysPreset"]),
    "PHYSCONSTRAINTS": ("physics", "oat-dumpable", ["OpenAssetTools:T6/PhysConstraints"]),
    "TECHNIQUE_SET": ("shader", "oat-dumpable", ["OpenAssetTools:T6/MaterialTechniqueSet"]),
    "SOUND": ("audio", "oat-dumpable", ["OpenAssetTools:T6/SndBank"]),
    "FONT": ("ui", "oat-dumpable", ["OpenAssetTools:T6/Font_s"]),
    "FONTICON": ("ui", "oat-dumpable", ["OpenAssetTools:T6/FontIcon"]),
    "LOCALIZE_ENTRY": ("script-data", "oat-dumpable", ["OpenAssetTools:T6/LocalizeEntry"]),
    "WEAPON_VARIANT": ("weapon-definition", "oat-dumpable",
        ["OpenAssetTools:T6/WeaponVariantDef", "tools/t6_raw_xasset_inventory.py"]),
    "ATTACHMENT": ("weapon-definition", "oat-dumpable", ["OpenAssetTools:T6/WeaponAttachment"]),
    "ATTACHMENT_UNIQUE": ("weapon-definition", "oat-dumpable", ["OpenAssetTools:T6/WeaponAttachmentUnique"]),
    "WEAPON_CAMO": ("weapon-definition", "oat-dumpable", ["OpenAssetTools:T6/WeaponCamo"]),
    "SNDDRIVER_GLOBALS": ("audio", "oat-dumpable", ["OpenAssetTools:T6/SndDriverGlobals"]),
    "RAWFILE": ("script-data", "oat-dumpable", ["OpenAssetTools:T6/RawFile"]),
    "STRINGTABLE": ("script-data", "oat-dumpable", ["OpenAssetTools:T6/StringTable"]),
    "LEADERBOARD": ("script-data", "oat-dumpable", ["OpenAssetTools:T6/LeaderboardDef"]),
    "KEYVALUEPAIRS": ("script-data", "oat-dumpable", ["OpenAssetTools:T6/KeyValuePairs"]),
    "VEHICLEDEF": ("vehicle-definition", "oat-dumpable", ["OpenAssetTools:T6/VehicleDef"]),
    "TRACER": ("weapon-definition", "oat-dumpable", ["OpenAssetTools:T6/TracerDef"]),
    "ZBARRIER": ("gameplay-definition", "oat-dumpable", ["OpenAssetTools:T6/ZBarrierDef"]),

    "SCRIPTPARSETREE": ("script-data", "partial", ["OpenAssetTools:T6/ScriptParseTree(binary)"]),
    "QDB": ("script-data", "partial", ["OpenAssetTools:T6/Qdb(rawfile)"]),
    "SLUG": ("script-data", "partial", ["OpenAssetTools:T6/Slug(rawfile)"]),
    "WEAPON": ("weapon-definition", "partial", []),
    "WEAPONDEF": ("weapon-definition", "partial", []),
    "WEAPON_FULL": ("weapon-definition", "partial", []),
    "DESTRUCTIBLEDEF": ("physics", "partial", []),
    "FX": ("fx", "partial", []),
    "IMPACT_FX": ("fx", "partial", []),

    "MPBODY": ("character-definition", "inventory-only", []),
    "MPHEAD": ("character-definition", "inventory-only", []),
    "CHARACTER": ("character-definition", "inventory-only", []),
    "AITYPE": ("character-definition", "inventory-only", []),
    "MPTYPE": ("character-definition", "inventory-only", []),
    "XMODELALIAS": ("character-definition", "inventory-only", []),
    "SOUND_PATCH": ("audio", "inventory-only", []),
    "UI_MAP": ("ui", "inventory-only", []),
    "MENULIST": ("ui", "inventory-only", []),
    "MENU": ("ui", "inventory-only", []),
    "XGLOBALS": ("gameplay-definition", "inventory-only", []),
    "DDL": ("gameplay-definition", "inventory-only", []),
    "GLASSES": ("ui", "inventory-only", []),
    "EMBLEMSET": ("ui", "inventory-only", []),
    "MEMORYBLOCK": ("gameplay-definition", "inventory-only", []),
    "SKINNEDVERTS": ("model", "inventory-only", []),
    "FOOTSTEP_TABLE": ("audio-fx", "inventory-only", []),
    "FOOTSTEPFX_TABLE": ("audio-fx", "inventory-only", []),
    "XMODELPIECES": ("model", "inventory-only", []),
}

MAP_ONLY = {
    "CLIPMAP", "CLIPMAP_PVS", "COMWORLD", "GAMEWORLD_SP", "GAMEWORLD_MP",
    "MAP_ENTS", "GFXWORLD", "LIGHT_DEF", "ADDON_MAP_ENTS",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_inventory(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: inventory must be an object")
    counts = doc.get("asset_type_counts")
    if not isinstance(counts, dict):
        raise ValueError(f"{path}: missing asset_type_counts")
    unknown = sorted(set(counts) - set(ASSET_TYPES))
    if unknown:
        raise ValueError(f"{path}: unknown asset types {unknown}")
    return doc


def classification(asset_type: str) -> tuple[str, str, list[str]]:
    if asset_type in MAP_ONLY:
        return "map", "handled-by-map-track", []
    return REGISTRY.get(asset_type, ("unclassified", "open", []))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inventories", nargs="+", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    total = Counter()
    sources = []
    per_type_sources = defaultdict(list)
    for path in args.inventories:
        doc = load_inventory(path)
        counts = Counter({k: int(v) for k, v in doc["asset_type_counts"].items()})
        total.update(counts)
        sources.append({
            "path": str(path),
            "sha256": sha256(path),
            "expandedSha256": doc.get("expanded_sha256"),
            "assetCount": int(doc.get("asset_count", sum(counts.values()))),
            "assetTypeCount": sum(1 for v in counts.values() if v),
        })
        for k, v in counts.items():
            if v:
                per_type_sources[k].append({"path": str(path), "count": v})

    rows = []
    status_counts = Counter()
    category_counts = Counter()
    nonmap_assets = 0
    for asset_type in ASSET_TYPES:
        count = int(total.get(asset_type, 0))
        category, status, tools = classification(asset_type)
        if asset_type not in MAP_ONLY:
            nonmap_assets += count
        if count:
            status_counts[status] += count
            category_counts[category] += count
        rows.append({
            "assetType": asset_type,
            "count": count,
            "category": category,
            "status": status,
            "tools": tools,
            "observedIn": per_type_sources.get(asset_type, []),
        })

    unresolved = [
        r["assetType"] for r in rows
        if r["count"] and r["assetType"] not in MAP_ONLY and r["status"] in {"open", "inventory-only"}
    ]
    priority = [
        r["assetType"] for r in rows
        if r["count"] and r["assetType"] not in MAP_ONLY
        and r["status"] not in {"usable", "oat-dumpable"}
    ]
    oat_pending_promotion = [
        r["assetType"] for r in rows
        if r["count"] and r["status"] == "oat-dumpable"
    ]

    out = {
        "format": FORMAT,
        "goal": "Make every non-map T6 XAsset class measurable until all observed classes have deterministic extraction and retained retail proof.",
        "upstreamBaseline": {
            "repository": OAT_REPOSITORY,
            "commit": OAT_COMMIT,
            "supportDocument": OAT_SUPPORT_DOC,
            "policy": "OAT dump support is useful extraction coverage but remains weaker than repo-retained retail proof.",
        },
        "rules": {
            "everyKnownT6AssetTypeListed": True,
            "unsupportedTypesRemainExplicit": True,
            "mapTrackSeparatedButNotDiscarded": True,
            "countsAreOccurrencesAcrossSuppliedZoneInventories": True,
            "usableDoesNotMeanP8UniversalClosure": True,
            "oatDumpableRequiresRepoPromotionBeforeUsable": True,
        },
        "sourceInventories": sources,
        "summary": {
            "inventoryFiles": len(sources),
            "assetOccurrences": sum(total.values()),
            "nonMapAssetOccurrences": nonmap_assets,
            "observedAssetTypes": sum(1 for r in rows if r["count"]),
            "unresolvedObservedNonMapTypes": unresolved,
            "priorityObservedNonMapTypes": priority,
            "oatDumpableObservedTypesPendingRepoPromotion": oat_pending_promotion,
            "statusOccurrenceCounts": dict(sorted(status_counts.items())),
            "categoryOccurrenceCounts": dict(sorted(category_counts.items())),
        },
        "assetTypes": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
